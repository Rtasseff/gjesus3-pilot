"""Tests for backfill_sidecar_condition.py: fill-only-unset, add-only tables, verify + backup.

Run: python -m pytest tools/test_backfill_sidecar_condition.py
"""
import csv
import json
import os



import backfill_sidecar_condition as bsc
from ingest import registry as reg

CFG = {"condition": {"is_control": "${discovered.drv_is_control}",
                     "disease_state": "${discovered.drv_disease_state}",
                     "study_arm": "${discovered.drv_study_arm}",
                     "source": "operator-entered"}}
UNSET = {"is_control": None, "disease_model": "", "disease_state": "", "control_type": "",
         "treatment": None, "timepoint_days": None, "study_arm": "", "source": "unknown"}


def _nas(tmp_path, sidecars):
    """A minimal NAS: registry_raw.csv + one sidecar per {acq_id: sidecar}."""
    (tmp_path / "registries").mkdir()
    with open(tmp_path / "registries" / "registry_raw.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=reg.REGISTRY_FIELDS)
        w.writeheader()
        for aid, sc in sidecars.items():
            d = tmp_path / "raw" / aid
            d.mkdir(parents=True)
            (d / "metadata.json").write_text(json.dumps(sc, indent=2), encoding="utf-8")
            w.writerow({"acq_id": aid, "canonical_path": f"/raw/{aid}/", "original_name": aid + "_name"})
    return str(tmp_path)


def _row(aid, ctrl="true", state="baseline", arm="control"):
    return {"acq_id": aid, "drv_is_control": ctrl, "drv_disease_state": state, "drv_study_arm": arm}


def test_fills_unset_condition_with_tristate_from_table(tmp_path):
    nas = _nas(tmp_path, {"A1": {"acq_id": "A1", "condition": dict(UNSET), "dicom": {"x": 1}}})
    counts, _ = bsc.backfill(nas, CFG, [_row("A1", "false", "ARDS", "ARDS")], apply=True,
                             backup_dir=str(tmp_path / "bk"))
    assert counts["changed"] == 1
    sc = json.load(open(os.path.join(nas, "raw", "A1", "metadata.json"), encoding="utf-8"))
    assert sc["condition"]["is_control"] is False
    assert sc["condition"]["disease_state"] == "ARDS"
    assert sc["condition"]["source"] == "operator-entered"
    assert sc["dicom"] == {"x": 1}
    assert os.path.exists(tmp_path / "bk" / "A1.metadata.json")


def test_never_overwrites_a_set_condition(tmp_path):
    set_cond = dict(UNSET, is_control=True, disease_state="baseline", source="operator-entered")
    nas = _nas(tmp_path, {"A1": {"acq_id": "A1", "condition": set_cond}})
    counts, _ = bsc.backfill(nas, CFG, [_row("A1", "false", "ARDS")], apply=True,
                             backup_dir=str(tmp_path / "bk"))
    assert counts["changed"] == 0 and counts["nothing-to-do"] == 1
    sc = json.load(open(os.path.join(nas, "raw", "A1", "metadata.json"), encoding="utf-8"))
    assert sc["condition"] == set_cond


def test_dry_run_touches_nothing(tmp_path):
    nas = _nas(tmp_path, {"A1": {"acq_id": "A1", "condition": dict(UNSET)}})
    p = os.path.join(nas, "raw", "A1", "metadata.json")
    before = open(p, encoding="utf-8").read()
    counts, report = bsc.backfill(nas, CFG, [_row("A1")], apply=False)
    assert counts["would-change"] == 1 and len(report) == 1
    assert open(p, encoding="utf-8").read() == before


def test_user_table_added_only_when_label_absent(tmp_path):
    table = tmp_path / "p.csv"
    table.write_text("key,Media\n2225_control,19\n", encoding="utf-8")
    cfg = {"user_metadata": [{"label": "pressures", "file": str(table), "key_column": "key",
                              "match": "${discovered.k}", "on_missing": "warn"}]}
    nas = _nas(tmp_path, {
        "A1": {"acq_id": "A1", "condition": dict(UNSET)},
        "A2": {"acq_id": "A2", "condition": dict(UNSET), "user_provided_metadata": {"pressures": {"old": 1}}},
    })
    counts, _ = bsc.backfill(nas, cfg, [{"acq_id": "A1", "k": "2225_control"}, {"acq_id": "A2", "k": "2225_control"}],
                             apply=True, backup_dir=str(tmp_path / "bk"))
    a1 = json.load(open(os.path.join(nas, "raw", "A1", "metadata.json"), encoding="utf-8"))
    a2 = json.load(open(os.path.join(nas, "raw", "A2", "metadata.json"), encoding="utf-8"))
    assert a1["user_provided_metadata"]["pressures"]["Media"] == "19"
    assert a2["user_provided_metadata"]["pressures"] == {"old": 1}
    assert counts["changed"] == 1


def test_unlisted_acquisitions_untouched_and_unknown_id_is_error(tmp_path):
    nas = _nas(tmp_path, {"A1": {"acq_id": "A1", "condition": dict(UNSET)},
                          "A2": {"acq_id": "A2", "condition": dict(UNSET)}})
    p2 = os.path.join(nas, "raw", "A2", "metadata.json")
    before = open(p2, encoding="utf-8").read()
    counts, _ = bsc.backfill(nas, CFG, [_row("A1"), _row("ZZ")], apply=True, backup_dir=str(tmp_path / "bk"))
    assert counts["changed"] == 1 and counts["not-in-registry"] == 1
    assert open(p2, encoding="utf-8").read() == before


def test_refuses_to_overwrite_an_existing_backup(tmp_path):
    nas = _nas(tmp_path, {"A1": {"acq_id": "A1", "condition": dict(UNSET)}})
    (tmp_path / "bk").mkdir()
    (tmp_path / "bk" / "A1.metadata.json").write_text("{}", encoding="utf-8")
    counts, _ = bsc.backfill(nas, CFG, [_row("A1")], apply=True, backup_dir=str(tmp_path / "bk"))
    assert counts["error"] == 1


def test_project_hard_link_sees_the_write(tmp_path):
    """The /raw sidecar is hard-linked into the project folder; the back-fill must
    write the same file, not replace it (2026-11-07 regression)."""
    nas = _nas(tmp_path, {"A1": {"acq_id": "A1", "condition": dict(UNSET)}})
    raw = os.path.join(nas, "raw", "A1", "metadata.json")
    link = os.path.join(nas, "project_link_metadata.json")
    os.link(raw, link)
    counts, _ = bsc.backfill(nas, CFG, [_row("A1", "false", "ARDS")], apply=True, backup_dir=str(tmp_path / "bk"))
    assert counts["changed"] == 1
    assert os.path.samefile(raw, link)
    assert json.load(open(link, encoding="utf-8"))["condition"]["is_control"] is False


def main():
    """Run as a suite script (tools/run_tests.py runs each test_*.py as a program); pytest also works."""
    import inspect
    import pathlib
    import sys
    import tempfile
    fails = []
    for name, fn in sorted(globals().items()):
        if not (name.startswith("test_") and callable(fn)):
            continue
        try:
            if "tmp_path" in inspect.signature(fn).parameters:
                with tempfile.TemporaryDirectory() as d:
                    fn(pathlib.Path(d))
            else:
                fn()
            print(f"ok: {name}")
        except Exception as e:  # noqa: BLE001 - report every failure
            fails.append(name)
            print(f"FAIL: {name}: {type(e).__name__}: {e}")
    print("FAILED: " + ", ".join(fails) if fails else "ALL CHECKS PASSED")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
