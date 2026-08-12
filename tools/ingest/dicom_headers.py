"""Curated DICOM-header extraction for plain (non-ParaVision, non-Molecubes) DICOM.

This is the long-deferred "pure-DICOM-header extractor" the DICOM dispatcher
reserved the `dicom:` sidecar section for (see config._extract_dicom_embedded
and 08_METADATA §4.3). It is **opt-in**: nothing runs unless a config sets

    auto_discover:
      dicom_headers: true

so every existing config keeps its exact behaviour.

WHAT IT DOES NOT DO — and why that is deliberate
------------------------------------------------
The other ecosystem extractors end with a `_raw_metadata` forensic dump of
everything they saw. This one does NOT, and must not grow one, because the
first data to use it is **human clinical MRI**. A raw DICOM header dump would
copy direct patient identifiers out of the (immutable, archived) source files
and into `metadata.json` — which is the *searchable, indexed, hard-linked-into-
projects* layer, and into `registry_subjects.csv`.

So the extractor works from an explicit allow-list (`_SAFE_TAGS`), and two
tags are deliberately excluded even though they are present in the source:

    PatientName        a name, even when pseudonymized upstream
    PatientBirthDate   a FULL date of birth — a direct identifier, and a
                       quasi-identifier in combination with sex + study date

Age is preserved instead, coarsened to whole years (`P39Y`): that is the
scientifically useful part of a DOB with the identifying precision removed.
The raw values remain in the archived source DICOMs; this module simply
declines to propagate them upward. See 08_METADATA §4.9.

Adding a tag here is a privacy decision, not a convenience one — check it
against that list before extending `_SAFE_TAGS`.
"""

import os

# Tag -> discovered.<key>. Order is the order they appear in the sidecar.
# EVERY addition to this list is a privacy decision — see the module docstring.
_SAFE_TAGS = [
    ("PatientID",             "dicom_patient_id"),
    ("PatientSex",            "dicom_patient_sex"),
    ("PatientWeight",         "dicom_patient_weight_kg"),
    ("StudyDate",             "dicom_study_date"),
    ("StudyDescription",      "dicom_study_description"),
    ("Modality",              "dicom_modality"),
    ("BodyPartExamined",      "dicom_body_part"),
    ("Manufacturer",          "dicom_manufacturer"),
    ("ManufacturerModelName", "dicom_model"),
    ("MagneticFieldStrength", "dicom_field_strength_t"),
    ("InstitutionName",       "dicom_institution"),
]

# Never surfaced, no matter what the source contains.
_DENY_TAGS = frozenset({
    "PatientName", "PatientBirthDate", "PatientBirthTime", "PatientAddress",
    "PatientTelephoneNumbers", "OtherPatientIDs", "OtherPatientNames",
    "ReferringPhysicianName", "PerformingPhysicianName", "OperatorsName",
})

# Files that are directory records, not image instances.
_SKIP_BASENAMES = frozenset({"DICOMDIR", "DIRFILE"})

# Bound the walk: a case is ~20k instances and they share a study header.
_MAX_FILES_SCANNED = 400
_MAX_FILES_PARSED = 40


def _norm_sex(value):
    """DICOM PatientSex (M/F/O) -> the subject-block vocabulary (M/F/unknown)."""
    v = (str(value or "").strip().upper())[:1]
    return v if v in ("M", "F") else "unknown"


def _age_years(patient_age, birth_date, study_date):
    """Whole-year ISO-8601 age, e.g. "P39Y". "" when underivable.

    Prefers the DICOM PatientAge tag ("039Y"); falls back to birth/study dates.
    Deliberately year-granular — see the module docstring.
    """
    text = str(patient_age or "").strip()
    if text.upper().endswith("Y"):
        digits = text[:-1].lstrip("0")
        if digits.isdigit():
            return f"P{int(digits)}Y"
    dob, study = str(birth_date or "").strip(), str(study_date or "").strip()
    if len(dob) == 8 and len(study) == 8 and dob.isdigit() and study.isdigit():
        years = int(study[:4]) - int(dob[:4])
        # Not yet had this year's birthday.
        if study[4:] < dob[4:]:
            years -= 1
        if 0 <= years < 150:
            return f"P{years}Y"
    return ""


def _iter_candidate_files(root):
    """Yield plausible DICOM instance paths under `root`, breadth-ish first."""
    if os.path.isfile(root):
        yield root
        return
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            if name.upper() in _SKIP_BASENAMES:
                continue
            yield os.path.join(dirpath, name)
            seen += 1
            if seen >= _MAX_FILES_SCANNED:
                return


def extract(path):
    """Extract curated headers from a DICOM case folder (or single file).

    Returns the standard `(discovered, section)` 2-tuple. Both are empty when
    pydicom is unavailable or nothing parses — this is best-effort, and never
    raises, so an unreadable case degrades to "no embedded metadata" rather
    than failing the ingest (08_METADATA §4.7).

    Reads a bounded number of instances: the study-level tags we want are
    identical across a case, but the FIRST file is often a presentation-state
    (Modality "PR") rather than the image series, so we keep parsing until a
    real image modality shows up and collect the modality set along the way.
    """
    try:
        import pydicom
    except ImportError:
        return ({}, {})

    best = None
    modalities = []
    parsed = 0
    for file_path in _iter_candidate_files(path):
        if parsed >= _MAX_FILES_PARSED:
            break
        try:
            ds = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
        except Exception:
            continue
        if not getattr(ds, "SOPClassUID", None) and not getattr(ds, "Modality", None):
            continue  # not really a DICOM instance
        parsed += 1
        modality = str(getattr(ds, "Modality", "") or "").strip()
        if modality and modality not in modalities:
            modalities.append(modality)
        # Prefer a real image series over a presentation state / structured report.
        if best is None or (modality not in ("PR", "SR", "KO") and
                            str(getattr(best, "Modality", "")) in ("PR", "SR", "KO")):
            best = ds
        if best is not None and str(getattr(best, "Modality", "")) not in ("PR", "SR", "KO"):
            if len(modalities) > 1:
                break

    if best is None:
        return ({}, {})

    # EVERY allow-listed key is emitted, "" when the tag is absent. A config
    # that references ${discovered.dicom_model} must not hard-fail on the one
    # case whose header lacks it — the strict registry-block resolver raises on
    # an unknown discovered key, so "always present, sometimes empty" is what
    # makes these references safe to write.
    discovered = {}
    for tag, key in _SAFE_TAGS:
        if tag in _DENY_TAGS:          # belt and braces
            discovered[key] = ""
            continue
        value = getattr(best, tag, None)
        discovered[key] = "" if value is None else str(value).strip()

    if discovered.get("dicom_patient_sex"):
        discovered["dicom_patient_sex"] = _norm_sex(discovered["dicom_patient_sex"])

    discovered["dicom_patient_age"] = _age_years(
        getattr(best, "PatientAge", None),
        getattr(best, "PatientBirthDate", None),
        getattr(best, "StudyDate", None),
    )
    discovered["dicom_modalities_in_study"] = "/".join(sorted(modalities))

    # The sidecar `dicom:` section mirrors discovered, grouped for skimming.
    # Empty values are pruned HERE (but not from `discovered` above): this
    # block is read by humans, while `discovered` is read by ${...} references
    # that need every key to exist.
    # NO _raw_metadata bucket here — see the module docstring.
    def _bucket(*keys):
        return {k: discovered[k] for k in keys if discovered.get(k)}

    section = {
        "subject": _bucket("dicom_patient_id", "dicom_patient_sex",
                           "dicom_patient_age", "dicom_patient_weight_kg"),
        "study": _bucket("dicom_study_date", "dicom_study_description",
                         "dicom_modality", "dicom_modalities_in_study",
                         "dicom_body_part"),
        "equipment": _bucket("dicom_manufacturer", "dicom_model",
                             "dicom_field_strength_t", "dicom_institution"),
        "_extraction": {
            "instances_parsed": parsed,
            "policy": "curated allow-list; PatientName and PatientBirthDate "
                      "deliberately not extracted (08_METADATA §4.9)",
        },
    }
    return (discovered, section)
