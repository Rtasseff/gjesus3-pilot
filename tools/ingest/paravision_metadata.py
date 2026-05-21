"""Bruker ParaVision metadata extractor.

Mirrors the public shape of `czi_metadata.py`:

  load_paravision_exam(exam_path)  -> dict   (parsed JCAMP-DX bundle)
  build_mri_section(md)            -> dict   (structured sidecar block)
  build_discovered_subset(md)      -> dict   (curated discovered.mri_* fields)
  extract(exam_path)               -> tuple  ((discovered, mri_section))

Input: a path to one ParaVision examination folder (e.g.
`.../<study>/29/`). The study-level `subject` file is read from the
exam's parent. Per-reconstruction `visu_pars` + `reco` files are read
from `pdata/<idx>/` subfolders for every reconstruction index present.

Output `discovered.mri_*` is a flat dict referenceable from YAML
`registry:` blocks (one column = one resolved value). The `mri:`
section is the structured block for the on-disk sidecar.
"""

import re
from pathlib import Path

from . import jcampdx


# ParaVision version is encoded in the JCAMP-DX TITLE line, e.g.
# `Parameter List, ParaVision 7.0.0`.
_PV_VERSION = re.compile(r"ParaVision\s+(\S+)")


# ------------------------------------------------------------------ loader

def load_paravision_exam(exam_path):
    """Parse all relevant JCAMP-DX files for one ParaVision exam.

    Returns a nested dict:
      {
        "subject":   {...},   # parsed study-root /subject (may be {})
        "acqp":      {...},   # parsed <exam>/acqp        (may be {})
        "method":    {...},   # parsed <exam>/method      (may be {})
        "visu_pars": {...},   # parsed <exam>/visu_pars   (may be {})
        "pdata":     {idx: {"visu_pars": {...}, "reco": {...}}, ...},
        "_paths": {           # source paths for the dump (useful for probes)
          "exam_path":  ...,
          "study_path": ...,
        }
      }
    """
    exam = Path(exam_path)
    study = exam.parent

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
            md["pdata"][idx] = {
                "visu_pars": jcampdx.parse_file(sub / "visu_pars"),
                "reco":      jcampdx.parse_file(sub / "reco"),
            }
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
    out = {
        "indices_present": sorted(
            md.get("pdata", {}).keys(),
            key=lambda x: int(x) if x.isdigit() else x,
        ),
        "by_index": {},
    }
    for idx, p in md.get("pdata", {}).items():
        reco = p.get("reco", {})
        vp = p.get("visu_pars", {})
        out["by_index"][idx] = {
            "reco_mode":             reco.get("RECO_mode", ""),
            "fov":                   reco.get("RECO_fov", ""),
            "size":                  reco.get("RECO_size", ""),
            "frame_count":           vp.get("VisuCoreFrameCount", ""),
            "data_min":              vp.get("VisuCoreDataMin", ""),
            "data_max":              vp.get("VisuCoreDataMax", ""),
            "frame_type":            vp.get("VisuCoreFrameType", ""),
            "frame_group_elem_desc": vp.get("VisuFGElemComment", ""),
        }
    return out


# ------------------------------------------------------------------ public API

def build_mri_section(md):
    """Build the structured `mri:` block for the sidecar.

    Four curated buckets at the top for human skimming, plus
    `_raw_metadata` containing the full parsed JCAMP-DX dump for
    forensic preservation. If a curated field is empty here, it's still
    recoverable from `_raw_metadata` without re-reading the source.
    """
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
            "pdata":     md.get("pdata", {}),
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


def extract(exam_path):
    """One-shot: read a ParaVision exam folder, return (discovered, mri_section).

    `exam_path` should point at one ParaVision Examination Entry folder
    (e.g. `.../<study>/29/`). The `subject` file is read from the exam's
    parent; per-reconstruction `visu_pars` + `reco` are read from any
    `pdata/<idx>/` subfolders present.
    """
    md = load_paravision_exam(exam_path)
    return build_discovered_subset(md), build_mri_section(md)
