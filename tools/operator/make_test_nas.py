#!/usr/bin/env python3
r"""make_test_nas.py -- build a throwaway "test NAS root" for operator-tool testing.

The operator front-ends (ni-ingest / mri-ingest / microscopy GUI) and the data-
office `ingest_raw.py` all WRITE into a NAS root: raw/ files, project hard links,
and appended registry rows. To rehearse a *real commit* (not just a dry-run)
without dirtying the live registry, point the tools at a throwaway NAS root that
you can inspect and `rm -rf` freely. This builds one.

What it creates under <dest>:

    raw/  projects/  staging/  publications/  curated_datasets/  tmp/
    registries/
        registry_raw.csv         <- HEADER ONLY (copied from the source NAS), so
                                     every acquisition you point at is "new" and
                                     a full commit is exercised end-to-end.
        ingest_manifest.csv      <- HEADER ONLY (copied from the source NAS).
        registry_projects.csv    <- FULL COPY of the source NAS's projects, so a
                                     project_hint like "ae-biomegune-0424"
                                     resolves to the real PROJ-XXXX (mirrors the
                                     exhibition projects). Templates also have
                                     auto_create_projects:true, so a hint with no
                                     match still auto-creates -- either path works.

Copying the HEADERS from the live registries (rather than hard-coding them)
guarantees the scratch schema matches the live schema exactly -- important
because registry.append_row has a defensive header check that aborts on a
mismatch.

Usage (Git Bash / PowerShell / WSL -- pure stdlib, cross-platform):

    python tools/operator/make_test_nas.py --dest C:\Users\<you>\temp\testnas
    # then point any front-end at it:
    python tools/operator/mri_ingest.py D:\...\study --nas-root C:\Users\<you>\temp\testnas --dry-run

By default the source NAS (where headers + projects are copied from) is
J:\gjesus3-data; override with --src-nas. Refuses to overwrite a non-empty
<dest> unless you pass --force (so you never nuke real data by a typo).
"""

import argparse
import os
import shutil
import sys

# The standard top-level folders a NAS root carries (mirrors the live layout).
_NAS_SUBDIRS = (
    "raw",
    "projects",
    "staging",
    "publications",
    "curated_datasets",
    "tmp",
    "registries",
)

# Registries that should be reset to HEADER ONLY (so everything is "new").
_HEADER_ONLY = ("registry_raw.csv", "ingest_manifest.csv")
# Registries copied WHOLE (so project_hints resolve to the real PROJ-XXXX).
_COPY_WHOLE = ("registry_projects.csv",)


def _copy_header_only(src_csv, dest_csv):
    """Write only the first line (the header) of src_csv into dest_csv.

    Tolerant decode mirrors registry.read_registry (live CSVs are cp1252-ish):
    try utf-8-sig, fall back to latin-1 so a stray non-ASCII byte never aborts.
    """
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            with open(src_csv, "r", encoding=encoding, newline="") as fh:
                header = fh.readline()
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover -- latin-1 decodes any byte, so this is unreachable
        raise RuntimeError(f"could not decode {src_csv!r}")
    # Write back as UTF-8 (no BOM); the pipeline reads tolerantly either way.
    with open(dest_csv, "w", encoding="utf-8", newline="") as fh:
        fh.write(header if header.endswith("\n") else header + "\n")


def _is_nonempty_dir(path):
    return os.path.isdir(path) and any(os.scandir(path))


def build_test_nas(dest, src_nas, force=False):
    """Create the throwaway NAS root at `dest`, seeded from `src_nas`."""
    src_registries = os.path.join(src_nas, "registries")
    if not os.path.isdir(src_registries):
        raise SystemExit(
            f"source NAS has no registries/ dir: {src_registries!r}. "
            f"Pass --src-nas pointing at a real NAS root (e.g. J:\\gjesus3-data)."
        )

    if _is_nonempty_dir(dest) and not force:
        raise SystemExit(
            f"refusing to write into non-empty {dest!r} without --force "
            f"(so a typo never clobbers real data). Delete it first, pick an "
            f"empty path, or pass --force to reset it."
        )

    # On --force, wipe the DATA dirs (raw/projects/staging/...) too, not just
    # the registries. Otherwise a rebuild leaves orphaned raw files + project
    # link folders from a prior test run on disk, out of sync with the now-empty
    # registry (e.g. a raw_linked/<acq> folder for an acquisition that is no
    # longer in registry_raw) -- which looks like a phantom extra acquisition.
    if force:
        for sub in _NAS_SUBDIRS:
            if sub == "registries":
                continue  # recreated + reseeded below
            data_dir = os.path.join(dest, sub)
            if os.path.isdir(data_dir):
                shutil.rmtree(data_dir, ignore_errors=True)

    for sub in _NAS_SUBDIRS:
        os.makedirs(os.path.join(dest, sub), exist_ok=True)

    dest_registries = os.path.join(dest, "registries")

    for name in _HEADER_ONLY:
        src_csv = os.path.join(src_registries, name)
        if not os.path.isfile(src_csv):
            raise SystemExit(
                f"source registry missing: {src_csv!r}. Is --src-nas a real "
                f"NAS root?"
            )
        _copy_header_only(src_csv, os.path.join(dest_registries, name))

    for name in _COPY_WHOLE:
        src_csv = os.path.join(src_registries, name)
        if os.path.isfile(src_csv):
            shutil.copyfile(src_csv, os.path.join(dest_registries, name))
        else:
            # No projects registry on the source -- header-only fallback so the
            # NAS still validates; templates auto-create projects anyway.
            print(
                f"  - note: {name} not found on source; the test NAS will rely "
                f"on auto_create_projects."
            )

    return dest


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="make_test_nas",
        description=(
            "Build a throwaway 'test NAS root' (empty raw/registry, real "
            "projects) so operator-tool commits can be rehearsed without "
            "touching the live registry. Inspect it, then rm -rf it."
        ),
    )
    p.add_argument(
        "--dest", required=True,
        help="Where to build the test NAS root (a throwaway dir you can delete).",
    )
    p.add_argument(
        "--src-nas", default=r"J:\gjesus3-data",
        help="Real NAS root to copy registry headers + projects from "
             "(default: J:\\gjesus3-data).",
    )
    p.add_argument(
        "--force", action="store_true",
        help="Reset an existing test NAS: wipe the data dirs "
             "(raw/projects/staging/...) AND reset the registries to a clean "
             "slate. Required when --dest is a non-empty directory.",
    )
    args = p.parse_args(argv)

    dest = build_test_nas(args.dest, args.src_nas, force=args.force)

    print(f"Test NAS root ready: {dest}")
    print("  registry_raw.csv      : header only (every acq is 'new')")
    print("  ingest_manifest.csv   : header only")
    print("  registry_projects.csv : copied from the source NAS")
    print()
    print("Point a front-end at it, e.g.:")
    if os.name == "nt":
        print(f'  $env:GJESUS3_ROOT = "{dest}"')
    else:
        print(f'  export GJESUS3_ROOT="{dest}"')
    print("  python tools/operator/mri_ingest.py <study> --dry-run")
    print("  python tools/operator/mri_ingest.py <study> --go   # real commit, isolated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
