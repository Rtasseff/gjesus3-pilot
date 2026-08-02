"""subject_id.py — parse instrument animal short codes into the facility key.

Phase 3 metadata enrichment (08_METADATA §4.4, identity model 06_REGISTRIES
§2.3 Option B) needs to turn what the instrument filename/folder carries into
the animal-facility DB join key:

    project_name  "AE-biomaGUNE-0525"  -> project_alias  "0525"
    short code    "m13" / "ID13B" / "14" -> animal_code 13 (+ optional organ)

then compose the canonical subject id "<animal_code>-AE-biomaGUNE-<NNNN>"
(done by animal_db.compose_subject_id). This module is the PURE string parser
half — no DB, no resolver dependency — so it is trivially unit-testable. The
ingest orchestrator (enrichment.py) resolves the ${discovered.*} templates
first and passes already-resolved strings in here.

Short-code shapes seen across instruments (per the per-instrument templates):
    MRI  (mri_bruker)   discovered.animal_num  -> already bare: "17"
    NI   (molecubes_ni) discovered.short_sample -> "m14"  (strip leading m)
    WSI  (axioscan7)    discovered.sample_short -> "ID13B" (strip ID, organ B)

The organ letter (e.g. the "B" in "ID13B") is a SAMPLE-level field
(anatomical_entity), NOT part of the subject id — it is returned separately so
a future tissue-sample path can use it; the subject id ignores it.
"""

import re

# Leading "m" or "ID" decoration, the numeric animal code, optional trailing
# organ letters. Case-insensitive. Non-matching strings (e.g. "phantom",
# "qc", "") yield (None, None) so phantom/QC scans route to the non-blocking
# unknown path rather than a bogus lookup.
_SHORT_CODE_RE = re.compile(r"^(?:id|m)?0*(?P<code>\d+)(?P<organ>[A-Za-z]+)?$", re.IGNORECASE)

# Project-name prefix. Case-insensitive, and still tolerant of the historical
# "biomeGUNE" misspelling (corrected to "biomaGUNE" everywhere 2026-08-02) so
# names carried in old data or typed from memory still parse. The alias is
# whatever follows the institute stem.
_NAME_PREFIX_RE = re.compile(r"^ae-?biom[ae]gune-(?P<alias>.+)$", re.IGNORECASE)


def parse_animal_short_code(value):
    """Parse an instrument short code -> (animal_code:int|None, organ:str|None).

    Strips a leading ``m`` / ``ID`` and any leading zeros, reads the numeric
    animal code, and returns trailing organ letters separately.

        "m13"    -> (13, None)
        "ID13B"  -> (13, "B")
        "14"     -> (14, None)
        "m14"    -> (14, None)
        "phantom"-> (None, None)        # no leading number -> not an animal
        ""/None  -> (None, None)

    Never raises — an unparseable code returns (None, None) so the caller can
    take the non-blocking path.
    """
    if value is None:
        return None, None
    s = str(value).strip()
    if not s:
        return None, None
    m = _SHORT_CODE_RE.match(s)
    if not m:
        return None, None
    code = int(m.group("code"))
    organ = m.group("organ") or None
    return code, organ


def project_alias_from_name(project_name):
    """Derive the facility project alias (NNNN) from a project name.

        "AE-biomaGUNE-0525" -> "0525"
        "ae-biomegune-0424" -> "0424"   (historical spelling/casing)
        "0525"              -> "0525"   (already bare)
        ""/None             -> ""

    Falls back to the trailing ``-``-delimited token when the institute stem
    isn't present (best-effort; a non-animal project just yields a DB miss).

    Reads the project NAME, not the PROJ-id: enrichment runs at Step 8.4,
    before the Step 9.5 resolve, so what it sees is what the operator supplied.
    """
    if not project_name:
        return ""
    s = str(project_name).strip()
    m = _NAME_PREFIX_RE.match(s)
    if m:
        return m.group("alias")
    if "-" in s:
        return s.rsplit("-", 1)[-1]
    return s


# ---- inline self-checks --------------------------------------------------

def _self_test():
    cases = [
        ("m13", (13, None)),
        ("ID13B", (13, "B")),
        ("id13b", (13, "b")),
        ("14", (14, None)),
        ("m14", (14, None)),
        ("17", (17, None)),
        ("m007", (7, None)),
        ("phantom", (None, None)),
        ("phantom_qc1", (None, None)),
        ("", (None, None)),
        (None, (None, None)),
    ]
    bad = [(c, parse_animal_short_code(c), exp) for c, exp in cases
           if parse_animal_short_code(c) != exp]
    names = [
        ("AE-biomaGUNE-0525", "0525"),      # canonical spelling (2026-08-02)
        ("ae-biomegune-0525", "0525"),      # historical lowercase + typo
        ("AE-biomeGUNE-0424", "0424"),
        ("0525", "0525"),
        ("laura-tholt", "tholt"),
        ("", ""),
        (None, ""),
    ]
    bad += [(n, project_alias_from_name(n), exp) for n, exp in names
            if project_alias_from_name(n) != exp]
    if bad:
        for got in bad:
            print(f"FAIL: {got}")
        return 1
    print(f"PASS - {len(cases)} short-code + {len(names)} project-name cases")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_self_test())
