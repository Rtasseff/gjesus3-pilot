"""condition.is_control / timepoint_days per case, and the dry-run metadata preview (BACKLOG 2026-11-07).

Run: python -m pytest tools/test_condition_per_case.py
"""
import ingest_raw
from ingest import resolver


def test_is_control_resolves_per_case_from_discovered():
    block = {"is_control": "${discovered.drv_is_control}", "disease_state": "${discovered.drv_state}"}
    assert resolver.resolve_condition_block(block, {"drv_is_control": "true", "drv_state": "baseline"})["is_control"] is True
    out = resolver.resolve_condition_block(block, {"drv_is_control": "false", "drv_state": "ARDS"})
    assert out["is_control"] is False and out["disease_state"] == "ARDS"


def test_missing_or_blank_column_is_unknown_not_an_error():
    block = {"is_control": "${discovered.drv_is_control}", "timepoint_days": "${discovered.drv_day}"}
    out = resolver.resolve_condition_block(block, {})
    assert out["is_control"] is None and out["timepoint_days"] is None
    assert resolver.resolve_condition_block(block, {"drv_is_control": ""})["is_control"] is None


def test_timepoint_days_resolves_to_a_number():
    out = resolver.resolve_condition_block({"timepoint_days": "${discovered.d}"}, {"d": "7"})
    assert out["timepoint_days"] == 7


def test_batch_constants_unchanged():
    assert resolver.resolve_condition_block({"is_control": True}, {})["is_control"] is True
    assert resolver.resolve_condition_block({"is_control": "false"}, {})["is_control"] is False
    assert resolver.resolve_condition_block(None, {})["source"] == "unknown"


def test_dry_run_preview_warns_on_unknown_is_control():
    lines = []
    cfg = {"sample_type": "organism", "discovered": {}}
    ingest_raw._preview_sidecar_metadata(cfg, lambda m, lvl="INFO": lines.append((lvl, m)))
    assert any(lvl == "WARN" and "is_control is null" in m for lvl, m in lines)
    assert any("Condition:" in m and "is_control=None" in m for _, m in lines)


def test_dry_run_preview_shows_per_case_condition_and_skips_non_biological():
    lines = []
    cfg = {"sample_type": "organism", "discovered": {"c": "true"}, "condition": {"is_control": "${discovered.c}"}}
    ingest_raw._preview_sidecar_metadata(cfg, lambda m, lvl="INFO": lines.append((lvl, m)))
    assert any("is_control=True" in m for _, m in lines)
    assert not any(lvl == "WARN" for lvl, _ in lines)
    lines.clear()
    ingest_raw._preview_sidecar_metadata({"sample_type": "material", "discovered": {}}, lambda m, lvl="INFO": lines.append((lvl, m)))
    assert lines == []


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
