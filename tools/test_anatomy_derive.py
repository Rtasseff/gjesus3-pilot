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
import backfill_microscopy_anatomy as bfm  # noqa: E402

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


def test_override():
    print("[one-time back-fill override (input, not a code rule)]")
    with tempfile.TemporaryDirectory() as d:
        ovpath = os.path.join(d, "ov.yaml")
        with open(ovpath, "w", encoding="utf-8") as f:
            f.write('overrides:\n')
            f.write('  - match: "cine[ _]*ig[ _]*flash"\n')
            f.write('    label: heart\n')
            f.write('    ontology: UBERON\n')
            f.write('    id: "UBERON:0000948"\n')
            f.write('    is_whole_body: false\n')
            f.write('    note: "test override"\n')
        ov = bf.load_override(ovpath)
        check(len(ov) == 1 and ov[0]["label"] == "heart", "load_override parses the rule")

        prop = bf.apply_override(["jrc_x", "Bruker:IgFLASH", "Cine_IG_FLASH"], ov)
        check(prop and prop["region"]["label"] == "heart", "override: Cine_IG_FLASH -> heart")
        check(prop and prop["source"] == "auto-derived-override", "override source tagged")
        check(bf.apply_override(["Velocity_map"], ov) is None,
              "override: bare velocity_map -> None (no named vessel, not overridden)")

        def _sc(series):
            return {"mri": {"reconstruction": {"by_index": {"1": {"dicoms": [
                {"headers": {"SeriesDescription": series}}]}}}},
                "anatomy": {"is_whole_body": None, "region": None,
                            "additional_regions": [], "source": "unknown", "auto_hint": ""}}

        # High-confidence wins over the override (4-chamber -> auto-derived, not override).
        oc, pr = bf.plan_one(_sc("Cine_ 4 chamber"), override=ov)
        check(oc == "fill" and pr["source"] == "auto-derived",
              "4-chamber stays high-confidence (override not consulted)")
        # Bare cine-FLASH: null from the mapping, filled by the override.
        oc2, pr2 = bf.plan_one(_sc("Cine_IG_FLASH"), override=ov)
        check(oc2 == "fill" and pr2["region"]["label"] == "heart"
              and pr2["source"] == "auto-derived-override",
              "bare Cine_IG_FLASH -> heart via override")
        # Without the override it correctly stays null.
        oc3, _ = bf.plan_one(_sc("Cine_IG_FLASH"))
        check(oc3 == "no-derivation", "bare Cine_IG_FLASH without override -> null")

        # The shipped override file loads and matches.
        repo_ov = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "configs", "mri_anatomy_override_2026-06.yaml")
        if os.path.isfile(repo_ov):
            p = bf.apply_override(["Cine_IG_FLASH"], bf.load_override(repo_ov))
            check(p and p["region"]["label"] == "heart",
                  "shipped override file maps Cine_IG_FLASH -> heart")


def test_microscopy_derive():
    print("[microscopy organ-code derive (operator-keyed)]")
    d = anatomy_derive.derive_microscopy_anatomy
    om = anatomy_derive.load_organ_map()
    check("AUA" in om and "MBC" in om, "shipped organ map loads AUA + MBC")

    # AUA verbose suffixes.
    check((d("ID12Lu", "AUA", om) or {}).get("region", {}).get("id") == "UBERON:0002048",
          "AUA Lu -> lung UBERON:0002048")
    check((d("ID5Li", "AUA", om) or {}).get("region", {}).get("id") == "UBERON:0002107",
          "AUA Li -> liver UBERON:0002107")
    check((d("ID9K", "AUA", om) or {}).get("region", {}).get("id") == "UBERON:0002113",
          "AUA K -> kidney UBERON:0002113")
    check(d("ID103T", "AUA", om) is None, "AUA T (tumor) -> null (unmapped)")
    check((d("mPCLS_n1", "AUA", om) or {}).get("region", {}).get("label") == "lung",
          "AUA mPCLS -> lung (keyword)")

    # MBC single letters.
    check((d("ID29H", "MBC", om) or {}).get("region", {}).get("label") == "heart",
          "MBC H -> heart")
    check((d("ID13B", "MBC", om) or {}).get("region", {}).get("label") == "brain",
          "MBC B -> brain")
    check((d("ID7L", "MBC", om) or {}).get("region", {}).get("label") == "lung",
          "MBC L -> lung (confirmed)")
    hl = d("ID8HL", "MBC", om)
    check(hl and hl["region"]["label"] == "heart", "MBC HL -> heart (primary)")
    check(hl and any(r["label"] == "lung" for r in hl.get("additional_regions") or []),
          "MBC HL adds lung as additional region")

    # Tissue discipline + operator-specificity + edge cases.
    check((d("ID29H", "MBC", om) or {}).get("is_whole_body") is None,
          "tissue -> is_whole_body stays null")
    check((d("ID29H", "MBC", om) or {}).get("source") == "auto-derived", "source = auto-derived")
    check(d("ID29H", "AUA", om) is None, "AUA has no single-letter H -> null (operator-specific)")
    check(d("ID12Lu", "ZZZ", om) is None, "unknown operator -> null")
    check(d("", "MBC", om) is None and d("ID12Lu", "", om) is None, "blank inputs -> null")
    check((d("id12lu", "aua", om) or {}).get("region", {}).get("label") == "lung",
          "case-insensitive")


def test_enrichment_microscopy():
    print("[enrichment microscopy auto-derive]")
    disc = {"sample_short": "ID12Lu", "operator": "AUA"}
    out = enrichment._build_anatomy({}, disc, _quiet, "tissue")
    check((out.get("region") or {}).get("label") == "lung", "tissue AUA Lu -> lung")
    # Organism (MRI) must NOT use the microscopy path.
    out2 = enrichment._build_anatomy({}, disc, _quiet, "organism")
    check(out2.get("region") is None, "organism does not microscopy-derive")
    # Operator-set anatomy wins.
    cfg = {"anatomy": {"is_whole_body": None,
                       "region": {"label": "brain", "id": "UBERON:0000955"}}}
    out3 = enrichment._build_anatomy(cfg, disc, _quiet, "tissue")
    check((out3.get("region") or {}).get("label") == "brain", "operator-set region wins")


def test_microscopy_backfill():
    print("[backfill_microscopy_anatomy dry-run + apply]")
    with tempfile.TemporaryDirectory() as d:
        registries_dir = os.path.join(d, "registries")
        os.makedirs(registries_dir)
        reg_path = os.path.join(registries_dir, "registry_raw.csv")
        acq = "ACQ-20260219-ZWSI-001"
        canonical = f"/raw/MICROSCOPY/2026/2026-02/{acq}/"
        acq_dir = os.path.join(d, canonical.lstrip("/"))
        os.makedirs(acq_dir)
        sidecar = {"acq_id": acq, "discovered": {"sample_short": "ID29H"},
                   "microscopy": {},
                   "anatomy": {"is_whole_body": None, "region": None,
                               "additional_regions": [], "source": "unknown", "auto_hint": ""}}
        with open(os.path.join(acq_dir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(sidecar, f, indent=2)
        rowd = {k: "" for k in reg.REGISTRY_FIELDS}
        rowd.update({"acq_id": acq, "data_ecosystem": "MICROSCOPY", "instrument": "ZWSI",
                     "operator": "MBC", "canonical_path": canonical, "sample_id": "0424_ID29H"})
        with open(reg_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=reg.REGISTRY_FIELDS)
            w.writeheader()
            w.writerow(rowd)
        sc_path = os.path.join(acq_dir, "metadata.json")

        c = bfm.backfill(d, apply=False)
        check(c["would-fill"] == 1 and c["filled"] == 0, "dry-run would-fill=1")
        with open(sc_path, encoding="utf-8") as f:
            check(json.load(f)["anatomy"]["region"] is None, "dry-run left sidecar untouched")

        c2 = bfm.backfill(d, apply=True)
        check(c2["filled"] == 1, "apply filled=1")
        with open(sc_path, encoding="utf-8") as f:
            anat = json.load(f)["anatomy"]
        check((anat.get("region") or {}).get("label") == "heart",
              "sidecar region=heart (MBC H) after apply")
        check(reg.read_registry(reg_path)[0]["anatomical_entity"] == "heart",
              "registry anatomical_entity=heart after apply")
        c3 = bfm.backfill(d, apply=True)
        check(c3["already-set"] == 1 and c3["filled"] == 0, "idempotent (already-set)")


def main():
    test_derive_rules()
    test_collect_signals()
    test_enrichment_build_anatomy()
    test_backfill_end_to_end()
    test_override()
    test_microscopy_derive()
    test_enrichment_microscopy()
    test_microscopy_backfill()
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
