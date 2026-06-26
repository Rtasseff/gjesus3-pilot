"""Unit tests for config.fanout_ni_recons — NI one-acquisition-per-reconstruction.

Pure (no disk, no NAS): feeds a synthetic anchor case (with an already-parsed NI
sidecar section) to the fan-out and checks the per-recon split, the stable
per-recon original_name, the scoped sidecar, empty-recon skipping, and deepcopy
isolation. Run: python tools/test_ni_per_recon.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from ingest import config

_fail = 0


def check(cond, msg):
    global _fail
    print(("  ok:   " if cond else "  FAIL: ") + msg)
    if not cond:
        _fail += 1


def make_case(by_index):
    return {
        "source_path": "/box/irene/260212/0324/0324_m61/20260212130722_CT",
        "ingest": {"copy_strategy": "ni_molecubes", "per_recon_acquisitions": True},
        "discovered": {"modality": "CT", "subject": "0324_m61",
                       "acq_datetime_full": "20260212130722"},
        "acquisition_datetime": "2026-02-12T13:07:22",
        "original_name": "260212/0324/0324_m61/20260212130722_CT",
        "ecosystem_section": {
            "reconstruction": {
                "recons_present": sorted(by_index),
                "by_index": by_index,
            },
            "_raw_metadata": {
                "reconparams_by_idx": {i: {"p": i} for i in by_index},
            },
        },
    }


REL = "260212/0324/0324_m61/20260212130722_CT"


def dcoms(*names):
    return [{"dst_basename": n, "src_relpath": f"recon_x/{n}", "headers": {}} for n in names]


# 1. mixed: recon 0 + 2 have DICOMs, recon 1 is empty -> 2 cases, recon 1 skipped
case = make_case({
    "0": {"algorithm": "a", "dicoms": dcoms("recon0.dcm")},
    "1": {"algorithm": "b", "dicoms": []},
    "2": {"algorithm": "c", "dicoms": dcoms("recon2.dcm")},
})
out = config.fanout_ni_recons(case, REL)
check(len(out) == 2, "mixed -> 2 cases (the empty recon_1 skipped)")
idxs = sorted(c["ni_recon_idx"] for c in out)
check(idxs == ["0", "2"], "fanned-out recon indices are 0 and 2")
c0 = [c for c in out if c["ni_recon_idx"] == "0"][0]
check(c0["original_name"] == REL + "/recon_0", "per-recon original_name = <anchor>/recon_0 (stable dedup key)")
check(c0["discovered"]["ni_recon_idx"] == "0", "discovered.ni_recon_idx set (for the link name)")
rb0 = c0["ecosystem_section"]["reconstruction"]
check(rb0["recons_present"] == ["0"], "sidecar reconstruction scoped: recons_present == [0]")
check(list(rb0["by_index"].keys()) == ["0"], "sidecar by_index scoped to recon 0 only")
check(list(c0["ecosystem_section"]["_raw_metadata"]["reconparams_by_idx"].keys()) == ["0"],
      "sidecar reconparams_by_idx scoped to recon 0 only")

# 2. deepcopy isolation: original case + siblings are untouched
check(set(case["ecosystem_section"]["reconstruction"]["by_index"].keys()) == {"0", "1", "2"},
      "original case's by_index is untouched (deepcopy, not mutated)")
c2 = [c for c in out if c["ni_recon_idx"] == "2"][0]
c0["discovered"]["mutated"] = True
check("mutated" not in c2["discovered"], "mutating one fanned case does not leak into a sibling")

# 3. all recons empty -> [] (whole anchor skipped, nothing registered)
out = config.fanout_ni_recons(make_case({"0": {"dicoms": []}, "1": {"dicoms": []}}), REL)
check(out == [], "all recons empty -> [] (skip the anchor)")

# 4. no recon dirs at all (empty by_index) -> []
out = config.fanout_ni_recons(make_case({}), REL)
check(out == [], "no recons at all -> []")

# 5. numeric sort: recon_10 after recon_2 (not lexicographic)
case = make_case({str(i): {"dicoms": dcoms(f"recon{i}.dcm")} for i in (0, 2, 10)})
out = config.fanout_ni_recons(case, REL)
check([c["ni_recon_idx"] for c in out] == ["0", "2", "10"], "recon indices sorted numerically (10 after 2)")

print("\nALL NI PER-RECON CHECKS PASSED" if _fail == 0 else f"\n{_fail} CHECK(S) FAILED")
sys.exit(1 if _fail else 0)
