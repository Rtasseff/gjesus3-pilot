"""anatomy_derive.py — derive the `anatomy` block from MRI scan-name signals.

Reviewed with the MRI lead (J. Ruiz-Cabello, 2026-06-14) + the data office.
08_METADATA §4.6 lists `is_whole_body` / `region` as operator-entered (the DICOM
`BodyPartExamined` tag is empty upstream); this module fills that gap from the
acquisition's scan name — but ONLY with high confidence:

  - Map ONLY when the scan NAME literally contains an anatomy/structure term.
    The scan name (SeriesDescription / ProtocolName / sequence name) is the
    signal — NOT the pulse-sequence type (FLASH/RARE are organ-independent) and
    NOT the FOV (it tracks the RF coil, not the region, and isn't recorded).
  - If there is ANY doubt, return ``None`` → the anatomy block stays null
    (queryable as "unknown"). A wrong label is worse than a missing one; this
    NEVER guesses.
  - No group-specific assumptions are baked in (this serves Jesús's cardiac
    work today but will expand to other groups) — every rule is a literal,
    generally-true anatomy term.

Consequences (per the MRI lead): setup/planning scans (localizer, pilot,
planning, axial-pure) carry no organ → skip; flow scans image LARGE VESSELS
(aorta / pulmonary artery / carotid), NOT the heart — so they map only when the
vessel is NAMED (a bare "velocity map" stays null); a bare "cine" (a technique,
not a region) stays null.

To extend: add literal-term rows to ``ANATOMY_RULES`` (one editable place).
UBERON ids verified via EBI OLS (2026-06-14).

Shared by BOTH the ingest auto-derive (enrichment._build_anatomy, future
ingests) AND tools/backfill_mri_anatomy.py (back-fill already-ingested
sidecars) — a SINGLE source of truth for the mapping.

Microscopy note: MRI anatomy comes from the scan NAME (`ANATOMY_RULES` below);
microscopy (AxioScan etc.) anatomy comes from the sample-id ORGAN CODE via an
operator-keyed reference map — see `derive_microscopy_anatomy` /
`load_organ_map` lower in this file and `tools/reference/microscopy_organ_map.yaml`.
"""

import os
import re

from . import subject_id


# Sentinel: a setup/planning scan (localizer / pilot / ...). It carries no
# organ even when a target is named ("Localizer for the pulmonary artery"), so
# a match derives NOTHING (returns None immediately).
_SKIP = object()

# --- MAPPING (reviewed 2026-06-14; UBERON ids verified via EBI OLS) ----------
# Each rule: (name, patterns, is_whole_body, region).
#   patterns — case-insensitive regexes; the rule fires if ANY matches the
#              combined scan-name text. First matching rule wins, so the
#              setup/planning rule is FIRST (a localizer never gets an organ).
#   region   — the {label, ontology, id} dict, or _SKIP (derive nothing).
# Only literal, generally-true anatomy terms (no group-specific guesses); add
# rows as new high-confidence terms appear. is_whole_body is False for every
# named region (a specific region is, by definition, not whole-body) and is
# never set True here (FOV/coil can't determine it — 08_METADATA §4.6).
ANATOMY_RULES = [
    ("setup/planning",
     [r"localis", r"localiz", r"tripilot", r"tri[\s_-]*pilot",
      r"\bscout\b", r"\bplanning\b", r"\bpilot\b", r"axial[\s_-]*pure"],
     None, _SKIP),
    # Heart — unambiguous cardiac view / structure names. A bare "cine" is a
    # technique, not a region, so it is deliberately NOT here (stays null).
    ("heart",
     [r"cardiac", r"4[\s_-]*chamber", r"long[\s_-]*axis", r"short[\s_-]*axis",
      r"ventric"],
     False, {"label": "heart", "ontology": "UBERON", "id": "UBERON:0000948"}),
    # Large vessels (flow scans image vessels, not myocardium) — only when the
    # vessel is NAMED; a bare "velocity map" has no named vessel -> stays null.
    ("pulmonary artery",
     [r"\bmpa\b", r"pulmonary[\s_-]*artery"],
     False, {"label": "pulmonary artery", "ontology": "UBERON", "id": "UBERON:0002012"}),
    ("aorta",
     [r"\baorta\b", r"\baortic\b"],
     False, {"label": "aorta", "ontology": "UBERON", "id": "UBERON:0000947"}),
    ("carotid artery",
     [r"\bcarotid\b"],
     False, {"label": "carotid artery", "ontology": "UBERON", "id": "UBERON:0005396"}),
    ("brain",
     [r"\bbrain\b", r"cerebr"],
     False, {"label": "brain", "ontology": "UBERON", "id": "UBERON:0000955"}),
    ("abdomen",
     [r"\babdomen\b", r"\babdominal\b"],
     False, {"label": "abdomen", "ontology": "UBERON", "id": "UBERON:0000916"}),
]


def derive_anatomy(text_signals, fov=None):
    """Propose an anatomy region from scan-name text. High-confidence only; never guesses.

    Args:
        text_signals: iterable of strings (scan name / SeriesDescription /
            ProtocolName / sequence name / study name). All are lower-cased and
            joined; rules match against the join.
        fov: accepted for signature stability but DELIBERATELY UNUSED — FOV
            tracks the RF coil, not the region, so it is not determinant of
            anatomy (per the MRI lead, 2026-06-14).

    Returns:
        dict {is_whole_body, region, auto_hint, source} when a rule matches a
        named region; otherwise ``None`` — a setup/planning scan, an unnamed
        flow scan, a bare technique name, or any unmatched signal derives
        nothing (the caller leaves the anatomy block null).
    """
    text = " ".join(str(s) for s in text_signals if s).lower()
    if not text.strip():
        return None
    for name, patterns, is_wb, region in ANATOMY_RULES:
        if any(re.search(p, text) for p in patterns):
            if region is _SKIP:
                # Setup/planning scan — derive nothing even if a target organ
                # is also named (e.g. "Localizer for the pulmonary artery").
                return None
            return {
                "is_whole_body": is_wb,
                "region": dict(region),
                "auto_hint": f"auto-derived (rule '{name}') from scan-name signal",
                "source": "auto-derived",
            }
    return None


def collect_mri_signals(discovered, mri_section):
    """Gather scan-name text signals + FOV for derive_anatomy from the MRI
    `discovered.*` fields and the `mri:` sidecar section.

    Knows the MRI sidecar shape so enrichment.py / the back-fill tool stay
    ecosystem-agnostic. Returns {"text_signals": [...], "fov": <value or None>}.
    """
    discovered = discovered or {}
    mri_section = mri_section or {}
    signals = []
    # Discovered fields available already at ingest time.
    for k in ("mri_study_name", "mri_sequence_name", "mri_pulse_program"):
        v = discovered.get(k)
        if v:
            signals.append(str(v))
    # The human scan name lives in the per-DICOM SeriesDescription / ProtocolName
    # (e.g. "Cine_slice_1_12") under reconstruction.by_index.<idx>.dicoms[].headers.
    recon = mri_section.get("reconstruction") or {}
    for idx_info in (recon.get("by_index") or {}).values():
        for d in (idx_info.get("dicoms") or []):
            headers = d.get("headers") or {}
            for tag in ("SeriesDescription", "ProtocolName", "StudyDescription"):
                if headers.get(tag):
                    signals.append(str(headers[tag]))
    geometry = mri_section.get("geometry") or {}
    fov = geometry.get("fov") if geometry else None
    return {"text_signals": signals, "fov": fov}


# ===================================================================
# Microscopy (AxioScan etc.) — anatomy from the sample-id organ code
# ===================================================================
# Unlike MRI (scan-name rules in code), the microscopy organ vocabulary is
# OPERATOR-SPECIFIC and editable, so the mapping lives in a reference YAML
# (tools/reference/microscopy_organ_map.yaml) loaded at runtime — data, not code.

_DEFAULT_ORGAN_MAP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # tools/
    "reference", "microscopy_organ_map.yaml",
)
_ORGAN_MAP_CACHE = {}


def load_organ_map(path=None):
    """Load the operator-keyed microscopy organ map (YAML) -> the `operators`
    dict. Cached per path. Returns {} if the file is absent/unreadable (so a
    missing map degrades to "derive nothing", never an error)."""
    path = path or _DEFAULT_ORGAN_MAP_PATH
    if path in _ORGAN_MAP_CACHE:
        return _ORGAN_MAP_CACHE[path]
    operators = {}
    try:
        import yaml  # lazy
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        operators = data.get("operators") or {}
    except (OSError, ValueError):
        operators = {}
    _ORGAN_MAP_CACHE[path] = operators
    return operators


def _region_from_entry(entry, source_note):
    """Build the proposed anatomy dict from a map entry. Tissue => is_whole_body
    stays null (a section is never whole-body — 08_METADATA §4.6)."""
    return {
        "is_whole_body": None,
        "region": {"label": entry["label"],
                   "ontology": entry.get("ontology", "UBERON"),
                   "id": entry["id"]},
        "additional_regions": entry.get("additional_regions") or [],
        "auto_hint": source_note,
        "source": "auto-derived",
    }


def derive_microscopy_anatomy(sample_short, operator, organ_map=None):
    """Derive a tissue anatomy region from a microscopy sample-id + operator.

    Args:
        sample_short: the sample-id chunk (e.g. "ID12Lu", "ID29H", "mPCLS_n1").
        operator: the acquiring operator code (e.g. "AUA" / "MBC") — selects the
            sub-map (the suffix vocabulary is operator-specific).
        organ_map: the `operators` dict (defaults to the reference YAML).

    High-confidence only: an exact organ-suffix code (parsed) is tried first,
    then prep-type keywords (substring); an unmapped code / unknown operator /
    blank input derives nothing (None) so anatomy stays null. Returns
    {is_whole_body, region, additional_regions, auto_hint, source} or None.
    """
    if organ_map is None:
        organ_map = load_organ_map()
    op = (operator or "").strip().upper()
    short = (sample_short or "").strip()
    if not op or not short:
        return None
    opmap = organ_map.get(op) or organ_map.get(operator) or {}
    if not opmap:
        return None

    # 1. Exact organ-suffix code (e.g. "ID12Lu" -> "Lu"). Case-insensitive,
    #    matched as the parsed suffix only (never a loose substring).
    _code, organ = subject_id.parse_animal_short_code(short)
    if organ:
        codes = {str(k).lower(): v for k, v in (opmap.get("codes") or {}).items()}
        entry = codes.get(organ.lower())
        if entry:
            return _region_from_entry(
                entry, f"auto-derived (operator {op}, organ code '{organ}') from sample-id")

    # 2. Prep-type keyword (substring), e.g. "mPCLS" -> lung.
    low = short.lower()
    for kw, entry in (opmap.get("keywords") or {}).items():
        if str(kw).lower() in low:
            return _region_from_entry(
                entry, f"auto-derived (operator {op}, keyword '{kw}') from sample-id")
    return None
