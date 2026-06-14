#!/usr/bin/env python3
"""test_anatomy_derive.py — MRI anatomy auto-derive + back-fill (2026-06-13).

Covers the anatomy auto-derivation feature (mapping reviewed 2026-06-14):
  - anatomy_derive.derive_anatomy: high-confidence literal-term matching
    (heart / named vessels / brain fire; setup scans + bare technique +
    unnamed flow + unmatched -> None, never a guess)
  - anatomy_derive.collect_mri_signals: pulls scan-name text + FOV from a sidecar
  - enrichment._build_anatomy: operator-set wins; derive fills only when unset
  - backfill_mri_anatomy: plan_one outcomes + end-to-end dry-run/apply on a
    temp NAS (sidecar anatomy + registry anatomical_entity both updated)

Run:  PYTHONPATH=tools python tools/test_anatomy_derive.py
"""

import csv
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/

from ingest import anatomy_derive, enrichment, registry as reg  # noqa: E402
import backfill_mri_anatomy as bf  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def _quiet(*a, **k):
    pass


def test_derive_rules():
    print("[derive_anatomy rules]")
    d = anatomy_derive.derive_anatomy

    # Heart — unambiguous cardiac view / structure names.
    cardiac = d(["Cine_4-chamber", "Bruker:IgFLASH"])
    check(cardiac and cardiac["region"]["label"] == "heart", "4-chamber -> heart")
    check(cardiac and cardiac["region"]["id"] == "UBERON:0000948", "heart -> UBERON:0000948")
    check(cardiac and cardiac["is_whole_body"] is False, "named region -> is_whole_body False")
    check(cardiac and cardiac["source"] == "auto-derived", "source = auto-derived")
    check(((d(["Long axis LV"]) or {}).get("region") or {}).get("label") == "heart",
          "long axis -> heart")
    check(((d(["short-axis stack"]) or {}).get("region") or {}).get("label") == "heart",
          "short axis -> heart")

    # Large vessels — only when the vessel is NAMED.
    mpa = d(["Cine MPA"])
    check(mpa and mpa["region"]["label"] == "pulmonary artery", "MPA -> pulmonary artery")
    check(mpa and mpa["region"]["id"] == "UBERON:0002012", "PA -> UBERON:0002012")
    aorta = d(["aortic flow"])
    check(aorta and aorta["region"]["id"] == "UBERON:0000947", "aortic -> aorta UBERON:0000947")
    carotid = d(["carotid velocity"])
    check(carotid and carotid["region"]["id"] == "UBERON:0005396", "carotid -> UBERON:0005396")

    # Brain.
    brain = d(["T2_TurboRARE brain axial"])
    check(brain and brain["region"]["label"] == "brain", "brain -> brain")

    # Setup/planning scans -> None, even when a target organ is also named.
    check(d(["Localizer", "TriPilot"]) is None, "localizer-only -> None")
    check(d(["Localizer for the pulmonary artery"]) is None,
          "localizer-for-PA -> None (setup wins over the named vessel)")
    check(d(["Axial pure"]) is None, "axial pure (planning) -> None")

    # Ambiguous / technique-only / generic-sequence / unmatched -> None.
    check(d(["Velocity map"]) is None, "bare velocity map (no named vessel) -> None")
    check(d(["Cine slices"]) is None, "bare cine (technique, no region) -> None")
    check(d(["Bruker:IgFLASH", "T1_FLASH"]) is None, "generic sequence -> None")
    check(d([]) is None, "empty signal -> None")
    check(d(["", None]) is None, "blank signals -> None")


def test_collect_signals():
    print("[collect_mri_signals]")
    sidecar_mri = {
        "geometry": {"fov": "30 20"},
        "reconstruction": {"by_index": {
            "1": {"dicoms": [{"headers": {"SeriesDescription": "Cine_4-chamber"}}]},
        }},
    }
    discovered = {"mri_sequence_name": "Bruker:IgFLASH",
                  "mri_study_name": "jrc_251016_m17_0424"}
    sig = anatomy_derive.collect_mri_signals(discovered, sidecar_mri)
    check("Cine_4-chamber" in sig["text_signals"], "SeriesDescription gathered")
    check("Bruker:IgFLASH" in sig["text_signals"], "sequence name gathered")
    check(sig["fov"] == "30 20", "fov gathered from geometry")
    # And the gathered signal derives heart.
    der = anatomy_derive.derive_anatomy(sig["text_signals"], fov=sig["fov"])
    check(der and der["region"]["label"] == "heart", "collected signal -> heart")


def test_enrichment_build_anatomy():
    print("[enrichment._build_anatomy auto-derive]")
    derive = {"text_signals": ["Cine 4-chamber"], "fov": None}

    # Operator left anatomy unset -> derive fills it.
    out = enrichment._build_anatomy({}, {}, _quiet, "organism", derive_fields=derive)
    check((out.get("region") or {}).get("label") == "heart",
          "unset anatomy is auto-derived to heart")
    check(out.get("source") == "auto-derived", "derived source tagged")

    # Operator-set anatomy WINS (no override).
    cfg_op = {"anatomy": {"is_whole_body": False,
                          "region": {"label": "brain", "id": "UBERON:0000955"}}}
    out2 = enrichment._build_anatomy(cfg_op, {}, _quiet, "organism", derive_fields=derive)
    check((out2.get("region") or {}).get("label") == "brain",
          "operator-set region (brain) is NOT overridden by the cardiac signal")

    # auto_derive=False disables it entirely.
    out3 = enrichment._build_anatomy({}, {}, _quiet, "organism",
                                     derive_fields=derive, auto_derive=False)
    check(out3.get("region") is None, "auto_derive=False leaves region null")

    # No confident match -> stays null.
    out4 = enrichment._build_anatomy({}, {}, _quiet, "organism",
                                     derive_fields={"text_signals": ["FLASH"], "fov": None})
    check(out4.get("region") is None, "ambiguous signal leaves region null")


def _seed_nas(d):
    """Build a temp NAS with registries/registry_raw.csv + one MRI sidecar."""
    registries_dir = os.path.join(d, "registries")
    os.makedirs(registries_dir)
    reg_path = os.path.join(registries_dir, "registry_raw.csv")
    acq = "ACQ-20260116-MRI-001"
    canonical = f"/raw/DICOM/2026/2026-01/{acq}/"
    acq_dir = os.path.join(d, canonical.lstrip("/"))
    os.makedirs(acq_dir)
    sidecar = {
        "acq_id": acq,
        "discovered": {"mri_sequence_name": "Bruker:IgFLASH"},
        "mri": {"reconstruction": {"by_index": {
            "1": {"dicoms": [{"headers": {"SeriesDescription": "Cine_4-chamber"}}]},
        }}},
        "anatomy": {"is_whole_body": None, "region": None,
                    "additional_regions": [], "source": "unknown", "auto_hint": ""},
    }
    with open(os.path.join(acq_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2)
    row = {k: "" for k in reg.REGISTRY_FIELDS}
    row.update({"acq_id": acq, "data_ecosystem": "DICOM", "instrument": "MRI",
                "canonical_path": canonical, "project_hint": "PROJ-0003"})
    with open(reg_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=reg.REGISTRY_FIELDS)
        w.writeheader()
        w.writerow(row)
    return reg_path, acq, os.path.join(acq_dir, "metadata.json")


def test_backfill_end_to_end():
    print("[backfill_mri_anatomy dry-run + apply]")
    with tempfile.TemporaryDirectory() as d:
        reg_path, acq, sidecar_path = _seed_nas(d)

        # plan_one says "fill".
        with open(sidecar_path, encoding="utf-8") as f:
            outcome, proposed = bf.plan_one(json.load(f))
        check(outcome == "fill" and proposed["region"]["label"] == "heart",
              "plan_one -> fill (heart)")

        # Dry-run touches nothing.
        c = bf.backfill(d, apply=False)
        check(c["would-fill"] == 1 and c["filled"] == 0, "dry-run would-fill=1, filled=0")
        with open(sidecar_path, encoding="utf-8") as f:
            check((json.load(f)["anatomy"]["region"]) is None,
                  "dry-run left the sidecar untouched")

        # Apply writes sidecar + registry.
        c2 = bf.backfill(d, apply=True)
        check(c2["filled"] == 1, "apply filled=1")
        with open(sidecar_path, encoding="utf-8") as f:
            anat = json.load(f)["anatomy"]
        check((anat.get("region") or {}).get("label") == "heart",
              "sidecar anatomy.region.label == heart after apply")
        check(anat.get("source") == "auto-derived", "sidecar source tagged")
        regrows = reg.read_registry(reg_path)
        check(regrows[0]["anatomical_entity"] == "heart",
              "registry anatomical_entity == heart after apply")

        # Idempotent: a second apply finds it already-set, fills nothing.
        c3 = bf.backfill(d, apply=True)
        check(c3["already-set"] == 1 and c3["filled"] == 0,
              "second apply is idempotent (already-set)")


def main():
    test_derive_rules()
    test_collect_signals()
    test_enrichment_build_anatomy()
    test_backfill_end_to_end()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for m in FAILS:
            print(f"  - {m}")
        return 1
    print("ALL PASS (anatomy auto-derive + back-fill)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
