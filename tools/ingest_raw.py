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
    metadata_sidecar, provenance, resolver,
)
import create_project as create_project_mod


def relative_config_path(config_path):
    """Return config_path as a forward-slash path relative to the git repo root.

    Falls back to a CWD-relative path if not in a git repo.
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
            return os.path.relpath(abs_path, repo_root).replace("\\", "/")
    except Exception:
        pass
    return os.path.relpath(abs_path).replace("\\", "/")

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


def log(msg, level="INFO"):
    """Print a timestamped log message."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}")


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
        shutil.copy2(src_path, dst_path)
        count += 1

    return count


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
        shutil.copy2(src_file, dst_abs)
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

    # Validate / confirm instrument matches DICOM
    if is_dicom and summary.get("modality"):
        expected_code = config.DICOM_MODALITY_TO_CODE.get(summary["modality"])
        if expected_code and expected_code != instrument:
            log(
                f"WARNING: DICOM Modality={summary['modality']} suggests "
                f"{expected_code}, but config says {instrument}",
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
        acq_date = datetime.now(timezone.utc).strftime("%Y%m%d")
        log(
            f"acquisition_datetime not provided; using today ({acq_date}) "
            f"as ACQ-ID prefix. Backfill the registry acquisition_datetime "
            f"when known.",
            "WARN",
        )

    # --- Step 4: Generate ACQ-ID ---
    registry_path = os.path.join(nas_root, "registries", "registry_raw.csv")
    acq_id_str = acq_id.generate_acq_id(acq_date, instrument, registry_path)
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
        # NEW 2026-05-20: folder-as-primary (internal MRI ParaVision).
        # No zip, no series/ wrapper. The acquisition folder IS the unit.
        # Selective copy honours `reconstructions:` flag (see Steps 6-8).
        copy_dest = dest_dir
        cfg_single["primary_file_name"] = acq_id_str
        cfg_single["primary_kind"] = "folder"
        cfg_single["file_format"] = ""
    elif data_ecosystem == "DICOM":
        # Legacy collaborator DICOM: files copied into a series/ subfolder.
        # (compress-on-ingest is queued in §3.1; today the series/ tree
        # stands in for the eventual zip.)
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

    if dry_run:
        log("[DRY RUN] Would create folder and copy files. Skipping.")
        return acq_id_str, True

    # --- Steps 6-8: Copy + checksum + verify (per-ecosystem) ---
    os.makedirs(copy_dest, exist_ok=True)

    if data_ecosystem == "DICOM" and acquisition_layout == "folder":
        # NEW 2026-05-20: ParaVision folder-as-primary copy.
        # Selective: only the reconstructions listed in `reconstructions:`
        # are kept; everything at the exam root lands in acquisition_aux/.
        # Per-file source/dest hash verification raises on mismatch.
        reconstructions = ingest_block.get("reconstructions")
        log(f"Folder-as-primary copy (reconstructions: {reconstructions!r})")
        try:
            dest_checksums = copy_paravision_exam(
                source_path, dest_dir, reconstructions, log,
            )
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
        shutil.copy2(source_path, dst_file)
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
            log("Verification PASSED — all files match")
        else:
            log(f"Verification FAILED — {len(mismatches)} mismatches:", "ERROR")
            for m in mismatches[:10]:
                log(f"  {m}", "ERROR")
            return acq_id_str, False

    # --- Step 8b: Optional delete-source (cross-instrument) ---
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
    sidecar_dict = metadata_sidecar.build_sidecar(
        acq_id_str,
        cfg_single,
        ecosystem_section_name=eco_section_name,
        ecosystem_section=eco_section,
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

    # --- Step 10: Update registry ---
    reg_dt = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = registry.build_row(acq_id_str, cfg_single, summary, canonical_path, reg_dt)
    registry.append_row(registry_path, row)
    log(f"Appended to registry: {registry_path}")

    # --- Step 11: Manifest entry (always) ---
    manifest_path = os.path.join(nas_root, "registries", "ingest_manifest.csv")
    linker.create_manifest_entry(manifest_path, acq_id_str, original_name, canonical_path)

    # --- Step 12: Project .lnk shortcut (if project_hint set) ---
    project_hint = cfg_single.get("project_hint", "").strip()
    if project_hint:
        if not nas_unc:
            log(
                f"project_hint={project_hint} but --nas-unc not provided; "
                f"skipping .lnk creation",
                "WARN",
            )
        else:
            projects_registry = os.path.join(
                nas_root, "registries", "registry_projects.csv"
            )
            project_folder_rel = linker.lookup_project_folder(
                projects_registry, project_hint
            )
            if not project_folder_rel:
                log(
                    f"project_hint={project_hint} not found in "
                    f"registry_projects.csv; skipping .lnk creation",
                    "WARN",
                )
            else:
                project_folder_abs = os.path.normpath(
                    os.path.join(nas_root, project_folder_rel.lstrip("/"))
                )
                folder_unc = linker.canonical_to_unc(canonical_path, nas_unc)
                # Prefer targeting the primary archive (correct icon, opens
                # the zip directly). Fall back to the folder if primary
                # isn't a single file (e.g. uncompressed series/ or the
                # folder-as-primary MRI layout).
                primary = cfg_single.get("primary_file_name", "")
                primary_kind = cfg_single.get("primary_kind", "")
                if primary and primary_kind == "folder":
                    # MRI folder layout: primary IS the acquisition folder
                    # itself. Target the folder UNC; double-clicking opens
                    # Explorer at the acq directory.
                    target_unc = folder_unc + "\\"
                elif primary and not primary.endswith("/"):
                    target_unc = f"{folder_unc}\\{primary}"
                else:
                    target_unc = folder_unc + "\\"
                # The .lnk filename is operator-controlled via the new
                # `link_filename:` top-level YAML field (see
                # resolver.resolve_link_filename). Per-instrument templates
                # set a meaningful default; per-batch configs may override.
                # Falls back to `original_name` when the field is unset —
                # preserves backward compatibility with rounds 1-2 / 4 / 5.
                link_template = cfg_single.get("link_filename") or ""
                lnk_name = None
                if link_template:
                    lnk_name = resolver.resolve_link_filename(
                        link_template, cfg_single, acq_id_str, acq_date,
                    )
                    if lnk_name:
                        # Trailing slash is allowed in the template as a
                        # visual hint ("this links to a folder") but the
                        # `.lnk` extension is appended by linker.create_lnk
                        # so we strip the slash here.
                        lnk_name = lnk_name.rstrip("/").rstrip("\\")
                if not lnk_name:
                    lnk_name = original_name
                try:
                    lnk_path = linker.create_lnk(
                        project_folder_abs,
                        lnk_name,
                        target_unc,
                        description=f"{acq_id_str} ({original_name})",
                        dry_run=False,
                    )
                    log(f"Created shortcut: {lnk_path} -> {target_unc}")
                    # Provenance log entry for the .lnk just created.
                    # Idempotent on output_path: skips silently if the
                    # project's provenance.csv already has a row for
                    # this shortcut (self-heals if the .lnk existed but
                    # the entry was missing).
                    prov_path = os.path.join(project_folder_abs, "provenance.csv")
                    lnk_filename = f"{lnk_name}.lnk"
                    entry = {
                        "output_path":         f"raw_linked/{lnk_filename}",
                        "output_name":         lnk_filename,
                        "file_type":           ".lnk",
                        "date_created":        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "creator":             cfg_single.get("operator", "") or "",
                        "input_refs":          acq_id_str,
                        "process_description": "Auto-created during ingest: Windows .lnk shortcut to raw acquisition",
                        "software_version":   provenance.software_version_string("ingest_raw.py"),
                        "parameters_ref":      cfg_single.get("ingest_config", "") or "",
                        "lab_notebook_ref":    "",
                        "notes":               "Auto-generated entry from ingest",
                    }
                    fid = provenance.append_entry(prov_path, entry)
                    if fid:
                        log(f"Appended provenance entry {fid} to {prov_path}")
                except RuntimeError as e:
                    log(f"Could not create .lnk: {e}", "WARN")
                except Exception as e:
                    log(f"Unexpected error creating .lnk: {e}", "WARN")

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
    nas_unc = args.nas_unc or None  # empty string -> disable .lnk creation
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
    if nas_unc:
        log(f"NAS UNC:  {nas_unc} (used for .lnk shortcut targets)")
    else:
        log(".lnk shortcut creation disabled (--nas-unc empty)")

    if args.dry_run:
        log("*** DRY RUN MODE — no changes will be made ***")

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
