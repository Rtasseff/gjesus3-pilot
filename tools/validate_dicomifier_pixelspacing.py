"""Validate the Dicomifier-vs-Bruker PixelSpacing axis-order workaround.

A regression check for the FID→DICOM regeneration path (`tasks.md §3.1`).
Dicomifier 2.5.3 on ParaVision 7.0.0 emits PixelSpacing in swapped axis
order vs Bruker's GUI export (`[col, row]` instead of DICOM Part 3's
`[row, col]`), producing visible geometric distortion in viewers. The
workaround in `tools/ingest/paravision_regen.py` is to always swap.

This script validates the workaround by:
1. Geometric FOV-consistency check on every Dicomifier-generated series
   (Rows × PS[0] ≈ Cols × PS[1] under DICOM Part 3 → "matches_unswapped";
   the inverse → "matches_swapped"). Square images are ambiguous.
2. Direct comparison to Bruker GUI export on the NAS (when present),
   keyed by SeriesInstanceUID.

Initial validation 2026-06-01: 16/16 anisotropic m17 series confirmed
swapped; pattern is deterministic. Re-run after Dicomifier upgrades or
when adding new pulse sequences / acquisition matrices to verify the
"always swap" rule still holds.

Usage (from inside WSL with the dicomifier-pilot env active):
    # Operator post-ingest sanity check — point at one or more ingested
    # <ACQ-ID>.data/ folders of regenerated DICOMs. PASS = every anisotropic
    # series reads "matches_unswapped" (Bruker-correct) and NONE read
    # "matches_swapped" (which would mean the regen workaround didn't apply):
    python tools/validate_dicomifier_pixelspacing.py \
        /mnt/gjesus3/raw/DICOM/2025/2025-10/ACQ-20251016-MRI-001/ACQ-20251016-MRI-001.data

    # No arguments -> the built-in m13/m17 dev validation paths (DICO_* /
    # BRUKER_NAS constants below; edit those for other dev sources).
"""
import argparse
import os
import sys
import pydicom
from collections import defaultdict, Counter

DICO_M13 = "/mnt/d/projects/gjesus3/dicomifier_pilot/m13"
DICO_M17 = "/mnt/d/projects/gjesus3/dicomifier_pilot/m17"
BRUKER_NAS = "/mnt/gjesus3/raw/DICOM/2025/2025-10"  # ACQ-20251016-MRI-* lives here (J: mapped at /mnt/gjesus3 in WSL)


def fov_test(rows, cols, ps):
    """Return 'square' / 'matches_unswapped' / 'matches_swapped' / 'neither'."""
    if rows == cols:
        return "square_ambiguous"
    if not ps or len(ps) != 2:
        return "no_pixelspacing"
    ps0, ps1 = float(ps[0]), float(ps[1])
    fov_a_unswapped = rows * ps0
    fov_b_unswapped = cols * ps1
    fov_a_swapped = rows * ps1
    fov_b_swapped = cols * ps0
    def close(x, y, rel=0.05):
        return abs(x - y) / max(x, y) < rel
    unsw = close(fov_a_unswapped, fov_b_unswapped)
    sw = close(fov_a_swapped, fov_b_swapped)
    if unsw and not sw:
        return "matches_unswapped"  # [row, col] convention → Bruker-correct
    if sw and not unsw:
        return "matches_swapped"    # [col, row] → Dicomifier bug
    if unsw and sw:
        return "either"
    return "neither"


def index_series(directory):
    """Group DICOMs by SeriesInstanceUID; return list of (sn, suid, first_ds, count, desc)."""
    if not os.path.isdir(directory):
        return []
    by_series = defaultdict(list)
    for f in sorted(os.listdir(directory)):
        if not f.endswith(".dcm"):
            continue
        try:
            ds = pydicom.dcmread(os.path.join(directory, f), stop_before_pixels=True)
        except Exception:
            continue
        by_series[ds.SeriesInstanceUID].append((f, ds))
    out = []
    for suid, items in by_series.items():
        sn = getattr(items[0][1], "SeriesNumber", 0) or 0
        desc = str(getattr(items[0][1], "SeriesDescription", "?"))
        out.append((int(sn), suid, items[0][1], len(items), desc))
    return sorted(out)


def analyse(label, directory):
    print(f"\n=== {label} — {directory} ===")
    series = index_series(directory)
    if not series:
        print("  (no DICOMs)")
        return Counter()
    counts = Counter()
    print(f"  {'SN':>10s}  {'Slc':>4s}  {'Rows':>5s} × {'Cols':>5s}  {'PS[0]':>9s}  {'PS[1]':>9s}  Test                      Desc")
    for sn, suid, ds, n, desc in series:
        rows = int(getattr(ds, "Rows", 0))
        cols = int(getattr(ds, "Columns", 0))
        ps = getattr(ds, "PixelSpacing", None)
        ps_str = (f"{float(ps[0]):.5f}", f"{float(ps[1]):.5f}") if ps and len(ps) == 2 else ("?", "?")
        verdict = fov_test(rows, cols, ps)
        counts[verdict] += 1
        print(f"  {sn:>10d}  {n:>4d}  {rows:>5d} × {cols:>5d}  {ps_str[0]:>9s}  {ps_str[1]:>9s}  {verdict:25s}  {desc[:30]}")
    print(f"\n  Per-verdict counts: {dict(counts)}")
    return counts


def compare_bruker(label):
    """For exams that exist on the NAS as Bruker GUI exports, compare PixelSpacing directly."""
    print(f"\n=== Bruker-vs-Dicomifier direct comparison ({label}) ===")
    if not os.path.isdir(BRUKER_NAS):
        print(f"  Bruker NAS path not accessible: {BRUKER_NAS}")
        return
    # Find each ACQ-20251016-MRI-NNN folder and check its DICOMs vs Dicomifier's matching series
    bruker_by_exam = {}
    for acq in sorted(os.listdir(BRUKER_NAS)):
        if not acq.startswith("ACQ-20251016-MRI-"):
            continue
        data_dir = os.path.join(BRUKER_NAS, acq, f"{acq}.data")
        if not os.path.isdir(data_dir):
            continue
        for fname in sorted(os.listdir(data_dir)):
            if not fname.endswith(".dcm"):
                continue
            try:
                ds = pydicom.dcmread(os.path.join(data_dir, fname), stop_before_pixels=True)
            except Exception:
                continue
            key = ds.SeriesInstanceUID
            if key not in bruker_by_exam:
                bruker_by_exam[key] = (acq, fname, ds)
            break  # one DICOM per series is enough

    print(f"  Indexed {len(bruker_by_exam)} Bruker series on NAS.")
    # Now read Dicomifier output and match
    dico_series = index_series(DICO_M17)
    matched = 0
    swap_confirmed = 0
    swap_not_needed = 0
    not_in_bruker = 0
    for sn, suid, ds_d, n, desc in dico_series:
        if suid in bruker_by_exam:
            acq, fname, ds_b = bruker_by_exam[suid]
            ps_b = getattr(ds_b, "PixelSpacing", None)
            ps_d = getattr(ds_d, "PixelSpacing", None)
            if not ps_b or not ps_d:
                continue
            matched += 1
            ps_b_t = (float(ps_b[0]), float(ps_b[1]))
            ps_d_t = (float(ps_d[0]), float(ps_d[1]))
            swapped = (abs(ps_b_t[0] - ps_d_t[1]) < 1e-6) and (abs(ps_b_t[1] - ps_d_t[0]) < 1e-6)
            same = (abs(ps_b_t[0] - ps_d_t[0]) < 1e-6) and (abs(ps_b_t[1] - ps_d_t[1]) < 1e-6)
            rows = int(getattr(ds_b, "Rows", 0))
            cols = int(getattr(ds_b, "Columns", 0))
            if same and ps_b_t[0] == ps_b_t[1]:
                tag = "same (square or isotropic — ambiguous)"
                swap_not_needed += 1
            elif swapped:
                tag = "SWAPPED (Dicomifier bug confirmed for this series)"
                swap_confirmed += 1
            elif same:
                tag = "same — no swap"
                swap_not_needed += 1
            else:
                tag = f"DIFFERENT but not a clean swap: B={ps_b_t}  D={ps_d_t}"
            print(f"  SN {sn:>10d} {rows:>4d}×{cols:>4d} desc={desc[:25]:25s}  {tag}")
        else:
            not_in_bruker += 1

    print(f"\n  Summary: matched_with_bruker={matched}, swap_confirmed={swap_confirmed}, swap_not_needed_or_ambiguous={swap_not_needed}, not_in_bruker={not_in_bruker}")


def _legacy_dev_run():
    """The original hardcoded-path dev validation (m13/m17 vs Bruker on NAS)."""
    analyse("m13 (Dicomifier, no Bruker comparison)", DICO_M13)
    analyse("m17 (Dicomifier)", DICO_M17)
    compare_bruker("m17 vs Bruker GUI on NAS")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Validate regenerated-DICOM PixelSpacing axis order via FOV "
                    "consistency. Operator post-ingest sanity check for the MRI "
                    "no-DICOM regeneration path (see the MRI regeneration runbook)."
    )
    ap.add_argument(
        "dicom_dir", nargs="*",
        help="One or more folders of .dcm files to check (e.g. an ingested "
             "<ACQ-ID>.data/). Omit to run the built-in m13/m17 dev paths.",
    )
    args = ap.parse_args(argv)

    if not args.dicom_dir:
        _legacy_dev_run()
        return 0

    total = Counter()
    for d in args.dicom_dir:
        label = os.path.basename(os.path.normpath(d)) or d
        total.update(analyse(label, d))

    # Verdict: a regenerated, workaround-applied batch must NOT contain any
    # "matches_swapped" series (that would mean the PixelSpacing swap didn't
    # apply). Square/ambiguous series are fine.
    swapped = total.get("matches_swapped", 0)
    print(f"\n=== OVERALL: {dict(total)} ===")
    if swapped:
        print(f"FAIL: {swapped} series still read as SWAPPED ([col,row]) — the "
              f"PixelSpacing workaround did NOT apply. Re-check the regeneration.")
        return 1
    print("PASS: no swapped-axis series — PixelSpacing is in Bruker-correct [row,col] order.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
