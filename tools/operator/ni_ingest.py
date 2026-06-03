#!/usr/bin/env python3
r"""ni-ingest -- operator-facing Nuclear Imaging (NI) ingest front-end.

Phase 2 of tasks/operator_ingest_tooling_plan.md. The simplest of the three
front-ends: the operator points at a folder and the script does the rest. It
hardcodes the instrument key NI -> molecubes_ni.yaml and reuses the validated
pipeline through the shared operator core (templates / config_builder / scope /
preview / runner / env). It never reimplements ingest logic.

Usage (on the Linux NI acquisition machine, via a managed repo checkout/venv):

    ni-ingest /path/to/folder              # preview table, then "Proceed? [y/N]"
    ni-ingest /path/to/folder --go         # skip the prompt and commit
    ni-ingest /path/to/folder --dry-run    # preview only, never prompts/commits
    ni-ingest /path/to/folder --nas-root /mnt/gjesus3

"folder" may be ONE extracted NI acquisition (parent + this folder become the
scope) OR a batch root whose children are extracted acquisitions (scope.py
auto-detects which). Idempotent dedup against the live registry makes re-running
safe -- already-ingested acquisitions are skipped.

----------------------------------------------------------------------------
ARCHIVE MODE vs LIVE MODE
----------------------------------------------------------------------------
ARCHIVE MODE works today. NI archives arrive as .tgz files from the SMB archive
(\\cicmgsp02\gnuclear2$); tools/extract_ni_archives.py pulls + extracts them so
each staged folder directly holds the acquisition's files (protocol.txt +
recon_<idx>/). This script ingests those extracted folders. If you point it at a
.tgz it explains the one extra step (and offers to run the extractor).

LIVE MODE (ingesting straight off the acquisition machine, no .tgz round-trip)
is NOT blocked on deployment -- the platform manager (Unai) confirmed the NI
server runs Linux and a script can be installed there. The ONE remaining piece
is the live folder layout, which will be captured in a future
molecubes_ni_live.yaml template + one detector branch here; the script and the
shared core are unchanged. Until that template exists, use archive mode (extract
the .tgz first). This script detects a likely live/non-extracted folder and
prints a clear "use archive mode for now" message instead of guessing a layout.
"""

import argparse
import importlib.util
import os
import sys
from datetime import datetime

# --- Import the shared operator core under its non-colliding alias ----------
#
# This package's directory is named `operator`, which shadows the stdlib
# `operator` module, so it ships NO importable top-level `__init__.py` (see
# tools/operator/IMPORT_CONTRACT.md). When this file is run directly
# (`python ni_ingest.py`) or via a console entry point there is no parent
# package, so relative imports are unavailable; we load the package through
# `_loader.py`, which registers it under the alias `gj_op_core` and wires up
# `tools/` on sys.path (appended, never inserted) so `ingest` / `ingest_raw`
# resolve while stdlib `operator` keeps winning.
_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_core():
    """Load and return the shared operator-core package (aliased gj_op_core)."""
    spec = importlib.util.spec_from_file_location(
        "gj_operator_loader", os.path.join(_HERE, "_loader.py")
    )
    loader_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader_mod)
    return loader_mod.load()


_CORE = _load_core()
templates = _CORE.templates
config_builder = _CORE.config_builder
scope = _CORE.scope
preview = _CORE.preview
runner = _CORE.runner
env = _CORE.env


INSTRUMENT_KEY = "NI"          # hardcoded -> molecubes_ni.yaml (templates map)


# --------------------------------------------------------------------- logging

def log(msg, level="INFO"):
    """Timestamped, ASCII-only log line to stderr ([HH:MM:SS] LEVEL: msg).

    Goes to STDERR so it never pollutes the preview table on stdout (a caller
    can capture the table cleanly). ingest_raw's own logs are routed here too
    via runner.run(log_callback=...).
    """
    ts = datetime.now().strftime("%H:%M:%S")
    sys.stderr.write(f"[{ts}] {level}: {msg}\n")
    sys.stderr.flush()


# --------------------------------------------------------------- archive detect

def _looks_like_tgz(path):
    """True if `path` is an NI archive file (.tgz / .tar.gz), not a folder."""
    lower = path.lower()
    return os.path.isfile(path) and (
        lower.endswith(".tgz") or lower.endswith(".tar.gz")
    )


def _dir_has_tgz_children(path):
    """True if `path` is a directory whose immediate children are .tgz archives."""
    if not os.path.isdir(path):
        return False
    try:
        for entry in os.scandir(path):
            if entry.is_file() and _looks_like_tgz(entry.path):
                return True
    except OSError:
        return False
    return False


def _explain_archive_and_maybe_extract(path, assume_yes):
    """Handle a .tgz (or folder-of-.tgz): tell the operator to extract first,
    and OFFER to run tools/extract_ni_archives.py for them.

    Returns an exit code (non-zero) -- this path never proceeds to ingest in
    this run; after extraction the operator re-points ni-ingest at the
    extracted staging folder.
    """
    extractor = os.path.normpath(os.path.join(_HERE, "..", "extract_ni_archives.py"))
    log(
        "that looks like a .tgz NI archive (or a folder of them). NI archives "
        "must be EXTRACTED before ingest.", "ERROR",
    )
    log(
        "Run the companion extractor first, then point ni-ingest at the "
        "extracted staging folder:", "INFO",
    )
    log(f"    python {extractor} --help", "INFO")

    if assume_yes:
        # --go is "skip prompts"; we still won't silently extract without
        # knowing the source/target args, so just instruct and exit.
        log(
            "(--go given, but extraction needs explicit archive + staging "
            "arguments -- run the extractor manually, then re-run ni-ingest "
            "on the extracted folder.)", "WARN",
        )
        return 2

    try:
        answer = input(
            "Show the extractor's options now? [y/N] "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer in ("y", "yes"):
        # Print the extractor help to stdout so the operator sees the exact
        # flags; we deliberately don't guess source/target for them.
        os.system(f'{sys.executable} "{extractor}" --help')
    log(
        "After extraction, re-run: ni-ingest <extracted-staging-folder>",
        "INFO",
    )
    return 2


# ------------------------------------------------------------------ live detect

def _looks_like_live_acquisition(path):
    """Heuristic: a folder that is NOT an extracted-archive NI acquisition and
    NOT a batch root of them, but still plausibly holds raw NI output -- i.e. a
    likely LIVE / non-extracted acquisition whose layout we don't yet model.

    Conservative: returns True only when scope.resolve_scope has already failed
    (so we're not stealing the well-defined archive-mode path) AND the folder
    shows some NI-ish signal. Right now the signal is intentionally loose (any
    non-empty folder), because the live layout is exactly what's still
    undocumented -- we'd rather print the clear "use archive mode" message than
    guess. This branch is replaced by a real detector when
    molecubes_ni_live.yaml lands.
    """
    if not os.path.isdir(path):
        return False
    try:
        return any(True for _ in os.scandir(path))
    except OSError:
        return False


def _explain_live_mode(path):
    """Print the clear, non-blaming live-mode message and return an exit code."""
    log(
        f"{path!r} doesn't look like an EXTRACTED NI archive (it has no "
        "protocol.txt + recon_<idx>/ acquisition folders).", "ERROR",
    )
    log(
        "NI live mode (ingesting straight off the acquisition machine) is "
        "pending the live folder layout -- a future molecubes_ni_live.yaml "
        "template. Deployment itself is NOT blocked (the NI server runs Linux "
        "and a script can be installed there); only the live-layout template "
        "remains. Use ARCHIVE MODE for now:", "INFO",
    )
    log(
        "  1. extract the .tgz archives with tools/extract_ni_archives.py", "INFO",
    )
    log(
        "  2. point ni-ingest at the extracted staging folder", "INFO",
    )
    return 3


# ------------------------------------------------------------------ preview tbl

def _count_files(folder):
    """Cheap recursive file count under `folder` (the n_files preview column).

    Best-effort: returns 0 (not an error) if the folder can't be walked. This is
    the SOURCE file count, an approximation of what lands on the NAS -- the
    ni_molecubes copy strategy drops some operational files, so the on-disk
    count may be lower. Shown only to give the operator a sense of scale.
    """
    if not folder or not os.path.isdir(folder):
        return 0
    n = 0
    try:
        for _root, _dirs, files in os.walk(folder):
            n += len(files)
    except OSError:
        pass
    return n


def _short(value, width):
    """Truncate `value` to `width` chars with an ellipsis marker for the table."""
    s = "" if value is None else str(value)
    if len(s) <= width:
        return s
    if width <= 1:
        return s[:width]
    return s[: width - 1] + "~"


def _print_preview_table(result):
    """Print the operator preview table to STDOUT:
    acq_id | sample_id | project | link name | n_files. Returns nothing.
    """
    cols = [
        ("acq_id", 24),
        ("sample_id", 14),
        ("project", 22),
        ("link name", 34),
        ("n_files", 8),
    ]
    header = "  ".join(name.ljust(w) for name, w in cols)
    sep = "  ".join("-" * w for _name, w in cols)
    print(header)
    print(sep)

    for case in result.cases:
        sample_id = (case.registry_resolved or {}).get("sample_id", "")
        n_files = _count_files(case.source)
        row = [
            _short(case.acq_id_preview, cols[0][1]).ljust(cols[0][1]),
            _short(sample_id, cols[1][1]).ljust(cols[1][1]),
            _short(case.project_preview, cols[2][1]).ljust(cols[2][1]),
            _short(case.link_filename_preview, cols[3][1]).ljust(cols[3][1]),
            str(n_files).rjust(cols[4][1]),
        ]
        print("  ".join(row))

    print(sep)
    print(
        f"{result.n_new} new acquisition(s) to ingest; "
        f"{result.n_skipped} already ingested (skipped); "
        f"{result.n_matched} matched on disk."
    )

    # Surface per-case warnings (e.g. unresolved tokens) below the table.
    flagged = [c for c in result.cases if c.warnings]
    if flagged:
        print("")
        print("Warnings:")
        for c in flagged:
            label = c.acq_id_preview or c.original_name or c.source
            for w in c.warnings:
                print(f"  [{label}] {w}")


# ----------------------------------------------------------------------- runner

def _build_cfg(staging_dir, pattern):
    """Load the NI template and apply the scope overrides -> in-memory cfg."""
    template = templates.load_template(INSTRUMENT_KEY)
    overrides = {
        "auto_discover.staging_dir": staging_dir,
        "auto_discover.pattern": pattern,
    }
    return config_builder.build_config(template, overrides)


def _commit(cfg, nas_root):
    """Run the real ingest, routing the pipeline log to our stderr logger."""
    recipe = runner.default_recipe_path(templates.template_path(INSTRUMENT_KEY))
    results = runner.run(
        cfg, nas_root,
        dry_run=False, delete_source=False,
        log_callback=log, recipe_path=recipe,
    )
    ok = sum(1 for _acq, success in results if success)
    failed = [acq for acq, success in results if not success]
    if failed:
        log(
            f"ingest finished: {ok} OK, {len(failed)} FAILED "
            f"({', '.join(failed)})", "ERROR",
        )
        return 1
    log(f"ingest finished: {ok} acquisition(s) ingested OK.", "INFO")
    return 0


# ------------------------------------------------------------------------- main

def _parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="ni-ingest",
        description=(
            "Ingest Nuclear Imaging (NI) acquisitions. Point at one extracted "
            "acquisition folder or a batch root of them. Archive mode (extract "
            ".tgz first with tools/extract_ni_archives.py); live mode pending "
            "the molecubes_ni_live.yaml layout."
        ),
    )
    parser.add_argument(
        "folder",
        help="Path to one extracted NI acquisition, or a batch root of them.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview only -- show the table and exit (never prompts, never "
             "commits). The default already previews then prompts; --dry-run "
             "is the no-prompt, no-commit variant.",
    )
    parser.add_argument(
        "--go", action="store_true",
        help="Skip the confirmation prompt and commit the ingest.",
    )
    parser.add_argument(
        "--nas-root", default=None,
        help="NAS root (must contain a registries/ subdir). Defaults to "
             "$GJESUS3_ROOT, then /mnt/gjesus3.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    # UTF-8 stdout for the preview table (link names are ASCII today, but stay
    # defensive); ignore if the platform's stdout can't be reconfigured.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001 -- best-effort, never fatal
        pass

    path = args.folder

    # 1) Validate the NAS root up front (one clear message, not a phantom path).
    try:
        nas_root = env.require_nas_root(args.nas_root)
    except env.NasRootError as e:
        log(str(e), "ERROR")
        return 2

    # 2) Archive (.tgz) inputs: explain + offer to extract, then stop.
    if _looks_like_tgz(path) or _dir_has_tgz_children(path):
        return _explain_archive_and_maybe_extract(path, assume_yes=args.go)

    # 3) Resolve the scope (single acquisition vs batch root). On a ScopeError,
    #    fall back to the live-mode message if the folder still looks like raw
    #    NI output (don't guess a live layout); otherwise re-surface the scope
    #    error verbatim.
    try:
        staging_dir, pattern = scope.resolve_scope(INSTRUMENT_KEY, path)
    except scope.ScopeError as e:
        if os.path.isdir(path) and _looks_like_live_acquisition(path):
            return _explain_live_mode(path)
        log(str(e), "ERROR")
        return 3
    except KeyError as e:  # unknown instrument key -- shouldn't happen (hardcoded)
        log(str(e), "ERROR")
        return 3

    log(f"scope: staging_dir={staging_dir!r}, pattern={pattern!r}", "INFO")

    # 4) Build the in-memory config from the NI template + scope overrides.
    cfg = _build_cfg(staging_dir, pattern)

    # 5) Read-only preview (the real acq_id / project / link, not the dry-run).
    log("building preview (read-only)...", "INFO")
    result = preview.preview_batch(cfg, nas_root)

    if result.blocking_errors:
        for err in result.blocking_errors:
            log(err, "ERROR")
        return 4

    if not result.cases:
        log(
            "no new NI acquisitions to ingest in that folder (everything "
            "matched is already in the registry, or nothing matched this "
            "instrument's naming).", "WARN",
        )
        _print_preview_table(result)
        return 0

    _print_preview_table(result)

    # 6) Decide whether to commit.
    if args.dry_run:
        log("--dry-run: nothing was written.", "INFO")
        return 0

    if not args.go:
        try:
            answer = input("Proceed? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer not in ("y", "yes"):
            log("aborted; nothing was written.", "INFO")
            return 0

    # 7) Commit through the validated pipeline.
    log("committing ingest...", "INFO")
    return _commit(cfg, nas_root)


def cli():
    """Console-entry-point shim (the `ni-ingest` script)."""
    raise SystemExit(main())


if __name__ == "__main__":
    cli()
