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
"""

import re


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
