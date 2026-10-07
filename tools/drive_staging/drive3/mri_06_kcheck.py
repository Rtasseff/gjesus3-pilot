"""Stream M: m175 / m178 (protocol 0118, Ermal, 2021-09-02) -- the staged reconstruction is the one on K: (read-only).

    python mri_06_kcheck.py

The drive holds each of the two studies twice, reconstructed twice (respiracion\\expiración and \\inspiracion). A1 R2:
register the copy byte-identical to Ermal's on K:\\gjesus\\MRI\\Proyecto 0118. mri_01_plan.py picks m175 from
inspiracion and m178 from expiración. This re-hashes every staged file of the two studies and the same relative path on
K:, and requires all equal (and the K: exam to hold no non-k-space file the stage lacks). Writes out\\kcheck.txt.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mri_common as C  # noqa: E402

STUDIES = ["20210902_082356_jrc210902_m175_ermal_1_1", "20210902_115741_jrc210902_m178_ermal_1_1"]


def files_under(root):
    res = {}
    for d, _dirs, fs in os.walk(C.lp(root)):
        for f in fs:
            p = os.path.join(d, f)
            res[os.path.relpath(p, C.lp(root))] = p
    return res


def main():
    L, bad = [], 0
    for s in STUDIES:
        st = files_under(os.path.join(C.STAGE, "M01", s))
        k = {r: p for r, p in files_under(os.path.join(C.K0118, s)).items()
             if r.split(os.sep)[0].isdigit() or r == "subject"}
        k = {r: p for r, p in k.items() if not C.is_kspace(os.path.basename(r))}
        exams = {r.split(os.sep)[0] for r in st if os.sep in r}
        k = {r: p for r, p in k.items() if r == "subject" or r.split(os.sep)[0] in exams}
        same = diff = 0
        for r, p in st.items():
            if r not in k:
                L.append(f"  {s}: staged file not on K: {r}")
                bad += 1
                continue
            if C.sha256(p) == C.sha256(k[r]):
                same += 1
            else:
                diff += 1
                L.append(f"  {s}: DIFFERS {r}")
        lacking = sorted(set(k) - set(st))
        bad += diff + len(lacking)
        L.append(f"{s}: staged {len(st)} files, identical on K: {same}, differ {diff}; K: files (of these exams, "
                 f"k-space excluded) the stage lacks: {len(lacking)} {lacking[:5]}")
    L.append("RESULT: " + ("PASS" if not bad else f"FAIL ({bad})"))
    open(C.out("kcheck.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
