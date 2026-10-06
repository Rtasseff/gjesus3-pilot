"""Fingerprint a NAS root's registries (read-only) so a dry run can be shown to have changed nothing.

    python petct_10_bracket.py snap <nas_root> <label>        -> out\\bracket_<label>.json
    python petct_10_bracket.py compare <labelA> <labelB>

Records size, mtime_ns and SHA-256 of every file directly under <nas_root>\\registries\\.
"""
import hashlib
import json
import os
import sys

sys.dont_write_bytecode = True
OUT = r"D:\projects\gjesus3\drive3_streams\petct\out"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


def snap(root, label):
    reg = os.path.join(root, "registries")
    d = {}
    for n in sorted(os.listdir(reg)):
        p = os.path.join(reg, n)
        if os.path.isfile(p):
            st = os.stat(p)
            d[n] = [st.st_size, st.st_mtime_ns, sha(p)]
    with open(os.path.join(OUT, f"bracket_{label}.json"), "w", encoding="utf-8") as f:
        json.dump({"root": root, "files": d}, f, indent=1)
    print(f"{label}: {len(d)} files fingerprinted under {reg}")


def compare(a, b):
    A = json.load(open(os.path.join(OUT, f"bracket_{a}.json"), encoding="utf-8"))["files"]
    B = json.load(open(os.path.join(OUT, f"bracket_{b}.json"), encoding="utf-8"))["files"]
    diff = sorted(n for n in set(A) | set(B) if A.get(n) != B.get(n))
    print(f"{a} -> {b}: {len(A)} / {len(B)} files; changed: {diff if diff else 'NONE'}")
    return 1 if diff else 0


if __name__ == "__main__":
    if sys.argv[1] == "snap":
        snap(sys.argv[2], sys.argv[3])
    else:
        sys.exit(compare(sys.argv[2], sys.argv[3]))
