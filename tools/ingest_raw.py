#!/usr/bin/env python3
"""ingest_raw.py — Ingest raw data from staging into the structured raw area.

Usage:
    python ingest_raw.py --config batch.yaml --dry-run   # preview
    python ingest_raw.py --config batch.yaml              # execute
    python ingest_raw.py --interactive                     # single case

See 10_TOOLS.md and 03_RAW_STORAGE.md for full specification.
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from ingest import (
    config, acq_id, checksum, registry, readme, dicom_utils, linker,
    metadata_sidecar, provenance, resolver, enrichment, locking,
    subjects_table,
)
import create_project as create_project_mod
import animal_db


def relative_config_path(config_path):
    """Return config_path as a forward-slash path relative to the git repo root.

    Falls back to a CWD-relative path if not in a git repo, and to the absolute
    path if even that is impossible. On Windows, os.path.relpath raises
    ValueError when the two paths live on different drives (e.g. a batch config
    on D: while the repo/CWD is on C:) — guard against it so a cross-drive
    --config doesn't abort the whole ingest over a cosmetic provenance string.
    """
    if not config_path:
        return ""
    abs_path = os.path.abspath(config_path)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
            cwd=os.path.dirname(abs_path) or ".",
        )
        repo_root = result.stdout.strip()
        if repo_root:
            try:
                return os.path.relpath(abs_path, repo_root).replace("\\", "/")
            except ValueError:
                # config on a different Windows drive than the repo — a
                # relative path is impossible; record the absolute path.
                return abs_path.replace("\\", "/")
    except Exception:
        pass
    try:
        return os.path.relpath(abs_path).replace("\\", "/")
    except ValueError:
        # On Windows, os.path.relpath raises ValueError when abs_path and the
        # CWD are on different drives (e.g. config on J:, repo/CWD on C:).
        # A non-relative ingest_config value is fine; a crash before any
        # ingest is not. Fall back to the absolute forward-slash path.
        return abs_path.replace("\\", "/")

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


def log(msg, level="INFO"):
    """Print a timestamped log message."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}")


def _copy_to_nas(src, dst):
    """Copy one file to the NAS, tolerant of CIFS/SMB mounts that reject
    timestamp/mode preservation.

    From WSL the NAS is a CIFS mount (`/mnt/gjesus3`), and such mounts commonly
    disallow `os.utime` (and sometimes `os.chmod`). `shutil.copy2` copies the
    bytes and THEN calls `copystat`, so it raises in `copystat` *after* the data
    is already written — crashing the ingest mid-copy (an `OSError`, seen as the
    WSL→NAS `copy2`/`utime` blocker). We instead copy the bytes with
    `copyfile` (which touches no metadata, so it cannot fail on a CIFS mount)
    and then preserve timestamps/mode **best-effort**, swallowing the mount's
    rejection. Integrity is guaranteed by the sha256 verify, not by timestamps.
    On native Windows / a local FS `copystat` succeeds, so behaviour is
    unchanged there.
    """
    shutil.copyfile(src, dst)
    try:
        shutil.copystat(src, dst)
    except OSError:
        pass  # CIFS mount disallows utime/chmod — timestamps not preserved, fine
    return dst


def copy_files(src_dir, dst_dir):
    """Copy all files from src_dir into dst_dir, preserving subdirectory structure.

    Returns number of files copied.
    """
    count = 0
    all_files = []
    for root, _dirs, files in os.walk(src_dir):
        for fname in files:
            src_path = os.path.join(root, fname)
            rel = os.path.relpath(src_path, src_dir)
            all_files.append((src_path, rel))

    if HAS_TQDM:
        iterator = tqdm(all_files, desc="Copying", unit="file")
    else:
        iterator = all_files

    for src_path, rel in iterator:
        dst_path = os.path.join(dst_dir, rel)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        _copy_to_nas(src_path, dst_path)
        count += 1

    return count


def _rollback_uncommitted(dest_dir, log_fn=log):
    """Remove a partially-written acquisition folder after a pre-commit failure.

    The registry append is the ingest commit point (F item 5). If an exception
    fires after the raw folder is created but before its registry row is
    written, the folder is an orphan the dedup index can't see — a re-run would
    copy it again under a fresh ACQ-ID. Remove it so a re-run starts clean.
    Best-effort: a failure to roll back is logged, never raised.
    """
    try:
        if dest_dir and os.path.isdir(dest_dir):
            shutil.rmtree(dest_dir)
            log_fn(
                f"Rolled back partial acquisition folder (no registry row "
                f"written): {dest_dir}",
                "WARN",
            )
    except Exception as e:
        log_fn(f"Could not roll back {dest_dir}: {e}", "WARN")


def _normalize_reconstructions(value):
    """Normalise the YAML `reconstructions:` value to a set of index strings
    or None (== keep all).

    Accepts: "all" (case-insensitive), a single int, a single str like "3",
    or a list of ints/strings (e.g. [3] or ["1", "3"]).
    """
    if value is None or value == "":
        return None
    if isinstance(value, str) and value.lower() == "all":
        return None
    if isinstance(value, (int, str)):
        return {str(value).strip()}
    if isinstance(value, list):
        return {str(v).strip() for v in value if v != "" and v is not None}
    return None


def _resolve_archive_primary(cfg_single, ingest_block):
    """Locate the source archive file to store as an `acquisition_layout: archive` primary.

    `ingest.archive_primary_from` is the directory holding the original
    collaborator archives; the case's `discovered.folder_name` (falling back
    to the source basename) plus any archive extension identifies the file
    (e.g. case "LEONE_1.01" -> "<dir>/LEONE_1.01.zip"; "HPIC02" ->
    "<dir>/HPIC02.rar"). Raises RuntimeError if the directory is unset or no
    matching archive is found.
    """
    src_dir = ingest_block.get("archive_primary_from")
    if not src_dir:
        raise RuntimeError(
            "acquisition_layout: archive requires ingest.archive_primary_from "
            "(directory holding the source archive files)."
        )
    discovered = cfg_single.get("discovered") or {}
    case = discovered.get("folder_name") or Path(cfg_single["source_path"]).name
    # Compound extensions (.tar.gz) are listed before their single-suffix
    # tails (.gz) so a name like "LEONE_1.tar.gz" matches as case "LEONE_1"
    # rather than being mis-split by os.path.splitext into stem "LEONE_1.tar".
    archive_exts = (".tar.gz", ".tgz", ".zip", ".rar", ".7z", ".tar", ".gz")
    for fname in sorted(os.listdir(src_dir)):
        lower = fname.lower()
        for ext in archive_exts:
            # Match the extension case-insensitively; the stem (everything
            # before it) must equal the case name exactly.
            if lower.endswith(ext) and fname[: len(fname) - len(ext)] == case:
                return os.path.join(src_dir, fname)
    raise RuntimeError(
        f"No source archive found for case {case!r} under {src_dir!r} "
        f"(looked for {case}.<{'/'.join(e.lstrip('.') for e in archive_exts)}>)."
    )


def copy_ni_acquisition(source_path, dest_dir, acq_id_str, log_fn):
    """Folder-as-primary copy for a Molecubes Nuclear Imaging acquisition.

    SLIM copy (round-8 v2, 2026-05-27): only the reconstructed DICOMs
    land on gjesus3, in a flat `<ACQ-ID>.data/` subfolder. All other
    files — raw event data, calibration, operational logs, AND the
    acquisition-level aux files (protocol.txt / XML / acquisition.log) —
    stay on the Molecubes platform archive (`\\\\cicmgsp02\\gnuclear2$`).
    The parsed contents of the aux files are preserved in
    `metadata.json.ni._raw_metadata`, so nothing meaningful is lost;
    the on-disk acq folder mirrors microscopy's one-file-per-acquisition
    convention (`<ACQ-ID>.czi`) as closely as a multi-DICOM
    reconstruction allows.

    Destination layout:

      <dest_dir>/                          (e.g. ACQ-20251029-CT-001/)
        metadata.json                       (written by caller after this)
        checksums.json                      (written by caller after this)
        README.txt                          (written by caller after this)
        <ACQ-ID>.data/                      (THIS function creates + populates)
          recon0.dcm                          (CT, no frame subdirs)
          recon1.dcm
          recon2.dcm
          recon0_frame0.dcm                   (PET/SPECT static)
          recon0_frame1.dcm, recon0_frame2.dcm  (PET dynamic)

    File-name mapping (computed by ni_metadata._plan_dcm_target):
      - Direct under recon_<X>/<basename>.dcm  → recon<X>.dcm  (CT path)
      - Under recon_<X>/frame_<Y>/iter_<N>/<basename>.dcm → recon<X>_frame<Y>.dcm
      - Filename contains "frameMULTI" → SKIPPED (platform-generated
        bundled DICOM whose metadata is not yet validated; per-frame
        DICOMs are used instead; existence is recorded in the sidecar
        under ni.reconstruction.by_index.<idx>.multi_frame_dicoms_on_platform).

    Everything else from the source is dropped (NOT copied to gjesus3):
      acq-root: protocol.txt/xml, acqparams.xml, recontemplate.xml,
        acquisition.log, data.raw, bright.raw, dark.raw, badpixels.map,
        attmap.amap, eventdata_*, singles.stat, spectrum.bin,
        monitoring.csv, sequence.csv, xrayserver.log, ACQSTATUS,
        DOWNLOADED, REMIDOWNLOADED, calibrationParameters.xml,
        reconstructionParameters*.xml, registration.matrix, recon.ini
      per-recon: .img, RECONSTATUS, preview.res, *.bin, *.stat,
        reconparams.txt/xml (parsed contents already in metadata.json),
        reconstruction.log, recon.ini, ATTMAP variants, scatter binaries

    Returns a dict mapping `<dst_relative_path> -> sha256` for the
    checksums.json file. Raises RuntimeError on hash mismatch or empty plan.
    """
    from ingest import ni_metadata

    src = Path(source_path)
    md = ni_metadata.load_ni_acquisition(src)
    data_dirname = f"{acq_id_str}.data"

    # Build the (src_file, dst_relpath) plan from the load_ni_acquisition
    # result. Each .dcm has its already-planned dst_basename; everything
    # else is dropped.
    plan = []
    recon_indices = []
    n_skipped_multi = 0
    n_unrecognized = 0
    for idx in sorted(
        md.get("recons", {}).keys(),
        key=lambda x: int(x) if x.isdigit() else x,
    ):
        recon_indices.append(idx)
        r = md["recons"][idx]
        for d in r.get("dicoms") or []:
            src_file = src / d["src_relpath"]
            dst_rel = os.path.join(data_dirname, d["dst_basename"])
            plan.append((src_file, dst_rel))
        n_skipped_multi += len(r.get("multi_frame_dicoms") or [])
        n_unrecognized += len(r.get("unrecognized_dicoms") or [])

    if not recon_indices:
        raise RuntimeError(
            f"No recon_<idx>/ subfolders found in {source_path} — "
            f"is this a Molecubes NI acquisition?"
        )
    log_fn(f"NI slim copy: recons={recon_indices}, dicoms_to_copy={len(plan)}")
    if n_skipped_multi:
        log_fn(
            f"  Skipping {n_skipped_multi} multi-frame (frameMULTI) DICOM(s); "
            f"per-frame DICOMs are used instead. Existence recorded in sidecar."
        )
    if n_unrecognized:
        log_fn(
            f"  WARN: {n_unrecognized} DICOM(s) at unexpected paths skipped "
            f"(see sidecar's unrecognized_dicom_paths).",
            "WARN",
        )

    if not plan:
        raise RuntimeError(
            f"NI slim copy plan is empty for {source_path}. Expected at "
            f"least one per-frame or direct .dcm under recon_<idx>/."
        )

    # Guard against destination-name collisions: two source DICOMs that map to
    # the same flat filename (e.g. >1 direct .dcm under one CT recon_<idx>/,
    # both planned as recon<idx>.dcm) would silently overwrite each other. The
    # per-file checksum can't catch it — each src is compared to its own copy,
    # so the last write wins and earlier frames are dropped with no error. Fail
    # loudly instead, naming the colliding sources.
    seen = {}
    collisions = {}
    for src_file, dst_rel in plan:
        if dst_rel in seen:
            collisions.setdefault(dst_rel, [seen[dst_rel]]).append(str(src_file))
        else:
            seen[dst_rel] = str(src_file)
    if collisions:
        detail = "; ".join(
            f"{dst} <- [{', '.join(srcs)}]" for dst, srcs in sorted(collisions.items())
        )
        raise RuntimeError(
            f"NI slim copy plan has destination-name collisions for "
            f"{source_path} (multiple source DICOMs map to the same file and "
            f"would silently overwrite): {detail}"
        )

    iterator = tqdm(plan, desc="Copying", unit="file") if HAS_TQDM else plan
    checksums = {}
    for src_file, dst_rel in iterator:
        dst_abs = os.path.join(dest_dir, dst_rel)
        os.makedirs(os.path.dirname(dst_abs), exist_ok=True)
        _copy_to_nas(src_file, dst_abs)
        src_hash = checksum.sha256_file(src_file)
        dst_hash = checksum.sha256_file(dst_abs)
        if src_hash != dst_hash:
            raise RuntimeError(
                f"Checksum mismatch on copy:\n"
                f"  src: {src_file} ({src_hash[:12]})\n"
                f"  dst: {dst_abs} ({dst_hash[:12]})"
            )
        checksums[dst_rel.replace(os.sep, "/")] = dst_hash
    log_fn(f"NI slim copy complete: {len(plan)} DICOM(s) under {data_dirname}/")
    return checksums


def copy_mri_paravision(
    source_path, dest_dir, acq_id_str, reconstructions, log_fn,
    auto_regenerate_dicom=False,
):
    """Folder-as-primary copy for a Bruker ParaVision MRI exam — v2 slim shape.

    SLIM copy (round-6 v2, 2026-05-27): only the reconstructed per-frame
    DICOMs land on gjesus3, in a flat `<ACQ-ID>.data/` subfolder. All
    other files — JCAMP-DX aux (acqp/method/visu_pars/subject), raw fid,
    per-recon non-DICOM (2dseq/visu_pars/reco), pulseprogram/specpar/
    uxnmr.* — stay on the platform acquisition machine. The parsed
    contents of the JCAMP-DX aux files are preserved in
    `metadata.json.mri._raw_metadata`, so nothing meaningful is lost;
    the on-disk acq folder mirrors microscopy's one-file-per-acquisition
    convention (`<ACQ-ID>.czi`) and NI's `<ACQ-ID>.data/` shape.

    auto_regenerate_dicom (Phase 2 of tasks.md §3.1, 2026-06-01):
    When True AND the source has no DICOMs in any selected pdata recon
    (the researcher didn't run Bruker's GUI DICOM exporter), invoke
    `paravision_regen.prepare_virtual_exam` to generate DICOMs via
    Dicomifier 2.5.3 + apply the PV-7 workarounds (PixelSpacing swap,
    Window-tag fix). Requires the `dicomifier-pilot` conda env on PATH;
    if unavailable, logs a clear error and falls through to the empty-
    placeholder behaviour. Default False — opt-in to keep the
    Dicomifier dependency optional for operators who don't need it.

    Destination layout:

      <dest_dir>/                          (e.g. ACQ-20251016-MRI-029/)
        metadata.json                       (written by caller after this)
        checksums.json                      (written by caller after this)
        README.txt                          (written by caller after this)
        <ACQ-ID>.data/                      (THIS function creates + populates)
          recon1_frame01.dcm                  (Bruker MRIm01.dcm from pdata/1/dicom/)
          recon1_frame02.dcm
          ...
          recon3_frame01.dcm                  (Bruker MRIm01.dcm from pdata/3/dicom/)
          recon3_frame02.dcm
          ...

    File-name mapping (computed by paravision_metadata._plan_dcm_target):
      - Source `pdata/<idx>/dicom/MRIm<NN>.dcm` → `recon<idx>_frame<NN>.dcm`.
      - Non-`MRIm`-prefixed DICOMs (rare): fallback to `recon<idx>_<basename>`
        + WARN.

    Reconstruction selection (`reconstructions:` YAML flag):
      None / 'all' → every pdata/<idx>/ present in the source.
      int (e.g. 3) → only that index.
      list (e.g. [1, 3]) → only those.
      Unselected indices' JCAMP-DX (visu_pars, reco) still lands in
      `_raw_metadata.pdata.<idx>` for forensic completeness, but their
      DICOMs are NOT copied.

    No-DICOM acquisition handling: if the source has NO `pdata/<idx>/
    dicom/*.dcm` files anywhere in the selected recons (the student
    didn't run Bruker's DICOM exporter), this function creates an
    empty `<ACQ-ID>.data/` folder and returns an empty checksums dict.
    Caller writes empty checksums.json + populated sidecar; the
    placeholder is filled in by an idempotent re-run after the student
    converts (or by the future FID→DICOM regeneration capability).

    Everything else from the source is dropped (NOT copied to gjesus3):
      acqp, method, visu_pars (exam-level JCAMP-DX), subject (study-level),
      fid (raw k-space ~12 MB/exam), pulseprogram, specpar, uxnmr.info,
      uxnmr.par, configscan, AdjStatePerScan,
      per-recon: 2dseq (binary image), visu_pars (parsed in sidecar),
      reco (parsed in sidecar), id, procs, methreco.

    Returns a dict mapping `<dst_relative_path> -> sha256` for the
    checksums.json file (possibly empty for no-DICOM acquisitions).
    Raises RuntimeError on hash mismatch.
    """
    from ingest import paravision_metadata

    src = Path(source_path)
    md = paravision_metadata.load_paravision_exam(src, reconstructions=reconstructions)
    data_dirname = f"{acq_id_str}.data"

    # Always create the .data subfolder (even when empty — placeholder
    # for no-DICOM acquisitions).
    data_dir_abs = os.path.join(dest_dir, data_dirname)
    os.makedirs(data_dir_abs, exist_ok=True)

    # Detect "no DICOMs in any selected recon" — the trigger for
    # auto-regeneration when the operator has opted in via the
    # `auto_regenerate_dicom: true` YAML flag.
    def _has_any_dicoms(md_):
        return any(
            p.get("selected") and p.get("dicoms")
            for p in md_.get("pdata", {}).values()
        )

    # Use a TemporaryDirectory for the virtual exam so it's auto-cleaned
    # after we finish copying. We hold the regen_ctx open across the
    # whole copy loop below — the virtual exam files must exist during
    # the per-file copy + checksum.
    import contextlib
    import tempfile as _tempfile

    regen_ctx = contextlib.ExitStack()
    try:
        if not _has_any_dicoms(md) and auto_regenerate_dicom:
            from ingest import paravision_regen

            log_fn(
                "  No DICOMs in source — auto_regenerate_dicom is true; "
                "invoking Dicomifier (`tools/ingest/paravision_regen.py`) "
                "to regenerate DICOMs from the 2dseq + JCAMP-DX aux files."
            )
            tmpdir = regen_ctx.enter_context(
                _tempfile.TemporaryDirectory(prefix=f"regen_{acq_id_str}_")
            )
            virtual_exam = Path(tmpdir) / src.name
            try:
                paravision_regen.prepare_virtual_exam(src, virtual_exam, log_fn)
            except RuntimeError as e:
                log_fn(
                    f"  Regeneration failed: {e}. "
                    f"Falling through to empty-.data/ placeholder.",
                    "WARN",
                )
                # regen_ctx will clean tmpdir on exit; md stays empty
            else:
                # Reload using the virtual exam as the new source
                md = paravision_metadata.load_paravision_exam(
                    virtual_exam, reconstructions=reconstructions,
                )
                src = virtual_exam
                if _has_any_dicoms(md):
                    log_fn("  Regeneration produced DICOMs; proceeding with normal copy.")
                else:
                    log_fn(
                        "  Regeneration produced no DICOMs — falling through "
                        "to empty-.data/ placeholder.", "WARN",
                    )

        plan = []
        recon_summary = []
        n_unrecognized = 0
        for idx in sorted(
            md.get("pdata", {}).keys(),
            key=lambda x: int(x) if x.isdigit() else x,
        ):
            p = md["pdata"][idx]
            if not p.get("selected"):
                recon_summary.append(f"pdata/{idx} (skipped — not in selection)")
                continue
            dcms = p.get("dicoms") or []
            recon_summary.append(f"pdata/{idx} ({len(dcms)} dcm)")
            for d in dcms:
                src_file = src / d["src_relpath"]
                dst_rel = os.path.join(data_dirname, d["dst_basename"])
                plan.append((src_file, dst_rel))
            n_unrecognized += len(p.get("unrecognized_dicoms") or [])

        log_fn(f"MRI slim copy: {', '.join(recon_summary) if recon_summary else 'no pdata/ subfolders found'}")
        if n_unrecognized:
            log_fn(
                f"  WARN: {n_unrecognized} non-MRIm-prefixed DICOM(s) found — "
                f"copying with fallback names; see sidecar unrecognized_dicom_paths.",
                "WARN",
            )

        if not plan:
            log_fn(
                "  No DICOMs to copy — likely the researcher didn't run Bruker's "
                "DICOM exporter (no pdata/<idx>/dicom/*.dcm in selected recons). "
                "Creating empty .data/ placeholder; sidecar will carry the "
                "parsed JCAMP-DX. Re-run after conversion is run to fill in the "
                "DICOMs (idempotent). To auto-regenerate via Dicomifier at "
                "ingest-time, set `ingest.auto_regenerate_dicom: true` in the YAML.",
                "WARN",
            )
            return {}

        # Same destination-name collision guard as the NI path: two source
        # DICOMs mapping to one flat filename would silently overwrite (the
        # per-file checksum compares each src to its own copy, so the last
        # write wins). Unlikely for MRIm<NN> names, but the non-MRIm fallback
        # (recon<idx>_<basename>) can collide. Fail loudly, naming the sources.
        _seen = {}
        _collisions = {}
        for src_file, dst_rel in plan:
            if dst_rel in _seen:
                _collisions.setdefault(dst_rel, [_seen[dst_rel]]).append(str(src_file))
            else:
                _seen[dst_rel] = str(src_file)
        if _collisions:
            detail = "; ".join(
                f"{dst} <- [{', '.join(srcs)}]" for dst, srcs in sorted(_collisions.items())
            )
            raise RuntimeError(
                f"MRI slim copy plan has destination-name collisions for "
                f"{source_path} (multiple source DICOMs map to the same file "
                f"and would silently overwrite): {detail}"
            )

        iterator = tqdm(plan, desc="Copying", unit="file") if HAS_TQDM else plan
        checksums = {}
        for src_file, dst_rel in iterator:
            dst_abs = os.path.join(dest_dir, dst_rel)
            os.makedirs(os.path.dirname(dst_abs), exist_ok=True)
            _copy_to_nas(src_file, dst_abs)
            src_hash = checksum.sha256_file(src_file)
            dst_hash = checksum.sha256_file(dst_abs)
            if src_hash != dst_hash:
                raise RuntimeError(
                    f"Checksum mismatch on copy:\n"
                    f"  src: {src_file} ({src_hash[:12]})\n"
                    f"  dst: {dst_abs} ({dst_hash[:12]})"
                )
            checksums[dst_rel.replace(os.sep, "/")] = dst_hash
        log_fn(f"MRI slim copy complete: {len(plan)} DICOM(s) under {data_dirname}/")
        return checksums
    finally:
        regen_ctx.close()


def copy_paravision_exam(source_path, dest_dir, reconstructions, log_fn):
    """Folder-as-primary copy for a Bruker ParaVision exam.

    Reorganises the as-found exam tree into:
      <dest_dir>/
        acquisition_aux/<every file at exam root>
        reconstructions/pdata_<idx>/<full pdata/<idx>/ subtree>
          (only for idx values in the `reconstructions` selection;
           omitted indices stay on the platform deep-archive)

    Returns a dict mapping `<dst_relative_path> -> sha256` for the
    checksums.json file. Raises RuntimeError if any source/dest hash
    mismatch is detected (a fail-the-ingest condition).
    """
    src = Path(source_path)
    keep = _normalize_reconstructions(reconstructions)

    # Plan the copy: build (src_file, dst_relpath) pairs.
    plan = []

    # Exam-root files -> acquisition_aux/<filename>
    for entry in sorted(src.iterdir()):
        if entry.is_file():
            plan.append((entry, os.path.join("acquisition_aux", entry.name)))

    # pdata/<idx>/<subtree> -> reconstructions/pdata_<idx>/<subtree>
    pdata_src = src / "pdata"
    selected = []
    skipped = []
    if pdata_src.is_dir():
        for entry in sorted(pdata_src.iterdir()):
            if not entry.is_dir():
                continue
            idx = entry.name
            if keep is not None and idx not in keep:
                skipped.append(idx)
                continue
            selected.append(idx)
            for root, _dirs, files in os.walk(entry):
                for fname in sorted(files):
                    sp = Path(root) / fname
                    rel_under_pdata = os.path.relpath(sp, entry)
                    dst_rel = os.path.join(
                        "reconstructions", f"pdata_{idx}", rel_under_pdata,
                    )
                    plan.append((sp, dst_rel))

    if keep is not None:
        log_fn(
            f"Reconstructions selected: kept={sorted(selected)} "
            f"skipped={sorted(skipped)} (per `reconstructions:` config)"
        )
    elif selected:
        log_fn(f"Reconstructions: keeping all ({sorted(selected)})")

    if not plan:
        raise RuntimeError(
            f"No files to copy from {source_path} — "
            f"empty exam folder or invalid reconstructions selection?"
        )

    # Execute: copy + per-file source/dest verify.
    iterator = tqdm(plan, desc="Copying", unit="file") if HAS_TQDM else plan
    checksums = {}
    for src_file, dst_rel in iterator:
        dst_abs = os.path.join(dest_dir, dst_rel)
        os.makedirs(os.path.dirname(dst_abs), exist_ok=True)
        _copy_to_nas(src_file, dst_abs)
        src_hash = checksum.sha256_file(src_file)
        dst_hash = checksum.sha256_file(dst_abs)
        if src_hash != dst_hash:
            raise RuntimeError(
                f"Checksum mismatch on copy:\n"
                f"  src: {src_file} ({src_hash[:12]})\n"
                f"  dst: {dst_abs} ({dst_hash[:12]})"
            )
        # Normalise path separators in the keys for cross-OS readability
        checksums[dst_rel.replace(os.sep, "/")] = dst_hash

    return checksums


def ingest_single(cfg_single, nas_root, dry_run=False, nas_unc=None, delete_source=False):
    """Run the ingestion workflow for a single acquisition.

    Args:
        cfg_single: Validated single-case config dict.
        nas_root: Path to NAS root (e.g., /mnt/gjesus3).
        dry_run: If True, print what would happen without doing it.
        nas_unc: UNC root for the NAS (e.g., \\\\GJESUS3\\gjesus3). Used as
            the target prefix for project .lnk shortcuts. If None, .lnk
            creation is skipped.
        delete_source: If True (or cfg's delete_source_after_ingest is True),
            remove the source file/folder after a successful verify. The
            parent of source_path is never touched.

    Returns:
        Tuple of (acq_id_str, success_bool).
    """
    source_path = cfg_single["source_path"]
    original_name = cfg_single.get("original_name") or Path(source_path).name
    cfg_single["original_name"] = original_name

    # Per-case ingest control flags merged from cfg["ingest"] (if present).
    # CLI --delete-source is OR'd in by the caller (run_batch / run_interactive).
    ingest_block = cfg_single.get("ingest") or {}
    if ingest_block.get("delete_source_after_ingest"):
        cfg_single["delete_source_after_ingest"] = True

    # --- Step 1: Analyze source ---
    log(f"Analyzing: {source_path}")

    instrument = cfg_single.get("instrument", "auto")

    # Resolve which summarizer to use BEFORE we know the final instrument
    # code. Order: explicit data_ecosystem > known instrument code >
    # auto/X-prefix (assumed DICOM, which is the only auto-detectable
    # ecosystem today).
    pre_eco = cfg_single.get("data_ecosystem", "").upper()
    if not pre_eco:
        if instrument in config.INSTRUMENT_ECOSYSTEM:
            pre_eco = config.INSTRUMENT_ECOSYSTEM[instrument]
        elif instrument == "auto" or instrument.startswith("X"):
            pre_eco = "DICOM"

    is_dicom = pre_eco == "DICOM"
    summarizer = config.get_summarizer(pre_eco)
    if summarizer is None:
        log(
            f"No summarizer registered for ecosystem '{pre_eco}'; "
            f"falling back to generic file inventory.",
            "WARN",
        )
        # Unknown ecosystem fallback: no primary-vs-auxiliary distinction
        # available, so file_count is just the total file count under the
        # source path. Ecosystems that care (DICOM, MICROSCOPY) ship their
        # own summarizers and override this.
        file_count = 0
        total_size = 0
        for root, _dirs, files in os.walk(source_path):
            for fname in files:
                fpath = os.path.join(root, fname)
                file_count += 1
                total_size += os.path.getsize(fpath)
        summary = {
            "file_count": file_count,
            "total_size_mb": round(total_size / 1_000_000, 1),
            "modality": None,
            "study_date": None,
        }
    else:
        summary = summarizer(source_path)

    # --- Step 2: Resolve instrument code ---
    if instrument == "auto":
        dicom_mod = summary.get("modality")
        if dicom_mod and dicom_mod in config.DICOM_MODALITY_TO_CODE:
            instrument = config.DICOM_MODALITY_TO_CODE[dicom_mod]
            log(f"Auto-detected instrument: {instrument} (DICOM Modality={dicom_mod})")
        else:
            log(f"Cannot auto-detect instrument. DICOM Modality={dicom_mod}", "ERROR")
            return None, False
        cfg_single["instrument"] = instrument

    # Validate / confirm instrument matches DICOM.
    # DICOM_MODALITY_TO_CODE maps a Modality tag to the *external* (X-prefix)
    # code, because the first DICOM data onboarded was collaborator XMRI/XPET.
    # The same Modality is equally valid for the internal counterpart
    # (MR -> MRI, PT -> PET, CT -> CT, NM/ST -> SPECT), so only warn on a
    # GENUINE mismatch (e.g. Modality=CT but instrument=MRI) -- not on the
    # internal-vs-external distinction, which fires on every internal scan.
    if is_dicom and summary.get("modality"):
        expected_code = config.DICOM_MODALITY_TO_CODE.get(summary["modality"])
        if expected_code:
            internal_equiv = (
                expected_code[1:] if expected_code.startswith("X")
                else expected_code
            )
            if instrument not in (expected_code, internal_equiv):
                log(
                    f"WARNING: DICOM Modality={summary['modality']} suggests "
                    f"{expected_code} (or internal {internal_equiv}), but config "
                    f"says {instrument}",
                    "WARN",
                )

    # Resolve ecosystem
    data_ecosystem = config.resolve_ecosystem(instrument)
    cfg_single["data_ecosystem"] = data_ecosystem

    # --- Step 3: Resolve ACQ-ID date prefix from acquisition_datetime ---
    # acquisition_datetime is now provided via the YAML registry: block
    # (literal, discovered.<x>, or NA). The resolver normalized it to ISO
    # ("YYYY-MM-DDT...") at expand-batch time.
    acq_dt_iso = cfg_single.get("acquisition_datetime", "")
    if acq_dt_iso and len(acq_dt_iso) >= 10:
        acq_date = acq_dt_iso[:10].replace("-", "")
    else:
        # No acquisition_datetime supplied by the config. Before defaulting
        # to today, fall back to the DICOM StudyDate the summarizer read
        # from the headers — collaborator / external DICOM carries the real
        # acquisition date in the data, not the filename (so the config can
        # legitimately set `acquisition_datetime: NA`). We also backfill
        # cfg_single["acquisition_datetime"] so the registry column and the
        # metadata sidecar reflect the real date instead of being left
        # blank. Caveat: a config that relies on this fallback keys its
        # registry rows off the discovered StudyDate while expand_batch's
        # idempotency check keys off the (empty) config value — so a re-run
        # won't dedupe these rows. That's acceptable for one-time external
        # DICOM deposits; supply an explicit acquisition_datetime to keep
        # strict idempotency.
        study_date = (summary.get("study_date") or "").strip()
        if len(study_date) == 8 and study_date.isdigit():
            acq_date = study_date
            cfg_single["acquisition_datetime"] = (
                f"{study_date[:4]}-{study_date[4:6]}-{study_date[6:8]}"
            )
            log(
                f"acquisition_datetime not provided; using DICOM StudyDate "
                f"({acq_date}) as ACQ-ID prefix and registry date."
            )
        else:
            acq_date = datetime.now(timezone.utc).strftime("%Y%m%d")
            log(
                f"acquisition_datetime not provided and no usable DICOM "
                f"StudyDate; using today ({acq_date}) as ACQ-ID prefix. "
                f"Backfill the registry acquisition_datetime when known.",
                "WARN",
            )

    # --- Step 4: Generate ACQ-ID ---
    # Allocate under the registry lock with a durable high-water reservation so
    # a concurrent ingest can't mint the same id during the file copy that
    # follows (the lock is brief and is NOT held across the copy — locking.py).
    # Dry-run previews registry-only (no reservation; a dry run writes nothing).
    registry_path = os.path.join(nas_root, "registries", "registry_raw.csv")
    registries_dir = os.path.join(nas_root, "registries")
    # Pre-flight: refuse early if the registry header doesn't match the current
    # schema (a pending migration). Without this the mismatch would only
    # surface at the registry append — AFTER the expensive file copy — and the
    # pre-commit rollback would then delete the verified copy, forcing a
    # needless re-copy. Checking here (before the ACQ-ID is even allocated)
    # fails fast, wastes nothing, and surfaces the migration need in dry-run.
    registry.assert_header_compatible(registry_path)
    if dry_run:
        acq_id_str = acq_id.generate_acq_id(acq_date, instrument, registry_path)
    else:
        with locking.registry_lock(registries_dir):
            acq_id_str = acq_id.allocate_acq_id(
                acq_date, instrument, registry_path, registries_dir,
            )
    log(f"Generated ACQ-ID: {acq_id_str}")

    # --- Step 5: Determine destination path + canonical primary file name ---
    year_str, month_str = acq_id.parse_date_for_path(acq_date)
    dest_dir = os.path.join(
        nas_root, "raw", data_ecosystem,
        year_str, month_str, acq_id_str,
    )
    canonical_path = f"/raw/{data_ecosystem}/{year_str}/{month_str}/{acq_id_str}/"

    # `acquisition_layout` from the ingest: block selects the per-ecosystem
    # primary-entity shape. Implicit defaults per ecosystem when not set.
    acquisition_layout = (ingest_block.get("acquisition_layout") or "").lower()

    if data_ecosystem == "DICOM" and acquisition_layout == "folder":
        # Folder-as-primary (internal MRI ParaVision round-6; internal
        # NI round-8). No zip. The acquisition folder is the deliverable;
        # inside it lives a `<ACQ-ID>.data/` folder (NI v2 2026-05-27) or
        # the as-found exam tree (MRI). For the registry's
        # primary_file_name, NI records the .data folder (analogue of
        # microscopy's <ACQ-ID>.czi); MRI still records the ACQ-ID itself
        # (legacy — to be aligned in the MRI redo round).
        copy_dest = dest_dir
        copy_strategy_preview = (ingest_block.get("copy_strategy") or "").lower()
        if copy_strategy_preview in ("ni_molecubes", "mri_paravision_v2"):
            cfg_single["primary_file_name"] = f"{acq_id_str}.data"
        else:
            cfg_single["primary_file_name"] = acq_id_str
        cfg_single["primary_kind"] = "folder"
        cfg_single["file_format"] = ""
    elif data_ecosystem == "DICOM" and acquisition_layout == "archive":
        # Archive-as-primary (collaborator / external DICOM): store the
        # ORIGINAL source archive file (.zip/.rar) as the acquisition's
        # primary, copied as a single large file over SMB. This is far
        # faster than walking the extracted tree (~20k loose DICOM files
        # per case = brutal small-file SMB latency) and restores the
        # compact one-archive-per-acquisition on-disk shape. Metadata
        # (date / modality / instance count) still comes from the extracted
        # `source_path` the summarizer read above; the archive to store is
        # located via `ingest.archive_primary_from` + the case name. The
        # primary is renamed to <ACQ-ID><ext> (keeps the source extension).
        archive_src = _resolve_archive_primary(cfg_single, ingest_block)
        archive_ext = os.path.splitext(archive_src)[1].lower()
        copy_dest = dest_dir
        cfg_single["primary_file_name"] = f"{acq_id_str}{archive_ext}"
        cfg_single["primary_kind"] = "archive"
        cfg_single["file_format"] = archive_ext
        cfg_single["archive_src"] = archive_src
        # NOTE (F item 4): do NOT overwrite original_name with the archive
        # basename here. The registry's original_name is the dedup key
        # (config._build_dedupe_index keys on (acq_date, original_name)), and
        # expand_batch set it to the staging-relative path (e.g. "LEONE_1.01").
        # Overwriting it with the archive file's basename ("LEONE_1.01.zip")
        # made the key written at ingest differ from the key recomputed on a
        # re-run, so an archive batch re-ingested every case with fresh
        # ACQ-IDs + duplicate rows. The archive's display name remains
        # available via archive_src / primary_file_name; original_name stays
        # dedup-stable.
    elif data_ecosystem == "DICOM":
        # Legacy collaborator DICOM: files copied into a series/ subfolder.
        # (compress-on-ingest is queued in §3.1; today the series/ tree
        # stands in for the eventual zip. Prefer acquisition_layout: archive
        # above for collaborator deposits that arrive as archives.)
        copy_dest = os.path.join(dest_dir, "series")
        cfg_single["primary_file_name"] = "series/"
        cfg_single["primary_kind"] = "archive"
        cfg_single["file_format"] = ".dcm"
    elif data_ecosystem == "MICROSCOPY":
        # Microscopy: single primary file copied directly into dest_dir under
        # the canonical name {acq_id}{ext}.
        copy_dest = dest_dir
        primary_ext = (
            summary.get("primary_extension")
            or os.path.splitext(source_path)[1].lower()
        )
        primary_name = f"{acq_id_str}{primary_ext}"
        cfg_single["primary_file_name"] = primary_name
        cfg_single["primary_kind"] = "file"
        cfg_single["file_format"] = primary_ext
    else:
        copy_dest = dest_dir
        cfg_single["primary_kind"] = ""

    # --- Summary ---
    log(f"  Source:      {source_path}")
    log(f"  Original:    {original_name}")
    log(f"  Instrument:  {instrument}")
    log(f"  Ecosystem:   {data_ecosystem}")
    log(f"  Acq Date:    {acq_date}")
    log(f"  Files:       {summary['file_count']}")
    log(f"  Size (MB):   {summary['total_size_mb']}")
    log(f"  Destination: {dest_dir}")
    if summary.get("modality"):
        log(f"  DICOM Mod:   {summary['modality']}")

    # Guard (F item 6): an empty / junk source for a data-requiring DICOM
    # layout must fail loudly, not register an empty acquisition with a real
    # ACQ-ID. Common when crawling semi-ordered historical drives. The folder
    # layout (NI/MRI) guards itself per copy-strategy — and MRI legitimately
    # allows a no-DICOM `.data/` placeholder — so it is excluded here;
    # microscopy requires a single file; archive is guarded by
    # _resolve_archive_primary. The legacy `series` / generic directory-walk
    # path is the one that would otherwise copy nothing and "succeed".
    # Fires in dry-run too, so a preview surfaces the junk folder.
    if (
        data_ecosystem == "DICOM"
        and acquisition_layout not in ("folder", "archive")
        and summary.get("file_count", 0) == 0
    ):
        log(
            f"Refusing to ingest empty source (0 primary/DICOM files): "
            f"{source_path}. Nothing to register — check this folder.",
            "ERROR",
        )
        return acq_id_str, False

    # Microscopy stores a single primary file (the .czi/.tif). The copy step
    # below requires a file source; reject a folder source HERE — before the
    # dry-run early return — so a preview and a real run agree. Otherwise the
    # dry-run "succeeds" and the real run fails after the ACQ-ID is allocated.
    if data_ecosystem == "MICROSCOPY" and not os.path.isfile(source_path):
        log(
            f"Microscopy ingest expects a single file source; got "
            f"{source_path}",
            "ERROR",
        )
        return acq_id_str, False

    if dry_run:
        log("[DRY RUN] Would create folder and copy files. Skipping.")
        return acq_id_str, True

    # --- Steps 6-8: Copy + checksum + verify (per-ecosystem) ---
    os.makedirs(copy_dest, exist_ok=True)

    if data_ecosystem == "DICOM" and acquisition_layout == "folder":
        # Folder-as-primary copy — per-instrument strategy selected by
        # `copy_strategy:` in the ingest: block. Default `paravision_exam`
        # for back-compat (round-6 MRI). NI uses `ni_molecubes` (round-8
        # redo 2026-05-26). See per-instrument templates for which
        # strategy to set.
        copy_strategy = (ingest_block.get("copy_strategy") or "paravision_exam").lower()
        log(f"Folder-as-primary copy (strategy: {copy_strategy})")
        try:
            if copy_strategy == "ni_molecubes":
                dest_checksums = copy_ni_acquisition(
                    source_path, dest_dir, acq_id_str, log,
                )
            elif copy_strategy == "mri_paravision_v2":
                reconstructions = ingest_block.get("reconstructions")
                auto_regenerate_dicom = bool(ingest_block.get("auto_regenerate_dicom", False))
                log(f"  reconstructions: {reconstructions!r}")
                if auto_regenerate_dicom:
                    log(
                        "  auto_regenerate_dicom: true (no-DICOM exams will be "
                        "regenerated via Dicomifier — requires `dicomifier` on PATH)"
                    )
                dest_checksums = copy_mri_paravision(
                    source_path, dest_dir, acq_id_str, reconstructions, log,
                    auto_regenerate_dicom=auto_regenerate_dicom,
                )
            elif copy_strategy == "paravision_exam":
                reconstructions = ingest_block.get("reconstructions")
                log(f"  reconstructions: {reconstructions!r}")
                dest_checksums = copy_paravision_exam(
                    source_path, dest_dir, reconstructions, log,
                )
            else:
                log(
                    f"Unknown copy_strategy: {copy_strategy!r}. "
                    f"Valid: 'paravision_exam', 'mri_paravision_v2', 'ni_molecubes'.",
                    "ERROR",
                )
                return acq_id_str, False
        except RuntimeError as e:
            log(str(e), "ERROR")
            return acq_id_str, False
        log(f"Copied + verified {len(dest_checksums)} files")
        checksum.write_checksums(
            dest_checksums,
            os.path.join(dest_dir, "checksums.json"),
        )
        log(f"Wrote checksums.json ({len(dest_checksums)} files)")

        # Recompute file_count and size from the DESTINATION (not the
        # source) — the registry should reflect what actually landed on
        # the NAS, which is selective (omits unwanted recon indices and
        # any pre-reconstruction raw the layout drops).
        dest_size = 0
        dcm_count = 0
        for root, _dirs, files in os.walk(dest_dir):
            for fname in files:
                if fname in ("checksums.json", "metadata.json", "README.txt"):
                    continue
                fpath = os.path.join(root, fname)
                dest_size += os.path.getsize(fpath)
                if fname.lower().endswith(".dcm"):
                    dcm_count += 1
        summary["file_count"] = dcm_count
        summary["total_size_mb"] = round(dest_size / 1_000_000, 1)
        log(
            f"Registry will record file_count={summary['file_count']} (.dcm), "
            f"size={summary['total_size_mb']} MB (deposited)"
        )
    elif data_ecosystem == "DICOM" and acquisition_layout == "archive":
        # Archive-as-primary copy: a single large source archive (.zip/.rar)
        # transferred to the NAS as <ACQ-ID><ext> — one sequential SMB copy
        # instead of ~20k loose-file copies. Mirrors the microscopy
        # single-file path (compute source hash, copy, verify dest hash).
        archive_src = cfg_single["archive_src"]
        primary_name = cfg_single["primary_file_name"]
        dst_file = os.path.join(copy_dest, primary_name)
        archive_mb = round(os.path.getsize(archive_src) / 1_000_000, 1)
        log(f"Computing source archive checksum ({archive_mb} MB)...")
        src_hash = checksum.sha256_file(archive_src)
        log(f"Copying archive -> {primary_name}")
        _copy_to_nas(archive_src, dst_file)
        log("Verifying copy integrity...")
        dst_hash = checksum.sha256_file(dst_file)
        if dst_hash != src_hash:
            log(
                f"Verification FAILED — source/dest hashes differ "
                f"({src_hash[:12]} vs {dst_hash[:12]})",
                "ERROR",
            )
            return acq_id_str, False
        log("Verification PASSED")
        checksum.write_checksums(
            {primary_name: dst_hash},
            os.path.join(dest_dir, "checksums.json"),
        )
        log("Wrote checksums.json (1 file)")
        # Registry size reflects the stored (compressed) archive; file_count
        # stays the extracted DICOM instance count from the summarizer.
        summary["total_size_mb"] = archive_mb
    elif data_ecosystem == "MICROSCOPY":
        # Single-file copy with rename. Source must be a file.
        if not os.path.isfile(source_path):
            log(
                f"Microscopy ingest expects a single file source; "
                f"got {source_path}",
                "ERROR",
            )
            return acq_id_str, False
        primary_name = cfg_single["primary_file_name"]
        dst_file = os.path.join(copy_dest, primary_name)
        log(f"Computing source checksum...")
        src_hash = checksum.sha256_file(source_path)
        log(f"Copying file -> {primary_name}")
        _copy_to_nas(source_path, dst_file)
        log("Verifying copy integrity...")
        dst_hash = checksum.sha256_file(dst_file)
        if dst_hash != src_hash:
            log(
                f"Verification FAILED — source/dest hashes differ "
                f"({src_hash[:12]} vs {dst_hash[:12]})",
                "ERROR",
            )
            return acq_id_str, False
        log("Verification PASSED")
        checksum.write_checksums(
            {primary_name: dst_hash},
            os.path.join(dest_dir, "checksums.json"),
        )
        log("Wrote checksums.json (1 file)")
    else:
        # DICOM (and unknown ecosystems): directory-walk copy, recursive
        # checksum, and source-vs-dest verification.
        log("Copying files...")
        n_copied = copy_files(source_path, copy_dest)
        log(f"Copied {n_copied} files")

        log("Computing checksums on destination...")
        if HAS_TQDM:
            pbar = tqdm(total=0, desc="Checksums", unit="file")
            def cb(rel, i, total):
                pbar.total = total
                pbar.update(1)
            dest_checksums = checksum.compute_checksums(dest_dir, progress_callback=cb)
            pbar.close()
        else:
            dest_checksums = checksum.compute_checksums(dest_dir)

        checksum_path = os.path.join(dest_dir, "checksums.json")
        checksum.write_checksums(dest_checksums, checksum_path)
        log(f"Wrote checksums.json ({len(dest_checksums)} files)")

        log("Verifying copy integrity...")
        ok, mismatches = checksum.verify_checksums(source_path, copy_dest)
        if ok:
            log("Verification PASSED - all files match")
        else:
            log(f"Verification FAILED - {len(mismatches)} mismatches:", "ERROR")
            for m in mismatches[:10]:
                log(f"  {m}", "ERROR")
            return acq_id_str, False

    # --- Steps 8.4-10: enrichment, sidecar, README, project, registry append ---
    # The registry append is the COMMIT POINT (F item 5): an acquisition only
    # "counts" once its row is written. If anything between the copy and the
    # append raises, roll back the partially-written dest folder so a re-run
    # starts clean (no orphan the dedup index can't see). --delete-source is
    # deferred to AFTER the commit (end of this function), so the source is
    # never removed unless the row exists.
    committed = False
    try:
        # --- Step 8.5: Write metadata.json sidecar ---
        # Section name defaults to lowercased ecosystem ("dicom", "microscopy")
        # but can be overridden by the extractor's 3-tuple return form (e.g.
        # ParaVision data lives under metadata.json.mri even though ecosystem
        # is DICOM, since the contents are ParaVision-specific not generic
        # DICOM headers). See config._extract_dicom_embedded.
        eco_section_name = (
            cfg_single.get("ecosystem_section_name")
            or (data_ecosystem.lower() if data_ecosystem else "")
        )
        eco_section = cfg_single.get("ecosystem_section") or {}

        # Scan-name signals for anatomy auto-derivation. Only MRI exposes a
        # deriving signal today (ParaVision scan name / sequence); other
        # ecosystems pass derive_fields=None (no auto-derive). The operator's
        # explicit anatomy: block always wins — this only fills the gap. See
        # ingest/anatomy_derive.py.
        derive_fields = None
        if eco_section_name == "mri":
            from ingest import anatomy_derive
            derive_fields = anatomy_derive.collect_mri_signals(
                cfg_single.get("discovered") or {}, eco_section,
            )

        # --- Step 8.4: Preclinical enrichment blocks (non-blocking) ---
        # subject/condition/anatomy for organism|tissue acquisitions
        # (08_METADATA §4.4–4.7). Never raises: a DB miss WARNs, writes a
        # source="pending-db" placeholder, and queues the acq to
        # registries/pending_subject_metadata.csv for later recovery.
        subjects_list, condition_block, anatomy_block = enrichment.build_enrichment(
            cfg_single,
            acq_id=acq_id_str,
            acq_date=acq_date,
            acq_dt_iso=acq_dt_iso,
            canonical_path=canonical_path,
            registries_dir=os.path.join(nas_root, "registries"),
            dry_run=dry_run,
            log=log,
            derive_fields=derive_fields,
        )
        # subjects_list: 1 block for single-animal instruments, 1-4 for a
        # multi-animal NI scan (NI-LIVE-08). The primary (first) feeds the single
        # `subject` sidecar key (back-compat); the full list packs subject_ids,
        # the sidecar subjects:[] array, and the subjects-table rows.
        subject_block = subjects_list[0] if subjects_list else None
        multi_subjects = subjects_list if len(subjects_list) > 1 else None

        # (The correction-pass S1 stashed cfg_single["subject_id"] here; the
        # merged build_row now projects subject_ids / sample_organism /
        # anatomical_entity straight from subject_block / anatomy_block — passed
        # to build_row at Step 10 — so the stash is no longer needed.)

        sidecar_dict = metadata_sidecar.build_sidecar(
            acq_id_str,
            cfg_single,
            ecosystem_section_name=eco_section_name,
            ecosystem_section=eco_section,
            subject=subject_block,
            subjects=multi_subjects,
            condition=condition_block,
            anatomy=anatomy_block,
        )
        sidecar_path = metadata_sidecar.write_sidecar(dest_dir, sidecar_dict)
        cfg_single["extended_metadata_present"] = "Y"
        log(f"Wrote {os.path.basename(sidecar_path)}")

        # --- Step 9: Generate README ---
        readme.generate_readme(acq_id_str, cfg_single, summary, dest_dir)
        log("Wrote README.txt")

        # --- Step 9.5: Resolve project_hint (canonicalize; optional auto-create) ---
        # Runs before the registry append so the row records the canonical
        # PROJ-XXXX, not whatever raw hint came in. Step 12 (.lnk) reads the
        # resolved value too.
        project_hint = cfg_single.get("project_hint", "").strip()
        if project_hint:
            projects_registry = os.path.join(nas_root, "registries", "registry_projects.csv")
            proj_id, _proj_folder = linker.resolve_project(projects_registry, project_hint)
            if proj_id:
                if proj_id != project_hint:
                    log(f"Resolved project_hint '{project_hint}' -> {proj_id} (by short_name)")
                # First-write-wins: if the YAML config supplied an
                # auto_create_project: block but the project already exists,
                # the block is silently ignored — log an INFO line so the
                # operator sees it didn't apply.
                if cfg_single.get("auto_create_project"):
                    log(
                        f"Project '{proj_id}' already exists; auto_create_project "
                        f"block ignored (first-write-wins). Edit "
                        f"_project.yaml directly if you need to update."
                    )
                cfg_single["project_hint"] = proj_id
            else:
                ingest_block = cfg_single.get("ingest") or {}
                if ingest_block.get("auto_create_projects"):
                    short_name_norm = project_hint.lower()

                    # Resolve the optional auto_create_project: block against
                    # this case's discovered fields. The block is the new
                    # canonical source for owner/description/notes; legacy
                    # fallback values are used only if the block didn't
                    # supply them (empty / unsupplied).
                    acp_resolved = resolver.resolve_auto_create_project_block(
                        cfg_single.get("auto_create_project"),
                        cfg_single.get("discovered") or {},
                    )
                    owner = acp_resolved.get("owner") or cfg_single.get("operator", "") or "?"
                    desc = acp_resolved.get("description") or (
                        f"Auto-created during ingest of "
                        f"{cfg_single.get('original_name', '?')} "
                        f"(hint='{project_hint}')"
                    )
                    notes_for_proj = (
                        acp_resolved.get("notes") or "auto-created by ingest_raw.py"
                    )

                    if not owner or owner == "?":
                        log(
                            f"Auto-creating project '{short_name_norm}' with "
                            f"empty/unknown owner. Edit "
                            f"projects/proj-{short_name_norm}/_project.yaml "
                            f"after creation to set ownership.",
                            "WARN",
                        )

                    log(f"Auto-creating project: short_name='{short_name_norm}', owner='{owner}'")
                    new_id, ok = create_project_mod.create_project(
                        short_name_norm, desc, owner, nas_root,
                        dry_run=False,
                        notes=notes_for_proj,
                    )
                    if ok and new_id:
                        cfg_single["project_hint"] = new_id
                    else:
                        log(
                            f"Project auto-create failed for hint='{project_hint}'; "
                            f"leaving registry project_hint as the raw value",
                            "WARN",
                        )
                else:
                    log(
                        f"project_hint='{project_hint}' not found in registry and "
                        f"ingest.auto_create_projects is false; leaving registry "
                        f"project_hint as the raw value",
                        "WARN",
                    )

        # --- Step 10: Update registry (the commit point) ---
        # Serialize the append under the registry lock (torn-line safety over
        # SMB). Brief hold — just the append. subject_block / anatomy_block were
        # built at Step 8.4 (above); pass them so build_row projects
        # sample_organism / subject_ids / anatomical_entity.
        reg_dt = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        row = registry.build_row(acq_id_str, cfg_single, summary, canonical_path, reg_dt,
                                 anatomy=anatomy_block, subjects=subjects_list)
        with locking.registry_lock(registries_dir):
            registry.append_row(registry_path, row)
            # Step 10b: upsert this acquisition's subject(s) into the one-row-
            # per-subject registry_subjects.csv (06_REGISTRIES §2.3.2 /
            # NI-LIVE-08), under the SAME lock — _hold_lock=False, since the lock
            # is not reentrant and re-acquiring would deadlock. NON-BLOCKING,
            # like enrichment: a subjects-table failure must never fail an ingest
            # whose registry row already committed. subjects_list is empty for
            # non-animal samples (no rows), 1 block for single-animal, and 1-4
            # for a multi-animal NI scan — one upsert call handles all.
            try:
                srows = [r for r in (subjects_table.row_from_subject_block(sb)
                                     for sb in subjects_list) if r]
                if srows:
                    subjects_table.upsert_subjects(
                        registries_dir, srows, now=reg_dt, log=log,
                        _hold_lock=False,
                    )
            except Exception as e:
                log(f"subjects table upsert failed (non-blocking): {e}", "WARN")
        committed = True
        log(f"Appended to registry: {registry_path}")
    except Exception as e:
        # Any failure between the copy and the registry commit: report the case
        # as failed; the finally rolls back the partial dest (below).
        log(
            f"Ingest failed after copy, before the registry commit "
            f"({acq_id_str}): {e}",
            "ERROR",
        )
        return acq_id_str, False
    finally:
        # Roll back the partial dest on ANY exit without a commit — an exception
        # handled above, or a KeyboardInterrupt/abort that bypasses the except —
        # so a re-run never meets an orphan the dedup index can't see.
        # Best-effort + idempotent; a clean commit (committed=True) is a no-op.
        if not committed:
            _rollback_uncommitted(dest_dir, log)

    # --- Step 11: Manifest entry (post-commit; non-fatal) ---
    manifest_path = os.path.join(nas_root, "registries", "ingest_manifest.csv")
    try:
        linker.create_manifest_entry(manifest_path, acq_id_str, original_name, canonical_path)
    except Exception as e:
        log(
            f"Could not write manifest entry (non-fatal — registry row already "
            f"committed): {e}",
            "WARN",
        )

    # --- Step 12: Project hard link (if project_hint set) ---
    # Replaces the legacy .lnk shortcut (2026-06-02): the project copy is a
    # real file identical to the raw primary — same inode, zero extra storage,
    # and it carries raw's single security descriptor (a read-only raw file
    # stays read-only through the link). Hard links use LOCAL paths on the NAS
    # volume, so --nas-unc is no longer needed for linking.
    project_hint = cfg_single.get("project_hint", "").strip()
    if project_hint:
        projects_registry = os.path.join(
            nas_root, "registries", "registry_projects.csv"
        )
        project_folder_rel = linker.lookup_project_folder(
            projects_registry, project_hint
        )
        if not project_folder_rel:
            log(
                f"project_hint={project_hint} not found in "
                f"registry_projects.csv; skipping hard-link creation",
                "WARN",
            )
        else:
            project_folder_abs = os.path.normpath(
                os.path.join(nas_root, project_folder_rel.lstrip("/"))
            )
            # Local path to the acquisition folder on the NAS volume.
            raw_acq_dir = os.path.normpath(
                os.path.join(nas_root, canonical_path.lstrip("/"))
            )
            # Resolve which raw primary the link points at, based on
            # primary_kind and whether primary_file_name names something
            # nested inside the acq folder (NI/MRI v2: <ACQ-ID>.data) or IS
            # the acq folder itself (legacy MRI folder layout). A folder
            # primary becomes a real folder of per-file hard links; a file
            # primary becomes a single hard link (see linker.create_hardlink).
            primary = cfg_single.get("primary_file_name", "")
            primary_kind = cfg_single.get("primary_kind", "")
            if primary and primary_kind == "folder" and primary != acq_id_str:
                # NI/MRI v2: primary is an internal data bundle (<ACQ-ID>.data).
                raw_primary_abs = os.path.join(raw_acq_dir, primary)
            elif primary and primary_kind == "folder":
                # Legacy MRI folder layout: primary_file_name == acq_id_str.
                raw_primary_abs = raw_acq_dir
            elif primary and not primary.endswith("/"):
                # Single-file primary (microscopy .czi, collaborator zip/rar).
                raw_primary_abs = os.path.join(raw_acq_dir, primary)
            else:
                raw_primary_abs = raw_acq_dir
            # Link name = resolved `link_filename:` (operator-controlled top-
            # level YAML field), falling back to original_name. This is the
            # same name the legacy .lnk used, minus the `.lnk` suffix.
            link_template = cfg_single.get("link_filename") or ""
            link_name = None
            if link_template:
                link_name = resolver.resolve_link_filename(
                    link_template, cfg_single, acq_id_str, acq_date,
                )
                if link_name:
                    # Trailing slash allowed in the template as a "links to a
                    # folder" hint; strip it so the name is filesystem-clean.
                    link_name = link_name.rstrip("/").rstrip("\\")
            if not link_name:
                link_name = original_name
            try:
                link_path = linker.create_hardlink(
                    project_folder_abs,
                    link_name,
                    raw_primary_abs,
                    dry_run=False,
                )
                is_dir_link = os.path.isdir(link_path)
                kind = "folder of per-file hard links" if is_dir_link else "hard link"
                log(f"Created {kind}: {link_path} -> {raw_primary_abs}")
                # Provenance log entry for the link just created. Idempotent
                # on output_path: skips silently if the project's
                # provenance.csv already has a row for this link (self-heals
                # if the link existed but the entry was missing).
                prov_path = os.path.join(project_folder_abs, "provenance.csv")
                entry = {
                    "output_path":         f"raw_linked/{link_name}",
                    "output_name":         link_name,
                    "file_type":           "hardlink-folder" if is_dir_link else "hardlink",
                    "date_created":        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "creator":             cfg_single.get("operator", "") or "",
                    "input_refs":          acq_id_str,
                    "process_description": (
                        "Auto-created during ingest: folder of per-file hard "
                        "links to raw acquisition"
                        if is_dir_link else
                        "Auto-created during ingest: hard link to raw acquisition"
                    ),
                    "software_version":   provenance.software_version_string("ingest_raw.py"),
                    "parameters_ref":      cfg_single.get("ingest_config", "") or "",
                    "lab_notebook_ref":    "",
                    "notes":               "Auto-generated entry from ingest",
                }
                fid = provenance.append_entry(prov_path, entry)
                if fid:
                    log(f"Appended provenance entry {fid} to {prov_path}")
            except OSError as e:
                log(f"Could not create hard link: {e}", "WARN")
            except Exception as e:
                log(f"Unexpected error creating hard link: {e}", "WARN")

    # --- Step 13: Optional delete-source (cross-instrument) ---
    # MOVED to after the registry commit (F item 5): the source is removed only
    # once the row exists, so a crash before the commit can never destroy the
    # source while leaving an unrecorded copy. The parent of source_path is
    # never touched.
    effective_delete = bool(delete_source) or bool(
        cfg_single.get("delete_source_after_ingest")
    )
    if effective_delete:
        try:
            if os.path.isfile(source_path):
                os.remove(source_path)
                log(f"Deleted source file: {source_path}")
            elif os.path.isdir(source_path):
                shutil.rmtree(source_path)
                log(f"Deleted source directory: {source_path}")
        except Exception as e:
            log(f"Could not delete source: {e}", "WARN")

    log(f"DONE: {acq_id_str}")
    return acq_id_str, True


def run_batch(cfg, nas_root, dry_run=False, nas_unc=None, delete_source=False):
    """Run batch ingestion from a batch config.

    Returns list of (acq_id, success) tuples.
    """
    cases = config.expand_batch(cfg, nas_root=nas_root)
    # Stamp ingest_config onto every case (set in main()).
    ingest_config_path = cfg.get("_ingest_config_path", "")
    for case in cases:
        case["ingest_config"] = ingest_config_path
    log(f"Batch: {len(cases)} cases discovered")

    # Pre-flight: if any case will hit the animal DB for subject enrichment but
    # credentials are absent, warn ONCE up front — otherwise every subject
    # silently becomes source='pending-db' (easy to miss across a large batch).
    # Common in WSL, where ~/.my.cnf is the WSL home and GJESUS3_MYCNF is unset.
    if any(c.get("subject_from_db") for c in cases) and not animal_db.credentials_available():
        log(
            f"animal-DB credentials not found ({animal_db.CNF_PATH}) — every "
            f"DB-sourced subject in this batch will be written as 'pending-db' "
            f"for later recovery. In WSL, export GJESUS3_MYCNF=<path to .my.cnf> "
            f"(or place ~/.my.cnf in the WSL home) before running. See the MRI "
            f"no-DICOM regeneration runbook §4.",
            "WARN",
        )

    results = []
    for i, case in enumerate(cases):
        log(f"\n{'='*60}")
        log(f"Case {i+1}/{len(cases)}: {case.get('source_path', '?')}")
        log(f"{'='*60}")

        errors = config.validate_single(case)
        if errors:
            for e in errors:
                log(e, "ERROR")
            results.append((None, False))
            continue

        acq_id_str, ok = ingest_single(
            case, nas_root,
            dry_run=dry_run, nas_unc=nas_unc, delete_source=delete_source,
        )
        results.append((acq_id_str, ok))

    # --- Summary ---
    print(f"\n{'='*60}")
    print("BATCH SUMMARY")
    print(f"{'='*60}")
    n_ok = sum(1 for _, ok in results if ok)
    n_fail = sum(1 for _, ok in results if not ok)
    print(f"  Total:    {len(results)}")
    print(f"  Success:  {n_ok}")
    print(f"  Failed:   {n_fail}")
    if n_fail > 0:
        print("  Failed cases:")
        for i, (aid, ok) in enumerate(results):
            if not ok:
                print(f"    Case {i+1}: {cases[i].get('source_path', '?')}")
    print()
    return results


def run_interactive(nas_root, dry_run=False, nas_unc=None, delete_source=False,
                    ingest_config_path=""):
    """Interactive mode for single-case ingestion.

    Builds the same {ingest, registry} cfg shape as a YAML config and runs
    it through prep_single_case so the resolver / validation paths are
    identical to file-driven configs.
    """
    print("=== Interactive Raw Data Ingestion ===\n")

    cfg_single = {"source_path": input("Source path: ").strip()}

    instrument = input("Instrument code (e.g., XMRI, ZWSI): ").strip()
    data_ecosystem = (
        config.INSTRUMENT_ECOSYSTEM.get(instrument, "")
        if instrument else ""
    )

    reg_block = {
        "instrument":          instrument or "NA",
        "data_ecosystem":      data_ecosystem or "NA",
        "operator":            input("Operator (initials): ").strip() or "NA",
        "data_source":         input(
            "Data source (e.g. 'internal' or 'collaborator:NAME'): "
        ).strip() or "NA",
        "sample_id":           input("Sample ID (optional, NA to skip): ").strip() or "NA",
        "sample_type":         input("Sample type (optional, NA to skip): ").strip() or "NA",
        "acquisition_datetime": input(
            "Acquisition date (YYYYMMDD or YYYY-MM-DD; NA to fill in later): "
        ).strip() or "NA",
        "notes":               input("Notes (optional, NA to skip): ").strip() or "NA",
    }
    proj = input("Project ID (e.g. PROJ-0001, blank for none): ").strip()
    if proj:
        reg_block["project_hint"] = proj

    cfg_single["registry"] = reg_block
    cfg_single["ingest_config"] = ingest_config_path  # "" in interactive mode

    try:
        config.prep_single_case(cfg_single)
    except (ValueError, config.resolver.ResolverError) as e:
        log(str(e), "ERROR")
        sys.exit(1)

    errors = config.validate_single(cfg_single)
    if errors:
        for e in errors:
            log(e, "ERROR")
        sys.exit(1)

    acq_id_str, ok = ingest_single(
        cfg_single, nas_root,
        dry_run=dry_run, nas_unc=nas_unc, delete_source=delete_source,
    )
    if not ok:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Ingest raw data from staging to structured raw area.",
        epilog="See 10_TOOLS.md for full documentation.",
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to YAML config file (single or batch)",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode (single case)",
    )
    parser.add_argument(
        "--nas-root",
        default=os.environ.get("GJESUS3_ROOT", "/mnt/gjesus3"),
        help="Path to NAS root (default: $GJESUS3_ROOT or /mnt/gjesus3)",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview what would happen without making changes",
    )
    parser.add_argument(
        "--project",
        help="Project ID (e.g. PROJ-0001) — recorded as project_hint in the raw registry",
    )
    parser.add_argument(
        "--nas-unc",
        default=os.environ.get("GJESUS3_UNC", r"\\GJESUS3\gjesus3"),
        help=(
            "UNC root for the NAS, used as the target prefix for project "
            ".lnk shortcuts (default: $GJESUS3_UNC or \\\\GJESUS3\\gjesus3). "
            "Pass an empty string to disable .lnk creation."
        ),
    )
    parser.add_argument(
        "--delete-source",
        action="store_true",
        help=(
            "Delete the source file/folder after a successful copy + "
            "verify. Default OFF. The parent of source_path is never "
            "touched. Cross-instrument: applies to DICOM and microscopy."
        ),
    )

    args = parser.parse_args()

    if not args.config and not args.interactive:
        parser.error("Must specify --config or --interactive")

    nas_root = args.nas_root
    # nas_unc is retained for the legacy .lnk porting seam but is NOT used by
    # the current hard-link linker (hard links use local NAS-volume paths).
    nas_unc = args.nas_unc or None
    log(f"NAS root: {nas_root}")

    # Fail fast if nas_root doesn't look like a real NAS root. Without this
    # check, Python silently creates whatever path was passed (e.g. the WSL
    # default "/mnt/gjesus3" resolves to "C:\mnt\gjesus3" on Windows native
    # Python) and the ingest runs to completion writing into a phantom tree.
    registries_dir = os.path.join(nas_root, "registries")
    if not os.path.isdir(nas_root) or not os.path.isdir(registries_dir):
        log(
            f"NAS root does not look valid: '{nas_root}' (expected a "
            f"directory containing a 'registries/' subfolder).",
            "ERROR",
        )
        log(
            "Pass --nas-root <path> explicitly, or set GJESUS3_ROOT in your "
            "shell. On Windows PowerShell: $env:GJESUS3_ROOT = 'J:\\'  "
            "(adjust drive letter to your NAS mount). On WSL: typically "
            "/mnt/gjesus3.",
            "ERROR",
        )
        sys.exit(2)
    # Project links are now hard links (local NAS-volume paths); they are
    # created whenever a row's project_hint resolves, independent of nas_unc.
    if nas_unc:
        log(f"NAS UNC:  {nas_unc} (legacy .lnk seam only; unused by hard-link linker)")

    if args.dry_run:
        log("*** DRY RUN MODE - no changes will be made ***")

    if args.delete_source:
        log("--delete-source: source files will be removed after successful verify", "WARN")

    ingest_config_rel = relative_config_path(args.config) if args.config else ""
    if ingest_config_rel:
        log(f"Ingest config: {ingest_config_rel}")

    if args.interactive:
        run_interactive(
            nas_root,
            dry_run=args.dry_run, nas_unc=nas_unc, delete_source=args.delete_source,
            ingest_config_path=ingest_config_rel,
        )
    else:
        cfg = config.load_config(args.config)
        # CLI --project overrides project_hint in the registry: block
        if args.project:
            cfg.setdefault("registry", {})["project_hint"] = args.project

        if config.is_batch_config(cfg):
            # Stamp ingest_config so each case's registry row records it.
            cfg.setdefault("registry", {})  # may already exist
            cfg["_ingest_config_path"] = ingest_config_rel
            run_batch(
                cfg, nas_root,
                dry_run=args.dry_run, nas_unc=nas_unc, delete_source=args.delete_source,
            )
        else:
            # Single-case config — validate + resolve registry: block.
            cfg["ingest_config"] = ingest_config_rel
            try:
                config.prep_single_case(cfg)
            except (ValueError, config.resolver.ResolverError) as e:
                log(str(e), "ERROR")
                sys.exit(1)
            errors = config.validate_single(cfg)
            if errors:
                for e in errors:
                    log(e, "ERROR")
                sys.exit(1)
            _, ok = ingest_single(
                cfg, nas_root,
                dry_run=args.dry_run, nas_unc=nas_unc, delete_source=args.delete_source,
            )
            if not ok:
                sys.exit(1)


if __name__ == "__main__":
    main()
