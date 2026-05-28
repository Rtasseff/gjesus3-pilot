"""Molecubes Nuclear Imaging metadata extractor.

Mirrors the public shape of `paravision_metadata.py` and `czi_metadata.py`:

  load_ni_acquisition(folder)     -> dict   (parsed bundle: protocol.txt + XMLs + DICOM headers)
  build_ni_section(md)            -> dict   (structured sidecar `ni:` block)
  build_discovered_subset(md)     -> dict   (curated discovered.ni_* dict)
  extract(folder)                 -> tuple  ((discovered, ni_section, "ni"))

Input: a path to one extracted Molecubes acquisition folder (e.g.
`D:/projects/Nuke/test_data/irene_0525_251029_0525_m13_20251029101558_CT/`).
Folder must contain `protocol.txt` at the root and at least one
`recon_<idx>/` subfolder; otherwise the extractor returns empties.

Output `discovered.ni_*` is a flat dict referenceable from YAML
`registry:` blocks (one column = one resolved value). The `ni:`
section is the structured block for the on-disk sidecar.

The 3-tuple `extract()` return form lets the DICOM ecosystem dispatcher
override the sidecar section name — NI data lives under
`metadata.json.ni` even though the ecosystem is DICOM (Molecubes-
specific content; ParaVision data uses the same trick to land at
`metadata.json.mri`).
"""

import os
import re
from pathlib import Path

from . import ni_xml

# pydicom is optional — degrades gracefully to skipping the DICOM-header
# bucket if missing.
try:
    import pydicom
    _HAS_PYDICOM = True
except ImportError:
    _HAS_PYDICOM = False


# ------------------------------------------------------------------ heuristics

def is_ni_acquisition(path):
    """Heuristic: does this folder look like a Molecubes NI acquisition?

    Two required signals:
      - `protocol.txt` at the folder root (the human-readable protocol)
      - at least one `recon_<idx>/` subfolder (the reconstruction(s))

    Used by `config._extract_dicom_embedded` to dispatch the right
    extractor. Together with the analogous ParaVision check, the DICOM
    ecosystem ends up with two content-detected source shapes; anything
    else (collaborator XMRI zips) falls through to the empty extractor.
    """
    p = Path(path)
    if not p.is_dir():
        return False
    if not (p / "protocol.txt").is_file():
        return False
    for entry in p.iterdir():
        if entry.is_dir() and entry.name.startswith("recon_"):
            return True
    return False


# ------------------------------------------------------------------ protocol.txt parser

# matches "Scan bed position from <X> to <Y>" — the one protocol.txt
# line that isn't a plain `key: value`.
_BED_POS_RE = re.compile(
    r"Scan bed position from\s+(?P<begin>\S+)\s+to\s+(?P<end>\S+)"
)


def parse_protocol_txt(path):
    """Parse a Molecubes `protocol.txt` into a flat {key: value} dict.

    Parses EVERY non-blank line (no allowlist), splitting on the first
    colon. The bed-position line is special-cased (no colon — encoded
    as a sentence) into two keys.

    Keys are preserved verbatim from the source file (e.g. "Study name",
    "Animal weight (g)", "Date/time"). The matching `EXPOSED_FIELDS`
    getters use these verbatim strings — keep them in sync if upstream
    Molecubes changes a label.

    Returns {} if the file doesn't exist.
    """
    p = Path(path)
    if not p.is_file():
        return {}
    raw = p.read_text(encoding="utf-8", errors="replace")
    out = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # Special: bed position line ("Scan bed position from X to Y" —
        # no colon, encoded as a sentence). Split into two verbatim-keyed
        # entries so the curated bucket can read them by name.
        m = _BED_POS_RE.search(line)
        if m:
            out["Scan bed position from"] = m.group("begin")
            out["Scan bed position to"] = m.group("end")
            continue
        # Regular "key: value" lines. partition() handles the
        # "Injected at : ..." case (space before colon) cleanly because
        # we strip both sides afterwards.
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip()
    return out


# ------------------------------------------------------------------ loader

# Frame folder name pattern: `frame_<digits>` or `frame_<word>` (rare).
_FRAME_DIR_RE = re.compile(r"^frame_(?P<idx>[A-Za-z0-9]+)$")


def _plan_dcm_target(src_path, recon_root, recon_idx):
    """Compute the new flat filename for a DICOM, given its source location.

    Returns dst_basename (or empty string if the file doesn't match any
    known layout — ingest skips those with WARN).

    Layout rules:
      - Direct under recon_<idx>/ with 'frameMULTI' in filename → 'recon<X>_frameMULTI.dcm'
        (PET/SPECT dynamic — the platform-generated bundled DICOM holding
        all frames in one file; kept alongside the per-frame DICOMs)
      - Direct under recon_<idx>/<basename>.dcm (no 'frameMULTI' in name) → 'recon<X>.dcm'
        (CT path)
      - Under recon_<idx>/frame_<Y>/iter_<N>/<basename>.dcm → 'recon<X>_frame<Y>.dcm'
        (PET/SPECT per-frame path)

    The iteration count (typically 30) is dropped from the destination
    filename — captured in metadata.json's reconparams_xml instead.
    """
    fname = src_path.name
    rel = src_path.relative_to(recon_root)
    parts = rel.parts  # e.g. ('frame_1', 'iter_30', '<basename>.dcm') or ('<basename>.dcm',)
    if len(parts) == 1:
        # Direct under recon_<idx>/. Could be CT (a regular per-recon DICOM)
        # or PET/SPECT (a multi-frame bundled DICOM with 'frameMULTI' in
        # the filename, sibling to the per-frame frame_<Y>/iter_<N>/ tree).
        if "frameMULTI" in fname:
            return f"recon{recon_idx}_frameMULTI.dcm"
        return f"recon{recon_idx}.dcm"
    if len(parts) == 3:
        m = _FRAME_DIR_RE.match(parts[0])
        if m and parts[1].startswith("iter_"):
            return f"recon{recon_idx}_frame{m.group('idx')}.dcm"
    return ""


def load_ni_acquisition(folder_path):
    """Parse all relevant metadata sources for one NI acquisition folder.

    Returns a nested dict:
      {
        "protocol_txt":      {parsed key:value dict},
        "protocol_xml":      {parsed hierarchical dict},
        "acqparams_xml":     {flat key:value dict},
        "recontemplate_xml": {flat key:value dict},
        "recons": {
          "<idx>": {
            "reconparams_xml": {flat key:value dict},
            "dicoms": [
              {
                "src_relpath":  "recon_0/frame_0/iter_30/<basename>.dcm",
                "dst_basename": "recon0_frame0.dcm",
                "headers":      {curated DICOM tags},
              },
              ...
            ],
            "multi_frame_dicoms": [
              {
                "src_relpath": "recon_0/<basename>_frameMULTI_iter30.dcm",
                "headers":     {curated DICOM tags},
              },
              ...
            ],
            "unrecognized_dicoms": ["<src_relpath>", ...],  # rare; ingest skips with WARN
          },
        },
        "_paths": {"folder_path": "..."},
      }

    The `dicoms` list is what the ingest copy function consumes —
    each entry has a planned flat filename to write under
    `<ACQ-ID>.data/`. The `multi_frame_dicoms` list documents
    platform-generated bundled DICOMs that we do NOT copy (kept on
    the platform archive), but whose existence + headers are recorded
    in the sidecar for downstream tools / future migration.
    """
    folder = Path(folder_path)

    md = {
        "protocol_txt":      parse_protocol_txt(folder / "protocol.txt"),
        "protocol_xml":      ni_xml.parse_hierarchical(folder / "protocol.xml"),
        "acqparams_xml":     ni_xml.parse_flat_params(folder / "acqparams.xml"),
        "recontemplate_xml": ni_xml.parse_flat_params(folder / "recontemplate.xml"),
        "recons":            {},
        "_paths": {"folder_path": str(folder)},
    }

    for entry in sorted(folder.iterdir()):
        if not (entry.is_dir() and entry.name.startswith("recon_")):
            continue
        idx = entry.name.replace("recon_", "", 1)
        recon_info = {
            "reconparams_xml":     ni_xml.parse_flat_params(entry / "reconparams.xml"),
            "dicoms":              [],
            "unrecognized_dicoms": [],
        }
        for dcm_path in sorted(entry.rglob("*.dcm")):
            dst_basename = _plan_dcm_target(dcm_path, entry, idx)
            rel = str(dcm_path.relative_to(folder)).replace(os.sep, "/")
            if dst_basename:
                recon_info["dicoms"].append({
                    "src_relpath":  rel,
                    "dst_basename": dst_basename,
                    "headers":      _read_dicom_headers(dcm_path),
                })
            else:
                recon_info["unrecognized_dicoms"].append(rel)
        md["recons"][idx] = recon_info

    return md


# Curated DICOM tag list for the per-DICOM dicom_headers bucket.
# UIDs are first (critical for any DICOM-aware tool — XNAT, PACS,
# OMERO, etc. join data by these). Modest overall (~25 fields) so the
# sidecar doesn't balloon; we keep the .dcm files on the NAS so full
# headers are recoverable via pydicom.dcmread at any time.
_DICOM_CURATED_TAGS = [
    # --- Identity (DICOM UIDs — required for tool interop) ---
    "StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID",
    # --- Instrument / acquisition ---
    "Modality", "Manufacturer", "ManufacturerModelName",
    "SeriesDescription", "StudyDescription",
    "StudyDate", "StudyTime", "AcquisitionDate", "AcquisitionTime",
    "SeriesDate", "SeriesTime",
    # --- Image shape ---
    "ImageType", "Rows", "Columns", "NumberOfFrames",
    "PixelSpacing", "SliceThickness", "SpacingBetweenSlices",
    "ReconstructionDiameter", "Units",
    # --- Subject ---
    "PatientID", "PatientName", "PatientSex", "PatientWeight",
    # --- PET-specific ---
    "RadiopharmaceuticalInformationSequence",
]


def _read_dicom_headers(dcm_path):
    """Read a DICOM file and return a curated dict of its top-level tags.

    Uses pydicom if available; gracefully returns {} otherwise (the
    sidecar block survives without it — the .dcm file is on the NAS and
    full headers are recoverable later).
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
            # Avoid leaking pydicom objects into the sidecar JSON;
            # stringify anything non-primitive.
            if isinstance(val, (int, float, str, list, dict)):
                out[tag] = val
            else:
                out[tag] = str(val)
    return out


# ------------------------------------------------------------------ helpers

def _g(d, *keys):
    """Walk nested dict; return '' on any missing step."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return ""
        cur = cur[k]
    return cur if cur is not None else ""


def _strip_unit(s, *units):
    """Strip trailing units like ' MBq', ' seconds' from a value string.

    Returns the original string if no unit matched. Whitespace-only
    inputs return ''.
    """
    if not isinstance(s, str):
        return s
    s = s.strip()
    for u in units:
        if s.endswith(u):
            return s[: -len(u)].strip()
    return s


def _bool_str(s):
    """Parse a '0' / '1' / 'yes' / 'no' protocol.txt boolean to a Python bool.

    Returns None for empty/unknown — keeps the sidecar honest.
    """
    if not s:
        return None
    s = s.strip().lower()
    if s in ("yes", "true", "1"):
        return True
    if s in ("no", "false", "0"):
        return False
    return None


def _parse_protocol_datetime(s):
    """Parse 'YYYY-Mon-DD HH:MM:SS' from protocol.txt → ISO 8601 string.

    Example: '2025-Oct-29 10:15:58' → '2025-10-29T10:15:58'.
    Returns '' on parse failure (the verbatim source is preserved
    elsewhere — `_raw_metadata.protocol_txt`).
    """
    if not s:
        return ""
    import datetime as _dt
    fmt = "%Y-%b-%d %H:%M:%S"
    try:
        d = _dt.datetime.strptime(s.strip(), fmt)
    except (ValueError, TypeError):
        return ""
    return d.strftime("%Y-%m-%dT%H:%M:%S")


def _recons_present(md):
    """Comma-separated, sorted list of recon_<idx> indices present."""
    indices = sorted(md.get("recons", {}).keys(),
                     key=lambda x: int(x) if x.isdigit() else x)
    return ",".join(indices)


# ------------------------------------------------------------------ buckets

def _build_study(md):
    pt = md.get("protocol_txt", {})
    return {
        "study_name":             pt.get("Study name", ""),
        "series_name":            pt.get("Series name", ""),
        "principal_investigator": pt.get("Principal Investigator", ""),
        "modality":               pt.get("Modality", ""),
        "datetime":               _parse_protocol_datetime(pt.get("Date/time", "")),
        "datetime_raw":           pt.get("Date/time", ""),
    }


def _build_subject(md):
    pt = md.get("protocol_txt", {})
    weight_raw = pt.get("Animal weight (g)", "")
    try:
        weight_g = float(weight_raw) if weight_raw else None
    except (ValueError, TypeError):
        weight_g = None
    return {
        "animal_id": pt.get("Animal ID", ""),
        "weight_g":  weight_g,
    }


def _build_acquisition(md):
    pt = md.get("protocol_txt", {})
    return {
        "scan_protocol":      pt.get("Scan protocol", ""),
        "dose":               pt.get("Dose", ""),
        "bed_position_from":  pt.get("Scan bed position from", ""),
        "bed_position_to":    pt.get("Scan bed position to", ""),
        "record_respiratory": _bool_str(pt.get("Record respiratory signal", "")),
        "record_cardiac":     _bool_str(pt.get("Record cardiac signal", "")),
        # PET-only fields (empty for CT)
        "isotope":                       pt.get("Isotope", ""),
        "activity_MBq":                  _strip_unit(pt.get("Activity", ""), " MBq", "MBq"),
        "activity_calibrated_at":        pt.get("Activity calibrated at", ""),
        "remaining_activity_MBq":        _strip_unit(pt.get("Remaining activity", ""), " MBq", "MBq"),
        "remaining_activity_calibrated_at": pt.get("Remaining activity calibrated at", ""),
        "injected_at":                   pt.get("Injected at", ""),
        "n_frames":                      pt.get("Number of frames", ""),
        "scan_duration_s":               _strip_unit(pt.get("Scan duration", ""), " seconds", "seconds"),
    }


def _build_reconstruction(md):
    """Per-recon summary: present indices + per-index params + per-DICOM headers."""
    indices = sorted(md.get("recons", {}).keys(),
                     key=lambda x: int(x) if x.isdigit() else x)
    out = {
        "recons_present": indices,
        "by_index": {},
    }
    for idx in indices:
        r = md["recons"][idx]
        rp = r.get("reconparams_xml") or {}
        bucket = {
            # Per-recon parameters. Pluck a few useful keys out of
            # reconparams.xml for human skimming; full set preserved
            # in _raw_metadata.reconparams_by_idx.
            "algorithm":     rp.get("ReconstructionTemplate/algorithm", ""),
            "iterations":    rp.get("ReconstructionTemplate/iterations", ""),
            "voxel_size":    rp.get("ReconstructionTemplate/voxel_size", ""),
            "energy_peak":   rp.get("ReconstructionTemplate/energy_peak", ""),
            "energy_win":    rp.get("ReconstructionTemplate/energy_win", ""),
            "gatingtype":    rp.get("ReconstructionTemplate/gatingtype", ""),
            # Each DICOM kept on gjesus3 under <ACQ-ID>.data/. For each:
            # dst_basename is what the file is named on the NAS; headers
            # is the curated DICOM tag subset (UIDs first).
            "dicoms": [
                {
                    "dst_basename": d["dst_basename"],
                    "src_relpath":  d["src_relpath"],
                    "headers":      d["headers"],
                }
                for d in r.get("dicoms") or []
            ],
        }
        # Note: multi-frame DICOMs (filename contains 'frameMULTI') are
        # platform-generated bundled DICOMs (`ImageType=DYNAMIC`,
        # `NumberOfFrames` spanning all time frames) sitting at recon root
        # alongside the per-frame frame_<Y>/iter_<N>/ tree. They're kept
        # on gjesus3 alongside the per-frame DICOMs (named
        # `recon<X>_frameMULTI.dcm`) so analysis tools have both
        # representations available — see equipment/nuclear-imaging
        # workflow notes "Multi-frame DICOM" section for the rationale.
        # They appear in the regular `dicoms` list above.
        #
        # Unrecognized DICOM paths (defensive — should be empty in
        # practice but exposes structural surprises if Molecubes ever
        # changes their layout).
        if r.get("unrecognized_dicoms"):
            bucket["unrecognized_dicom_paths"] = r["unrecognized_dicoms"]
        out["by_index"][idx] = bucket
    return out


# ------------------------------------------------------------------ public API

def build_ni_section(md):
    """Build the structured `ni:` block for the sidecar.

    Four curated buckets at the top for human skimming, plus
    `_raw_metadata` containing the fully parsed source files (every
    XML aux + the parsed protocol.txt) for forensic preservation. The
    source acquisition_aux files are NOT copied to gjesus3 — the
    parsed structure here IS the on-NAS preservation. If a curated
    field is empty in the buckets, it's still recoverable from
    `_raw_metadata` without re-reading the platform archive.
    """
    return {
        "study":          _build_study(md),
        "subject":        _build_subject(md),
        "acquisition":    _build_acquisition(md),
        "reconstruction": _build_reconstruction(md),
        "_raw_metadata":  {
            # All four source files parsed into structured dicts. The
            # verbatim originals stay on the Molecubes archive only —
            # the structured forms here are the gjesus3 preservation
            # surface and feed every curated bucket above.
            "protocol_txt":       md.get("protocol_txt") or {},
            "protocol_xml":       md.get("protocol_xml") or {},
            "acqparams_xml":      md.get("acqparams_xml") or {},
            "recontemplate_xml":  md.get("recontemplate_xml") or {},
            "reconparams_by_idx": {
                idx: r.get("reconparams_xml") or {}
                for idx, r in (md.get("recons") or {}).items()
            },
        },
    }


# Curated subset surfaced as `discovered.ni_*` so YAML configs can
# reference them. Each entry: (discovered_key, getter_fn(md) -> str|number,
# human-readable description). Adding a field here means adding a row
# to the table in 09_MODALITIES.md NI section (per CLAUDE.md cross-ref
# rule).
EXPOSED_FIELDS = [
    ("ni_study_name",
        lambda md: _g(md, "protocol_txt", "Study name"),
        "Study name from protocol.txt (typically the funded-project id, e.g. '0525')"),
    ("ni_series_name",
        lambda md: _g(md, "protocol_txt", "Series name"),
        "Series name from protocol.txt (typically the acquisition-date short form)"),
    ("ni_pi",
        lambda md: _g(md, "protocol_txt", "Principal Investigator"),
        "PI from protocol.txt (often the operator's username — Molecubes labelling)"),
    ("ni_modality",
        lambda md: _g(md, "protocol_txt", "Modality"),
        "Modality reported by the platform: PET / CT / SPECT / OI"),
    ("ni_acquisition_datetime",
        lambda md: _parse_protocol_datetime(_g(md, "protocol_txt", "Date/time")),
        "ISO datetime from protocol.txt (e.g. '2025-10-29T10:15:58')"),
    ("ni_animal_id",
        lambda md: _g(md, "protocol_txt", "Animal ID"),
        "Animal ID from protocol.txt (e.g. '0525_m13' — combines short_project + short_sample)"),
    ("ni_animal_weight_g",
        lambda md: _g(md, "protocol_txt", "Animal weight (g)"),
        "Animal weight in grams (often '0' if not entered)"),
    ("ni_scan_protocol",
        lambda md: _g(md, "protocol_txt", "Scan protocol"),
        "Scan protocol name (e.g. 'spiral high-resolution')"),
    ("ni_bed_from",
        lambda md: _g(md, "protocol_txt", "Scan bed position from"),
        "Scan bed start position"),
    ("ni_bed_to",
        lambda md: _g(md, "protocol_txt", "Scan bed position to"),
        "Scan bed end position"),
    ("ni_isotope",
        lambda md: _g(md, "protocol_txt", "Isotope"),
        "Radioisotope (PET/SPECT only; empty for CT)"),
    ("ni_activity_mbq",
        lambda md: _strip_unit(_g(md, "protocol_txt", "Activity"), " MBq", "MBq"),
        "Injected activity in MBq (PET/SPECT only)"),
    ("ni_n_frames",
        lambda md: _g(md, "protocol_txt", "Number of frames"),
        "Number of time frames (PET only; static = 1)"),
    ("ni_scan_duration_s",
        lambda md: _strip_unit(_g(md, "protocol_txt", "Scan duration"), " seconds", "seconds"),
        "Scan duration in seconds (PET only)"),
    ("ni_recons_present",
        lambda md: _recons_present(md),
        "Comma-separated list of recon_<idx> subfolders found in the source (e.g. '0,1,2' for CT, '0' for PET)"),
]


def build_discovered_subset(md):
    """Pluck the curated `discovered.ni_*` dict from the parsed bundle."""
    return {key: fn(md) for key, fn, _desc in EXPOSED_FIELDS}


def extract(folder_path):
    """One-shot: read an NI acquisition folder, return (discovered, ni_section, 'ni').

    Returns a 3-tuple so the DICOM ecosystem dispatcher (`config._extract_dicom_embedded`)
    knows to override the sidecar section name. NI content lives under
    `metadata.json.ni`, not the generic `dicom:` block.

    If the folder doesn't look like an NI acquisition, returns
    ({}, {}, 'ni') — the dispatcher checks `is_ni_acquisition` before
    calling, so this is defensive.
    """
    md = load_ni_acquisition(folder_path)
    return build_discovered_subset(md), build_ni_section(md), "ni"
