#!/usr/bin/env python3
"""test_value_fields.py — invariants for the "values to record" catalogue.

The microscopy GUI's builder rows and the runner's per-batch "Fill in for this
batch" gaps are BOTH driven by the single catalogue in value_fields.py. This
test guards that catalogue so adding/renaming a field can't silently break the
blank-in-builder -> fillable-in-runner behaviour (the bug that left
`registry.session_id` un-promptable while `registry.project_hint` worked).

It deliberately imports value_fields.py and config_builder.py DIRECTLY by path
(both are pure modules, no Flask / czifile), so it runs anywhere Python does.

Run:  python tools/operator/test_value_fields.py
"""

import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    """Load a sibling pure-Python module by path (no package machinery)."""
    spec = importlib.util.spec_from_file_location(
        f"gj_test_{name}", os.path.join(_HERE, f"{name}.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vf = _load("value_fields")
cb = _load("config_builder")

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


REQUIRED_KEYS = {"key", "label", "kind", "hint", "star", "required", "gap"}


def test_shape():
    print("[catalogue shape]")
    fields = vf.VALUE_FIELDS
    check(isinstance(fields, list) and fields, "VALUE_FIELDS is a non-empty list")
    keys = [f.get("key") for f in fields]
    check(len(keys) == len(set(keys)), f"field keys are unique ({keys})")
    for f in fields:
        kk = f.get("key", "<missing>")
        check(REQUIRED_KEYS <= set(f), f"{kk}: has all of {sorted(REQUIRED_KEYS)}")
        check(f.get("kind") in vf.VALID_KINDS,
              f"{kk}: kind {f.get('kind')!r} in {vf.VALID_KINDS}")
        check(isinstance(f.get("label"), str) and f.get("label"),
              f"{kk}: has a non-empty label")
        for flag in ("star", "required", "gap"):
            check(isinstance(f.get(flag), bool), f"{kk}: {flag} is a bool")


def test_required_implies_gap():
    # A field that BLOCKS ingest when blank must be gap-capable — otherwise the
    # runner could never surface it for the operator to fill, deadlocking ingest.
    print("[required => gap-capable]")
    for f in vf.VALUE_FIELDS:
        if f.get("required"):
            check(f.get("gap"), f"{f['key']}: required field is gap-capable")


def test_helpers():
    print("[helpers]")
    gaps = vf.gap_fields()
    builder = vf.builder_fields()
    gap_keys = {f["key"] for f in gaps}
    expect = {f["key"] for f in vf.VALUE_FIELDS if f["gap"]}
    check(gap_keys == expect, "gap_fields() returns exactly the gap-capable keys")
    check(len(builder) == len(vf.VALUE_FIELDS), "builder_fields() returns every field")
    # returned dicts must be COPIES — a caller (the Flask layer) must not be able
    # to mutate the module-level source of truth.
    if builder:
        builder[0]["label"] = "MUTATED"
        check(vf.VALUE_FIELDS[0]["label"] != "MUTATED",
              "builder_fields() returns copies (source not mutated)")


def test_keys_are_real_override_targets():
    # Every catalogue key must be something config_builder actually accepts as an
    # override, INCLUDING the explicit "" a gap field is saved as when blank.
    # If a key isn't on the whitelist the recipe would silently carry a value the
    # ingest pipeline never applies — the failure mode this catalogue prevents.
    print("[keys are valid override targets]")
    for f in vf.VALUE_FIELDS:
        key = f["key"]
        try:
            cfg = cb.build_config({}, {key: ""})
        except cb.OverrideError as e:
            check(False, f"{key}: rejected by config_builder ({e})")
            continue
        if "." in key:
            head, leaf = key.split(".", 1)
            applied = (cfg.get(head) or {}).get(leaf, "__missing__")
        else:
            applied = cfg.get(key, "__missing__")
        check(applied == "", f"{key}: accepted by config_builder and applied")


def main():
    test_shape()
    test_required_implies_gap()
    test_helpers()
    test_keys_are_real_override_targets()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)} check(s)):")
        for m in FAILS:
            print(f"  - {m}")
        raise SystemExit(1)
    print("All value_fields invariants hold.")


if __name__ == "__main__":
    main()
