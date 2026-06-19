"""Write per-acquisition metadata.json sidecar.

Schema follows the on-disk shape already deployed for DICOM acquisitions
(e.g. /raw/DICOM/2018/2018-04/ACQ-20180425-XMRI-001/metadata.json):

    {
      "acq_id": ...,
      "generated": "<ISO UTC>",
      "generator": "ingest_raw.py",
      "user_supplied": {researcher, operator, data_source, instrument,
                        sample_id, sample_type, original_name, notes},
      "discovered": {<field>: <value>, ...}        # everything auto_discover surfaced
      "<ecosystem_section>": {...}                  # "dicom", "microscopy", ...
    }

`discovered` carries everything auto_discover produced for the case
(filename-parser output, parent-folder date, future embedded extracts).
The ecosystem section is reserved for embedded-metadata extraction
(DICOM headers, .czi internals) — currently `{}` and populated in
follow-up work driven by probe_czi.py output.
"""

import json
import os
from datetime import datetime, timezone


SIDECAR_FILENAME = "metadata.json"


def build_user_supplied(cfg):
    """Pluck the user-facing config fields that go into the sidecar.

    Two distinct person roles (2026-06-09, 06_REGISTRIES §2.3a):
      - `researcher` — set up the experiment. ALSO a registry column.
      - `operator`   — ran the equipment for THIS acquisition. SIDECAR-ONLY
                       (not a registry column); kept for future DB/image-server
                       search. For MRI/NI the two are the same person.
    ("user" is reserved for "a person using the software" and is not a role.)
    """
    return {
        "researcher":   cfg.get("researcher", ""),
        "operator":     cfg.get("operator", ""),
        "data_source":  cfg.get("data_source", ""),
        "instrument":   cfg.get("instrument", ""),
        "sample_id":    cfg.get("sample_id", ""),
        "sample_type":  cfg.get("sample_type", ""),
        "original_name": cfg.get("original_name", ""),
        "notes":        cfg.get("notes", ""),
    }


def build_sidecar(acq_id, cfg, ecosystem_section_name="", ecosystem_section=None,
                  subject=None, condition=None, anatomy=None, subjects=None):
    """Construct the sidecar dict.

    Args:
        acq_id: ACQ-ID string.
        cfg: per-case config dict (post-special-fields-promotion).
        ecosystem_section_name: e.g. "dicom" or "microscopy". If empty,
            no ecosystem section is added.
        ecosystem_section: dict to nest under ecosystem_section_name; if
            None, an empty dict is used.
        subject / condition / anatomy: the Phase 3 preclinical enrichment
            blocks (08_METADATA §4.4–4.6), built by ingest/enrichment.py for
            organism/tissue acquisitions. Each is added only when not None,
            keeping the key order acq_id .. discovered, subject, subjects,
            condition, anatomy, <ecosystem_section> (08_METADATA §4.3).
        subjects: OPTIONAL list of subject blocks for a multi-animal NI scan
            (NI-LIVE-08) — written as the `subjects:[]` array alongside the
            primary `subject`. None (omitted) for single-subject instruments,
            so their sidecars are byte-for-byte unchanged.

    Returns:
        ordered dict ready for json.dump.
    """
    discovered = cfg.get("discovered") or {}
    sidecar = {
        "acq_id": acq_id,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "ingest_raw.py",
        "user_supplied": build_user_supplied(cfg),
        "discovered": dict(discovered),
    }
    if subject is not None:
        sidecar["subject"] = subject
    if subjects is not None:
        sidecar["subjects"] = subjects
    if condition is not None:
        sidecar["condition"] = condition
    if anatomy is not None:
        sidecar["anatomy"] = anatomy
    if ecosystem_section_name:
        sidecar[ecosystem_section_name] = ecosystem_section or {}
    return sidecar


def write_sidecar(folder, sidecar_dict):
    """Write the sidecar dict as metadata.json inside `folder`.

    Returns the absolute path written.
    """
    path = os.path.join(folder, SIDECAR_FILENAME)
    with open(path, "w") as f:
        json.dump(sidecar_dict, f, indent=2)
        f.write("\n")
    return path
