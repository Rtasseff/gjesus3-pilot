"""Stream N, step 6: stage the drive's reconstructions on D: in the S:\\gnuclear snapshot's own layout.

    <tree>\\<year>\\Jesus\\MJ\\<drive relpath>          (the two renamed files get the scanner's name)

Trees under D:\\projects\\gjesus3\\drive3_streams\\petct\\stage\\:
  new102      the 102 that exist nowhere else          -> the production source of batch N-D
  inprod290   the 290 production already holds         -> the dedup proof (a dry run must list 0)
  snaponly100 the drive copies of the 100 in the snapshot -> only for the whole-drive dry run
  all492      hard links of the three (D: to D:, no bytes)

The drive copy (J:\\_staging_drive3_MJ\\...\\files) is opened 'rb' only; nothing is written on J:.
Each file is copied to <dst>.part, its SHA-256 computed in the same pass and compared with the
drive manifest's (plan_stage_all.csv carries it); only a match is renamed into place. Re-runnable:
a file already staged with the manifest's size is re-hashed and kept if it matches.
Writes stage\\_STAGED.csv.
"""
import csv
import hashlib
import os
import sys

sys.dont_write_bytecode = True
csv.field_size_limit(2 ** 31 - 1)
OUT = r"D:\projects\gjesus3\drive3_streams\petct\out"
STAGE = r"D:\projects\gjesus3\drive3_streams\petct\stage"
DRIVE = r"J:\_staging_drive3_MJ\drive3_MJesus_WX22D623YP29\files"
TREE = {"NEW": "new102", "in production": "inprod290", "only in the S": "snaponly100"}
CHUNK = 8 << 20


def lp(p):
    ap = os.path.abspath(p)
    return ap if ap.startswith("\\\\?\\") else "\\\\?\\" + ap


def sha256(p):
    h = hashlib.sha256()
    with open(lp(p), "rb") as f:
        for b in iter(lambda: f.read(CHUNK), b""):
            h.update(b)
    return h.hexdigest()


def copy_verified(src, dst, want_sha, want_size):
    if not os.path.abspath(dst).lower().startswith(STAGE.lower() + os.sep):
        raise RuntimeError(f"refusing to write outside {STAGE}: {dst}")
    os.makedirs(lp(os.path.dirname(dst)), exist_ok=True)
    if os.path.exists(lp(dst)) and os.path.getsize(lp(dst)) == want_size:
        if sha256(dst) == want_sha:
            return "kept"
        os.remove(lp(dst))
    tmp = dst + ".part"
    h = hashlib.sha256()
    n = 0
    with open(lp(src), "rb") as fi, open(lp(tmp), "wb") as fo:
        for b in iter(lambda: fi.read(CHUNK), b""):
            fo.write(b)
            h.update(b)
            n += len(b)
    if h.hexdigest() != want_sha or n != want_size:
        os.remove(lp(tmp))
        raise RuntimeError(f"MISMATCH {src}: {h.hexdigest()} / {n} vs manifest {want_sha} / {want_size}")
    os.replace(lp(tmp), lp(dst))
    return "copied"


def main():
    plan = list(csv.DictReader(open(os.path.join(OUT, "plan_stage_all.csv"), encoding="utf-8", newline="")))
    out, counts = [], {}
    for r in plan:
        tree = next(v for k, v in TREE.items() if r["coverage"].startswith(k))
        rel = r["staged_rel"].replace("/", os.sep)
        dst = os.path.join(STAGE, tree, rel)
        src = os.path.join(DRIVE, r["drive_relpath"])
        how = copy_verified(src, dst, r["sha256"], int(r["size"]))
        counts[(tree, how)] = counts.get((tree, how), 0) + 1
        link = os.path.join(STAGE, "all492", rel)
        os.makedirs(lp(os.path.dirname(link)), exist_ok=True)
        if os.path.exists(lp(link)):
            if not os.path.samefile(lp(link), lp(dst)):
                raise RuntimeError(f"all492 holds a different file at {link}")
        else:
            os.link(lp(dst), lp(link))
        out.append({"tree": tree, "acq_key": r["acq_key"], "staged_rel": r["staged_rel"],
                    "drive_relpath": r["drive_relpath"], "sha256": r["sha256"], "size": r["size"],
                    "verified": "sha256 == drive manifest"})
    with open(os.path.join(STAGE, "_STAGED.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    for k in sorted(counts):
        print(k, counts[k])
    print(f"staged {len(out)} files; all492 hard links: {len(out)}")


if __name__ == "__main__":
    main()
