#!/usr/bin/env python3
"""mri-ingest — operator-facing MRI (Bruker ParaVision) ingest front-end.

Phase 3 of `tasks/operator_ingest_tooling_plan.md`. A dead-simple "point at the
study folder and go" wrapper around the validated ingest pipeline: the operator
never writes YAML. The script hardcodes the MRI instrument key (-> the locked
`mri_bruker.yaml` template), auto-detects the scope (single exam / study folder /
batch root), applies the two per-run knobs (reconstructions + scanner model),
previews what will happen, then commits via the same `ingest_raw.run_batch` the
data office uses. No ingest logic is reimplemented here.

Usage:
    mri-ingest /path/to/study
    mri-ingest /path/to/study --reconstructions 3 --model 7T
    mri-ingest /path/to/study --dry-run
    mri-ingest /path/to/study --go            # skip the confirm prompt
    mri-ingest /path/to/study --ftp-remote /opt/PV-7.0.0/data/nmr/<study>

Scope (auto-detected by scope.resolve_scope("MRI", path)):
    - point at ONE ParaVision exam folder (has acqp + method)  -> that exam only
    - point at a STUDY folder (children are exams)             -> all its exams
    - point at a BATCH ROOT (grandchildren are exams)          -> all studies

Per-run knobs (the ONLY things the operator changes; everything else is locked
in the template):
    --reconstructions all|3|1,3   which pdata/<idx>/ recons' DICOMs to copy.
                                   Default: template default ('all'). Unselected
                                   recons still get their JCAMP-DX preserved.
    --model 7T|11.7T              which BioSpec scanner produced the batch.
                                   Sets registry instrument_model. Default: leave
                                   the template placeholder (you'll see a warning
                                   in the preview if you skipped it).

FTP (fetch and ingest stay decoupled — same model as tools/ftp_mirror.py):
    Default: the path is assumed already-local (FTP already pulled, or a mounted
    console share). No network access.
    --ftp-remote /remote/path: open a paramiko SFTP using GJESUS3_FTP_* env creds,
    mirror /remote/path into a local staging dir, THEN run the normal
    preview/commit against that local copy. The positional path is then the local
    staging directory the mirror writes into.

NAS root: --nas-root, else $GJESUS3_ROOT, else /mnt/gjesus3. Validated up front
(must contain a registries/ subdir) so the operator gets one clear message
instead of a silent phantom-path write.
"""

import argparse
import importlib.util
import os
import sys
from datetime import datetime

# --- Load the shared operator core under its non-colliding alias -------------
#
# This package's directory is named `operator`, which collides with the stdlib
# `operator` module, so it ships no importable top-level `__init__.py` and must
# be loaded via _loader.py (see tools/operator/IMPORT_CONTRACT.md). A standalone
# `python mri_ingest.py` has no package context for relative imports, so we use
# the documented spec-based loader form.
_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "gj_operator_loader", os.path.join(_HERE, "_loader.py")
)
_l = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_l)
_op = _l.load()  # the package, aliased as gj_op_core

templates = _op.templates
config_builder = _op.config_builder
scope = _op.scope
preview = _op.preview
runner = _op.runner
env = _op.env
metadata_prompt = _op.metadata_prompt

INSTRUMENT_KEY = "MRI"

# --model -> registry instrument_model. The template carries the
# "Bruker BioSpec <7T|11.7T>" placeholder; these are the two real values.
_MODEL_MAP = {
    "7T": "Bruker BioSpec 7T",
    "11.7T": "Bruker BioSpec 11.7T",
}


# ------------------------------------------------------------------ logging

def log(msg, level="INFO"):
    """Stderr log line: [HH:MM:SS] LEVEL: msg. ASCII-only text."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}", file=sys.stderr)


def _reconfigure_stdout():
    """Best-effort UTF-8 stdout so the preview table renders cleanly."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001 — pre-3.7 / already-wrapped streams
        pass


# ------------------------------------------------------------ recon parsing

def parse_reconstructions(raw):
    """Map the --reconstructions CLI string to a config value.

    'all' / '' / None -> 'all' (template default semantics).
    '3'               -> [3]
    '1,3'             -> [1, 3]

    Returns the value to set at ingest.reconstructions, or None to leave the
    template default in place (when the flag was not given).
    """
    if raw is None:
        return None  # flag not given -> don't override the template
    s = raw.strip().lower()
    if s in ("", "all"):
        return "all"
    parts = [p.strip() for p in s.split(",") if p.strip()]
    try:
        return [int(p) for p in parts]
    except ValueError:
        raise ValueError(
            f"invalid --reconstructions value {raw!r}; expected 'all', a single "
            f"index (e.g. '3'), or a comma list (e.g. '1,3')."
        )


# ------------------------------------------------------------------ FTP pull

def ftp_pull(remote_root, local_root, dry_run=False):
    """Mirror remote_root -> local_root over a paramiko SFTP using env creds.

    Decoupled from ingest (the same model as tools/ftp_mirror.py): this only
    fetches; the caller then runs the normal preview/commit against local_root.

    Returns local_root on success. Raises on missing paramiko / creds / a
    transport failure.
    """
    try:
        import paramiko
    except ImportError:
        raise RuntimeError(
            "paramiko is not installed but --ftp-remote was given. "
            "Install it (pip install paramiko) or pull the study manually and "
            "point mri-ingest at the local copy."
        )

    if not env.ftp_creds_present():
        raise RuntimeError(
            "FTP credentials are not set. --ftp-remote needs GJESUS3_FTP_HOST, "
            "GJESUS3_FTP_USER and GJESUS3_FTP_PASSWORD in the environment "
            "(GJESUS3_FTP_PORT optional, defaults to 22)."
        )

    # Reuse the validated mirror helper against an already-opened SFTP.
    from ftp_mirror import mirror as ftp_mirror_fn

    creds = env.ftp_creds()
    log(f"Connecting: sftp://{creds['user']}@{creds['host']}:{creds['port']}")
    transport = paramiko.Transport((creds["host"], creds["port"]))
    try:
        transport.connect(username=creds["user"], password=creds["password"])
        sftp = paramiko.SFTPClient.from_transport(transport)

        if not dry_run:
            os.makedirs(local_root, exist_ok=True)

        log(f"Mirroring {remote_root} -> {local_root}")
        n_xfer, n_skip, n_bytes = ftp_mirror_fn(
            sftp, remote_root, local_root, dry_run=dry_run, force=False
        )
        action = "would transfer" if dry_run else "transferred"
        log(
            f"FTP {action} {n_xfer} files ({n_bytes / 1_000_000:.1f} MB); "
            f"skipped {n_skip} already-present"
        )
    finally:
        transport.close()

    return local_root


# ------------------------------------------------------------ preview table

def _truncate(s, width):
    s = str(s)
    if len(s) <= width:
        return s
    if width <= 1:
        return s[:width]
    return s[: width - 1] + "…"  # ellipsis


def print_preview_table(result):
    """Print the operator-facing preview table to stdout (UTF-8).

    Columns: acq_id, sample_id, project, link name, n_files (recon DICOM count
    summed across selected recons), warnings count. The aggregate line shows
    new vs already-ingested.
    """
    cols = [
        ("ACQ-ID", 26),
        ("SAMPLE", 22),
        ("PROJECT", 22),
        ("LINK NAME", 38),
        ("EXAM", 6),
        ("RECON", 8),
    ]
    header = "  ".join(name.ljust(w) for name, w in cols)
    print(header)
    print("  ".join("-" * w for _, w in cols))

    for c in result.cases:
        reg = c.registry_resolved or {}
        disco = c.discovered or {}
        sample = reg.get("sample_id") or disco.get("jrc_id") or ""
        exam = disco.get("mri_exam_number") or disco.get("folder_name") or ""
        recon = disco.get("mri_recon_indices") or ""
        row = [
            (_truncate(c.acq_id_preview, cols[0][1]), cols[0][1]),
            (_truncate(sample, cols[1][1]), cols[1][1]),
            (_truncate(c.project_preview, cols[2][1]), cols[2][1]),
            (_truncate(c.link_filename_preview, cols[3][1]), cols[3][1]),
            (_truncate(exam, cols[4][1]), cols[4][1]),
            (_truncate(recon, cols[5][1]), cols[5][1]),
        ]
        print("  ".join(val.ljust(w) for val, w in row))
        for w in c.warnings:
            print(f"    ! {w}")

    print()
    summary = (
        f"{result.n_new} acquisition(s) would be ingested"
    )
    if result.n_skipped:
        # Skipped = glob matches that did not become acquisitions: either
        # already in the registry (idempotent re-run) OR non-exam siblings
        # (AdjResult / NIFTI / subject / etc.) that fail the ParaVision
        # detector. The per-line "Batch notes / skips" below say which.
        summary += (
            f"; {result.n_skipped} match(es) skipped "
            f"(already-ingested or non-exam siblings)"
        )
    if result.n_matched:
        summary += f"; {result.n_matched} glob match(es) scanned"
    print(summary)

    if result.warnings:
        print()
        print("Batch notes / skips:")
        for w in result.warnings:
            print(f"  - {w}")


# ------------------------------------------------------------ build config

def build_mri_config(staging_dir, pattern, reconstructions=None, model=None,
                     extra_overrides=None):
    """Load the MRI template and apply the per-run overrides.

    Args:
        staging_dir: resolved staging directory (from scope.resolve_scope).
        pattern: resolved glob pattern.
        reconstructions: parsed value (str 'all' | list[int]) or None to keep
            the template default.
        model: '7T' | '11.7T' or None to keep the template placeholder.
        extra_overrides: optional flat dict of additional config_builder
            overrides (e.g. condition.*/anatomy.* from metadata_prompt).

    Returns:
        (cfg, template_path) — cfg is the in-memory config dict; template_path
        is stamped into the registry ingest_config column by the runner.
    """
    template_path = templates.template_path(INSTRUMENT_KEY)
    template = templates.load_template(INSTRUMENT_KEY)

    overrides = {
        "auto_discover.staging_dir": staging_dir,
        "auto_discover.pattern": pattern,
    }
    if reconstructions is not None:
        overrides["ingest.reconstructions"] = reconstructions
    if model is not None:
        if model not in _MODEL_MAP:
            raise ValueError(
                f"unknown --model {model!r}; expected one of "
                f"{sorted(_MODEL_MAP)}."
            )
        overrides["registry.instrument_model"] = _MODEL_MAP[model]
    if extra_overrides:
        overrides.update(extra_overrides)

    cfg = config_builder.build_config(template, overrides)
    return cfg, template_path


# ------------------------------------------------------------------ main

def main(argv=None):
    _reconfigure_stdout()

    p = argparse.ArgumentParser(
        prog="mri-ingest",
        description=(
            "Ingest Bruker ParaVision MRI data into gjesus3. Point at a single "
            "exam, a study folder, or a batch root; preview, then commit."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Scope is auto-detected. The only per-run knobs are "
            "--reconstructions and --model; every other convention is locked in "
            "the mri_bruker template.\n\n"
            "FTP: with --ftp-remote, the study is first SFTP-mirrored "
            "(GJESUS3_FTP_* env creds) into the local path you passed, then "
            "ingested from there."
        ),
    )
    p.add_argument(
        "path",
        help="Path to a ParaVision exam, a study folder, or a batch root "
             "(the directory holding the FTP-pulled study folders). With "
             "--ftp-remote, this is the LOCAL staging directory the remote "
             "tree is mirrored into.",
    )
    p.add_argument(
        "--reconstructions", "--recons", dest="reconstructions", default=None,
        help="Which pdata/<idx>/ recons' DICOMs to copy: 'all', a single index "
             "(e.g. '3'), or a comma list (e.g. '1,3'). Default: the template "
             "default ('all'). Unselected recons still keep their JCAMP-DX.",
    )
    p.add_argument(
        "--model", default=None, choices=sorted(_MODEL_MAP),
        help="Which BioSpec scanner produced this batch (sets the registry "
             "instrument_model). Default: leave the template placeholder.",
    )
    p.add_argument(
        "--ftp-remote", dest="ftp_remote", default=None,
        help="Remote SFTP path to mirror into the local staging dir before "
             "ingest (creds via GJESUS3_FTP_* env). Omit to ingest an "
             "already-local path.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Preview only; make no changes (and do not commit). Implies the "
             "preview table is shown and nothing is written.",
    )
    p.add_argument(
        "--go", action="store_true",
        help="Skip the 'Proceed? [y/N]' confirmation and commit straight after "
             "the preview.",
    )
    p.add_argument(
        "--nas-root", dest="nas_root", default=None,
        help="NAS root (must contain a registries/ subdir). Default: "
             "$GJESUS3_ROOT, else /mnt/gjesus3.",
    )
    # Operator condition/anatomy metadata (08_METADATA). Omitted flags are
    # prompted for interactively (unless --no-prompt / no TTY). All optional +
    # non-blocking; the values apply to every exam in the run.
    p.add_argument(
        "--is-control", type=metadata_prompt.cli_bool, default=None,
        metavar="true|false",
        help="condition.is_control: true=control (no disease model / "
             "perturbation / intervention), false=case. Omit to be prompted.",
    )
    p.add_argument(
        "--disease-model", dest="disease_model", default=None,
        help="condition.disease_model (free text). Only asked/used for a case "
             "(--is-control false).",
    )
    p.add_argument(
        "--disease-state", dest="disease_state", default=None,
        help="condition.disease_state (free text). Only asked/used for a case.",
    )
    p.add_argument(
        "--is-whole-body", type=metadata_prompt.cli_bool, default=None,
        metavar="true|false",
        help="anatomy.is_whole_body: true=whole-body, false=region of interest "
             "(set the UBERON region later in the per-acq metadata file).",
    )
    p.add_argument(
        "--no-prompt", action="store_true",
        help="Never prompt for condition/anatomy metadata; use only the flags "
             "given (leaves the rest unset / non-blocking).",
    )
    args = p.parse_args(argv)

    # --- NAS root (validate first; fail fast with a plain message) ----------
    try:
        nas_root = env.require_nas_root(args.nas_root)
    except env.NasRootError as e:
        log(str(e), "ERROR")
        return 2
    log(f"NAS root: {nas_root}")

    # --- recon parse (fail fast on a bad string) ----------------------------
    try:
        reconstructions = parse_reconstructions(args.reconstructions)
    except ValueError as e:
        log(str(e), "ERROR")
        return 2

    # --- FTP pull (optional, decoupled) -------------------------------------
    # The mirror writes into the positional path, which becomes the local
    # staging directory the scope detector then runs against.
    local_path = args.path
    if args.ftp_remote:
        try:
            ftp_pull(args.ftp_remote, local_path, dry_run=args.dry_run)
        except Exception as e:  # noqa: BLE001 — surface as a clean operator error
            log(str(e), "ERROR")
            return 2
        if args.dry_run:
            # In dry-run nothing was actually fetched; the local tree may not
            # exist yet, so we can't scope it. Tell the operator and stop.
            log(
                "--dry-run with --ftp-remote previews the FTP transfer only; "
                "the study was NOT fetched, so the ingest preview is skipped. "
                "Re-run without --dry-run (or fetch first) to preview the "
                "ingest.",
                "INFO",
            )
            return 0

    # --- scope (point-at-folder -> staging_dir + pattern) -------------------
    try:
        staging_dir, pattern = scope.resolve_scope(INSTRUMENT_KEY, local_path)
    except scope.ScopeError as e:
        log(str(e), "ERROR")
        return 2
    log(f"Scope: staging_dir={staging_dir} pattern={pattern!r}")

    # --- operator condition/anatomy metadata (CLI flags + optional prompts) -
    # is_batch -> the scope pattern carries a wildcard (a study '<study>/*' or
    # batch root '*/*'); a single exam is a literal '<study>/<exam>'.
    # Non-blocking: skipped values keep the template's null sentinels.
    is_batch = "*" in pattern
    interactive = (not args.no_prompt) and sys.stdin.isatty()
    meta_overrides = metadata_prompt.collect_overrides(
        {
            "is_control": args.is_control,
            "disease_model": args.disease_model,
            "disease_state": args.disease_state,
            "is_whole_body": args.is_whole_body,
        },
        is_batch=is_batch, interactive=interactive,
    )
    meta_summary = metadata_prompt.describe(meta_overrides)
    if meta_summary:
        log(f"Metadata: {meta_summary}")

    # --- build the in-memory config -----------------------------------------
    try:
        cfg, template_path = build_mri_config(
            staging_dir, pattern,
            reconstructions=reconstructions, model=args.model,
            extra_overrides=meta_overrides,
        )
    except ValueError as e:
        log(str(e), "ERROR")
        return 2

    recon_desc = (
        "template default ('all')" if reconstructions is None
        else reconstructions
    )
    log(f"Reconstructions: {recon_desc}")
    if args.model:
        log(f"Scanner model: {_MODEL_MAP[args.model]}")
    else:
        log(
            "Scanner model not given (--model); the registry instrument_model "
            "will keep the template placeholder. Pass --model 7T or "
            "--model 11.7T to record the real scanner.",
            "WARN",
        )

    # --- preview (read-only) ------------------------------------------------
    log("Building preview (read-only)...")
    try:
        result = preview.preview_batch(cfg, nas_root)
    except Exception as e:  # noqa: BLE001 — preview should never abort the tool
        log(f"preview failed: {e}", "ERROR")
        return 2

    print()
    print_preview_table(result)
    print()

    if result.blocking_errors:
        log("Cannot proceed - the config has blocking errors:", "ERROR")
        for be in result.blocking_errors:
            log(f"  {be}", "ERROR")
        return 1

    if result.n_new == 0:
        log(
            "Nothing new to ingest (everything in scope is already in the "
            "registry, or no files matched). Safe to stop.",
            "INFO",
        )
        return 0

    # --- dry-run stops here -------------------------------------------------
    if args.dry_run:
        log("--dry-run: previewed only, nothing was written.", "INFO")
        return 0

    # --- confirm + commit ---------------------------------------------------
    if not args.go:
        try:
            answer = input(f"Proceed with ingest of {result.n_new} "
                           f"acquisition(s)? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            log("Aborted (no confirmation).", "INFO")
            return 1
        if answer not in ("y", "yes"):
            log("Aborted by operator.", "INFO")
            return 1

    recipe_path = runner.default_recipe_path(template_path)
    log(f"Committing... (ingest_config -> {recipe_path})")
    outcomes = runner.run(
        cfg, nas_root,
        dry_run=False,
        log_callback=log,
        recipe_path=recipe_path,
    )

    n_ok = sum(1 for _acq, ok in outcomes if ok)
    n_fail = len(outcomes) - n_ok
    if n_fail:
        log(f"Done with errors: {n_ok} ok, {n_fail} failed.", "ERROR")
        return 1
    log(f"Done: {n_ok} acquisition(s) ingested.", "INFO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
