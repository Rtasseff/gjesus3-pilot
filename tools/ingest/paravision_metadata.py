"""Bruker ParaVision metadata extractor.

Mirrors the public shape of `ni_metadata.py` (round-6 v2 2026-05-27):

  load_paravision_exam(exam_path)  -> dict   (parsed JCAMP-DX bundle + per-DICOM headers)
  build_mri_section(md)            -> dict   (structured sidecar block)
  build_discovered_subset(md)      -> dict   (curated discovered.mri_* fields)
  extract(exam_path)               -> tuple  ((discovered, mri_section, "mri"))

Input: a path to one ParaVision examination folder (e.g.
`.../<study>/29/`). The study-level `subject` file is read from the
exam's parent. Per-reconstruction `visu_pars` + `reco` files are read
from `pdata/<idx>/` subfolders for every reconstruction index present.
Per-frame DICOMs at `pdata/<idx>/dicom/MRIm<NN>.dcm` are inventoried
and their curated headers (with `StudyInstanceUID`/`SeriesInstanceUID`/
`SOPInstanceUID` first) are pulled into the sidecar.

Output `discovered.mri_*` is a flat dict referenceable from YAML
`registry:` blocks (one column = one resolved value). The `mri:`
section is the structured block for the on-disk sidecar.

The 3-tuple `extract()` return form lets the DICOM ecosystem dispatcher
override the sidecar section name — ParaVision data lives under
`metadata.json.mri` even though the ecosystem is DICOM (parsed
ParaVision-specific content rather than generic DICOM headers).
"""

import os
import re
from pathlib import Path

from . import jcampdx

# pydicom is optional — degrades gracefully to skipping per-DICOM
# header capture if missing.
try:
    import pydicom
    _HAS_PYDICOM = True
except ImportError:
    _HAS_PYDICOM = False


# ParaVision version is encoded in the JCAMP-DX TITLE line, e.g.
# `Parameter List, ParaVision 7.0.0`.
_PV_VERSION = re.compile(r"ParaVision\s+(\S+)")


# Bruker exports per-frame DICOMs as `MRIm<NN>.dcm` (typically NN is 1-2
# digits, zero-padded to 2). Extract NN to use in the flat destination
# name `recon<idx>_frame<NN>.dcm`.
_BRUKER_DCM_NAME = re.compile(r"^MRIm(?P<n>\d+)\.dcm$", re.IGNORECASE)


# Curated DICOM tag list for per-DICOM `headers` bucket. UIDs first
# (critical for XNAT/PACS interop). MRI-specific tags (field strength,
# echo / repetition time, flip angle, scanning sequence) come from
# Bruker's own DICOM exporter and are useful for distinguishing
# sequences. ~30 tags total; modest sidecar weight.
_DICOM_CURATED_TAGS = [
    # --- Identity (DICOM UIDs — required for tool interop) ---
    "StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID",
    # --- Instrument / acquisition ---
    "Modality", "Manufacturer", "ManufacturerModelName",
    "SeriesDescription", "ProtocolName", "StudyDescription",
    # NB: Bruker GUI export sets SeriesDescription = per-recon descriptive
    # (e.g. "Cine_slice_1_12") and ProtocolName = method name
    # (e.g. "Cine_IG_FLASH"). Dicomifier 2.5.3 swaps them. Carrying both
    # in the sidecar lets downstream consumers pick whichever convention
    # they expect. See tasks/tasks.md §3.1 findings (2).
    "StudyDate", "StudyTime", "AcquisitionDate", "AcquisitionTime",
    "SeriesDate", "SeriesTime",
    # --- Image shape ---
    "ImageType", "Rows", "Columns", "NumberOfFrames",
    "PixelSpacing", "SliceThickness", "SpacingBetweenSlices",
    "InstanceNumber",
    # --- Subject ---
    "PatientID", "PatientName", "PatientSex", "PatientWeight",
    # --- MRI-specific (from Bruker DICOM exporter) ---
    "MagneticFieldStrength", "EchoTime", "RepetitionTime",
    "FlipAngle", "ScanningSequence", "SequenceVariant",
    "InversionTime", "NumberOfAverages",
]


def _read_dicom_headers(dcm_path):
    """Read a DICOM file and return a curated dict of its top-level tags.

    Uses pydicom if available; gracefully returns {} otherwise (the
    sidecar block survives without it — the .dcm file is on the NAS and
    full headers are recoverable later via pydicom.dcmread).
    """
    if not _HAS_PYDICOM:
        return {}
    try:
        ds = pydicom.dcmread(str(dcm_path), stop_before_pixels=True)
    except Exception:
        return {}
    out = {}
    for tag in _DICOM_CURATED_TAGS:
        if tag in ds:
            val = ds.get(tag, "")
            if isinstance(val, (int, float, str, list, dict)):
                out[tag] = val
            else:
                out[tag] = str(val)
    return out


def _plan_dcm_target(src_path, pdata_root, recon_idx):
    """Compute the new flat filename for a Bruker DICOM, given its source location.

    Source layout: `<pdata_root>/dicom/MRIm<NN>.dcm` where pdata_root is
    `<exam>/pdata/<idx>/`. Returns 'recon<idx>_frame<NN>.dcm' preserving
    Bruker's zero-padded NN. Falls back to 'recon<idx>_<basename>' for
    non-`MRIm`-prefixed DICOMs (defensive — emit a sensible name + the
    caller WARNs).

    The iteration count is dropped from the destination filename — it's
    fixed at the ParaVision recon level and preserved in
    `_raw_metadata.pdata.<idx>.reco`.
    """
    fname = src_path.name
    m = _BRUKER_DCM_NAME.match(fname)
    if m:
        # Zero-pad to 2 digits min; preserve more digits if present (rare).
        n_str = m.group("n")
        n_padded = n_str.zfill(2) if len(n_str) < 2 else n_str
        return f"recon{recon_idx}_frame{n_padded}.dcm"
    # Defensive fallback: keep the basename, prefix with recon<idx>_.
    return f"recon{recon_idx}_{fname}"


def _normalize_reconstructions(reconstructions):
    """Normalize the `reconstructions:` YAML flag to a set of string indices.

    Accepts:
      - None or 'all' or '' → None (means "keep all present")
      - int (e.g. 3) → {'3'}
      - list of ints (e.g. [1, 3]) → {'1', '3'}
      - list of strings → {'1', '3'}
      - string number → {'3'}
    """
    if reconstructions is None:
        return None
    if isinstance(reconstructions, str):
        if reconstructions.strip().lower() in ("", "all"):
            return None
        # Single string like '3'
        return {reconstructions.strip()}
    if isinstance(reconstructions, int):
        return {str(reconstructions)}
    if isinstance(reconstructions, (list, tuple, set)):
        return {str(x).strip() for x in reconstructions}
    raise ValueError(
        f"Invalid reconstructions value: {reconstructions!r} "
        f"(expected 'all', int, or list of ints)"
    )


# ------------------------------------------------------------------ loader

def load_paravision_exam(exam_path, reconstructions=None):
    """Parse all relevant JCAMP-DX files + inventory per-frame DICOMs for one ParaVision exam.

    Args:
        exam_path: path to a ParaVision examination folder (e.g. `<study>/29/`).
        reconstructions: which pdata/<idx>/ recons to inventory DICOMs for.
            None or 'all' → every present idx. Int / list-of-ints → only those.
            Indices NOT selected still get their JCAMP-DX parsed (cheap), but
            their `dicoms[]` list stays empty (caller knows not to copy).

    Returns a nested dict:
      {
        "subject":   {...},   # parsed study-root /subject (may be {})
        "acqp":      {...},   # parsed <exam>/acqp        (may be {})
        "method":    {...},   # parsed <exam>/method      (may be {})
        "visu_pars": {...},   # parsed <exam>/visu_pars   (may be {})
        "pdata":     {
          "1": {
            "visu_pars": {...},
            "reco":      {...},
            "dicoms": [
              {
                "src_relpath":  "pdata/1/dicom/MRIm01.dcm",
                "dst_basename": "recon1_frame01.dcm",
                "headers":      {curated DICOM tag dict},
              },
              ...
            ],
            "unrecognized_dicoms": ["<src_relpath>", ...],   # rare; defensive
            "selected": True,    # whether this recon was selected via `reconstructions:`
          },
          ...
        },
        "_paths": {
          "exam_path":  ...,
          "study_path": ...,
        }
      }

    The `dicoms[]` list is what the ingest copy function consumes —
    each entry has a planned flat filename to write under `<ACQ-ID>.data/`.
    For no-DICOM acquisitions (students who didn't run Bruker's exporter):
    all `dicoms[]` lists are empty; the caller creates an empty `.data/`
    folder + writes an empty checksums.json.
    """
    exam = Path(exam_path)
    study = exam.parent
    keep = _normalize_reconstructions(reconstructions)

    md = {
        "subject":   jcampdx.parse_file(study / "subject"),
        "acqp":      jcampdx.parse_file(exam / "acqp"),
        "method":    jcampdx.parse_file(exam / "method"),
        "visu_pars": jcampdx.parse_file(exam / "visu_pars"),
        "pdata":     {},
        "_paths": {
            "exam_path":  str(exam),
            "study_path": str(study),
        },
    }

    pdata_root = exam / "pdata"
    if pdata_root.is_dir():
        for sub in sorted(pdata_root.iterdir()):
            if not sub.is_dir():
                continue
            idx = sub.name
            selected = (keep is None) or (idx in keep)
            entry = {
                "visu_pars": jcampdx.parse_file(sub / "visu_pars"),
                "reco":      jcampdx.parse_file(sub / "reco"),
                "dicoms":              [],
                "unrecognized_dicoms": [],
                "selected":            selected,
            }
            # Inventory per-frame DICOMs ONLY for selected recons. Unselected
            # recons' JCAMP-DX still gets parsed (we want their existence
            # in `_raw_metadata.pdata.<idx>`) but no DICOM-header reads.
            if selected:
                dicom_dir = sub / "dicom"
                if dicom_dir.is_dir():
                    for dcm in sorted(dicom_dir.iterdir()):
                        if not (dcm.is_file() and dcm.suffix.lower() == ".dcm"):
                            continue
                        dst = _plan_dcm_target(dcm, sub, idx)
                        rel = str(dcm.relative_to(exam)).replace(os.sep, "/")
                        if dst.startswith(f"recon{idx}_frame"):
                            entry["dicoms"].append({
                                "src_relpath":  rel,
                                "dst_basename": dst,
                                "headers":      _read_dicom_headers(dcm),
                            })
                        else:
                            # Non-MRIm-prefixed DICOM — keep but flag
                            entry["unrecognized_dicoms"].append(rel)
                            entry["dicoms"].append({
                                "src_relpath":  rel,
                                "dst_basename": dst,  # fallback recon<idx>_<basename>
                                "headers":      _read_dicom_headers(dcm),
                            })
            md["pdata"][idx] = entry
    return md


# ------------------------------------------------------------------ helpers

def _g(d, *keys):
    """Walk nested dict; return '' on any missing step."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return ""
        cur = cur[k]
    return cur if cur is not None else ""


def _paravision_version(md):
    """Pull the ParaVision version out of any of the parsed-file TITLE lines."""
    for src in ("visu_pars", "acqp", "method", "subject"):
        title = _g(md, src, "TITLE")
        if isinstance(title, str):
            m = _PV_VERSION.search(title)
            if m:
                return m.group(1)
    return ""


def _exam_number(md):
    """Exam number from the exam folder name (numeric only)."""
    p = _g(md, "_paths", "exam_path")
    if not p:
        return ""
    name = Path(p).name
    return name if name.isdigit() else ""


def _matrix_str(md):
    """Return the matrix dimensions as 'NxM' (or just 'N' for 1D)."""
    m = _g(md, "method", "PVM_Matrix")
    if isinstance(m, list):
        return "x".join(str(int(v)) if isinstance(v, (int, float)) else str(v) for v in m)
    if isinstance(m, (int, float)):
        return str(int(m))
    return ""


def _fov_str(md):
    """Return the FOV dimensions as 'NxM' (units typically mm or cm — see PVM_SPackArrSliceOrient)."""
    fov = _g(md, "method", "PVM_Fov")
    if isinstance(fov, list):
        return "x".join(str(v) for v in fov)
    if isinstance(fov, (int, float)):
        return str(fov)
    return ""


def _recon_indices(md):
    """Comma-separated list of pdata/<idx>/ reconstruction indices present."""
    indices = sorted(md.get("pdata", {}).keys(),
                     key=lambda x: int(x) if x.isdigit() else x)
    return ",".join(indices)


# ------------------------------------------------------------------ buckets

def _build_subject(md):
    s = md.get("subject", {})
    return {
        "id":             s.get("SUBJECT_id", ""),
        "name":           s.get("SUBJECT_name", ""),
        "study_name":     s.get("SUBJECT_study_name", ""),
        "type":           s.get("SUBJECT_type", ""),
        "sex":            s.get("SUBJECT_sex", ""),
        "birth_date":     s.get("SUBJECT_dbirth", ""),
        "weight":         s.get("SUBJECT_weight", ""),
        "position":       s.get("SUBJECT_position", ""),
        "entry":          s.get("SUBJECT_entry", ""),
        "study_datetime": s.get("SUBJECT_date", ""),
        "referral":       s.get("SUBJECT_referral", ""),
        "instance_uid":   s.get("SUBJECT_instance_uid", ""),
    }


def _build_acquisition(md):
    acqp = md.get("acqp", {})
    method = md.get("method", {})
    vp = md.get("visu_pars", {})
    return {
        "method":           method.get("Method", ""),
        "pulse_program":    acqp.get("PULPROG", ""),
        "creation_datetime": vp.get("VisuCreationDate", ""),
        "echo_time_ms":     method.get("PVM_EchoTime", ""),
        "repetition_time_ms": method.get("PVM_RepetitionTime", ""),
        "averages":         method.get("PVM_NAverages", ""),
        "repetitions":      method.get("PVM_NRepetitions", ""),
        "scan_time_str":    method.get("PVM_ScanTimeStr", ""),
        "scan_time_ms":     method.get("PVM_ScanTime", ""),
        "nucleus":          method.get("PVM_Nucleus1", ""),
        "frequency_mhz":    method.get("PVM_FrqRef", [""])[0] if isinstance(method.get("PVM_FrqRef"), list) else method.get("PVM_FrqRef", ""),
        "receiver_gain":    acqp.get("RG", ""),
        "frame_count":      vp.get("VisuCoreFrameCount", ""),
        "frame_group_desc": vp.get("VisuFGOrderDesc", ""),
    }


def _build_geometry(md):
    method = md.get("method", {})
    vp = md.get("visu_pars", {})
    return {
        "spatial_dim":      method.get("PVM_SpatDimEnum", ""),
        "matrix":           method.get("PVM_Matrix", ""),
        "fov":              method.get("PVM_Fov", ""),
        "slice_thickness":  vp.get("VisuCoreFrameThickness", ""),
        "core_dim":         vp.get("VisuCoreDim", ""),
        "core_size":        vp.get("VisuCoreSize", ""),
        "core_extent":      vp.get("VisuCoreExtent", ""),
        "core_units":       vp.get("VisuCoreUnits", ""),
        "orientation":      vp.get("VisuCoreOrientation", ""),
        "position":         vp.get("VisuCorePosition", ""),
    }


def _build_reconstruction(md):
    """Per-recon summary: present indices + per-recon params + per-DICOM headers.

    Mirrors the NI v2.1 shape: each kept recon has a `dicoms[]` list of
    {dst_basename, src_relpath, headers} entries. UIDs are first in each
    headers dict.
    """
    indices = sorted(
        md.get("pdata", {}).keys(),
        key=lambda x: int(x) if x.isdigit() else x,
    )
    out = {
        "indices_present": indices,
        "by_index": {},
    }
    for idx in indices:
        p = md["pdata"][idx]
        reco = p.get("reco", {})
        vp = p.get("visu_pars", {})
        bucket = {
            # Per-recon parameters from the JCAMP-DX. Pluck a few useful
            # keys for human skimming; full set preserved in
            # `_raw_metadata.pdata.<idx>`.
            "reco_mode":             reco.get("RECO_mode", ""),
            "fov":                   reco.get("RECO_fov", ""),
            "size":                  reco.get("RECO_size", ""),
            "frame_count":           vp.get("VisuCoreFrameCount", ""),
            "data_min":              vp.get("VisuCoreDataMin", ""),
            "data_max":              vp.get("VisuCoreDataMax", ""),
            "frame_type":            vp.get("VisuCoreFrameType", ""),
            "frame_group_elem_desc": vp.get("VisuFGElemComment", ""),
            "selected":              p.get("selected", False),
            # Per-DICOM headers list. Empty if this recon wasn't selected
            # via `reconstructions:`, or if Bruker's DICOM exporter wasn't
            # run (the no-DICOM acquisition case — see workflow notes).
            "dicoms": [
                {
                    "dst_basename": d["dst_basename"],
                    "src_relpath":  d["src_relpath"],
                    "headers":      d["headers"],
                }
                for d in p.get("dicoms") or []
            ],
        }
        if p.get("unrecognized_dicoms"):
            bucket["unrecognized_dicom_paths"] = p["unrecognized_dicoms"]
        out["by_index"][idx] = bucket
    return out


# ------------------------------------------------------------------ public API

def build_mri_section(md):
    """Build the structured `mri:` block for the sidecar.

    Four curated buckets at the top for human skimming + per-DICOM
    `dicoms[]` list under each kept recon (UIDs first), plus
    `_raw_metadata` containing the parsed JCAMP-DX dump for forensic
    preservation. The source aux files (acqp/method/visu_pars/subject)
    are NOT copied to disk — the parsed dicts here are the gjesus3
    preservation surface. If a curated field is empty here, it's still
    recoverable from `_raw_metadata` without re-reading the source.
    """
    # The pdata _raw_metadata strips the per-DICOM `dicoms`/`unrecognized_dicoms`
    # / `selected` keys — those are runtime planning info, not source content.
    # The kept keys are the parsed JCAMP-DX (visu_pars, reco).
    pdata_raw = {}
    for idx, p in (md.get("pdata") or {}).items():
        pdata_raw[idx] = {
            "visu_pars": p.get("visu_pars", {}),
            "reco":      p.get("reco", {}),
        }
    return {
        "subject":        _build_subject(md),
        "acquisition":    _build_acquisition(md),
        "geometry":       _build_geometry(md),
        "reconstruction": _build_reconstruction(md),
        "_raw_metadata":  {
            "subject":   md.get("subject", {}),
            "acqp":      md.get("acqp", {}),
            "method":    md.get("method", {}),
            "visu_pars": md.get("visu_pars", {}),
            "pdata":     pdata_raw,
        },
    }


# Curated subset surfaced as `discovered.mri_*` so YAML configs can
# reference them. Each entry: (discovered_key, getter_fn(md) -> str|number,
# human-readable description). Adding a field here means adding a row
# to the table in 09_MODALITIES.md MRI section (per CLAUDE.md cross-ref rule).
EXPOSED_FIELDS = [
    ("mri_study_name",
        lambda md: _g(md, "subject", "SUBJECT_study_name"),
        "Study name from the ParaVision study-root subject file (e.g. 'jrc_251016_m17_0424')"),
    ("mri_animal_id",
        lambda md: _g(md, "subject", "SUBJECT_id"),
        "Subject/animal ID (typically matches study name in MFB convention)"),
    ("mri_animal_sex",
        lambda md: _g(md, "subject", "SUBJECT_sex"),
        "Animal sex from the subject file"),
    ("mri_animal_weight",
        lambda md: _g(md, "subject", "SUBJECT_weight"),
        "Animal weight (units per platform — typically kg in ParaVision)"),
    ("mri_animal_type",
        lambda md: _g(md, "subject", "SUBJECT_type"),
        "Animal type / category (e.g. 'Quadruped')"),
    ("mri_position",
        lambda md: _g(md, "subject", "SUBJECT_position"),
        "Animal positioning in scanner (e.g. 'SUBJ_POS_Supine')"),
    ("mri_study_datetime",
        lambda md: _g(md, "subject", "SUBJECT_date"),
        "Study start datetime from the subject file (ParaVision local time)"),
    ("mri_paravision_version",
        lambda md: _paravision_version(md),
        "ParaVision version that produced the data (e.g. '7.0.0')"),
    ("mri_exam_number",
        lambda md: _exam_number(md),
        "ParaVision Examination Entry number (the exam folder name)"),
    ("mri_acquisition_datetime",
        lambda md: _g(md, "visu_pars", "VisuCreationDate"),
        "Per-exam creation datetime from visu_pars (when the recon ran)"),
    ("mri_modality",
        lambda md: _g(md, "visu_pars", "VisuInstanceModality"),
        "DICOM-style modality code from visu_pars (typically 'MR')"),
    ("mri_sequence_name",
        lambda md: _g(md, "method", "Method"),
        "Bruker method / sequence name (e.g. 'Bruker:IgFLASH')"),
    ("mri_pulse_program",
        lambda md: _g(md, "acqp", "PULPROG"),
        "Pulse program file from acqp (e.g. 'IgFLASH.ppg')"),
    ("mri_nucleus",
        lambda md: _g(md, "method", "PVM_Nucleus1"),
        "Primary nucleus (e.g. '1H')"),
    ("mri_echo_time_ms",
        lambda md: _g(md, "method", "PVM_EchoTime"),
        "Echo time TE in ms"),
    ("mri_repetition_time_ms",
        lambda md: _g(md, "method", "PVM_RepetitionTime"),
        "Repetition time TR in ms"),
    ("mri_scan_time_str",
        lambda md: _g(md, "method", "PVM_ScanTimeStr"),
        "Human-readable scan duration (e.g. '0h3m17s865ms')"),
    ("mri_matrix",
        lambda md: _matrix_str(md),
        "Acquisition matrix as 'NxM' (e.g. '256x128')"),
    ("mri_frame_count",
        lambda md: _g(md, "visu_pars", "VisuCoreFrameCount"),
        "Number of frames in the reconstructed image (slices / cardiac frames / etc.)"),
    ("mri_recon_indices",
        lambda md: _recon_indices(md),
        "Comma-separated list of pdata/<idx>/ reconstructions present (e.g. '1,3')"),
]


def build_discovered_subset(md):
    """Pluck the curated `discovered.mri_*` dict from the parsed JCAMP-DX."""
    return {key: fn(md) for key, fn, _desc in EXPOSED_FIELDS}


def extract(exam_path, reconstructions=None):
    """One-shot: read a ParaVision exam folder, return (discovered, mri_section, 'mri').

    Args:
        exam_path: path to one ParaVision Examination Entry folder
            (e.g. `.../<study>/29/`).
        reconstructions: which pdata/<idx>/ recons to inventory DICOMs
            for. None or 'all' → every present idx. Int / list-of-ints
            → only those. The unselected recons still get their
            JCAMP-DX parsed for `_raw_metadata`, but their per-DICOM
            `dicoms[]` lists stay empty (caller knows not to copy).

    Returns a 3-tuple `(discovered, mri_section, 'mri')` so the DICOM
    ecosystem dispatcher (`config._extract_dicom_embedded`) overrides
    the sidecar section name. ParaVision content lives under
    `metadata.json.mri`, not the generic `dicom:` block.
    """
    md = load_paravision_exam(exam_path, reconstructions=reconstructions)
    return build_discovered_subset(md), build_mri_section(md), "mri"
