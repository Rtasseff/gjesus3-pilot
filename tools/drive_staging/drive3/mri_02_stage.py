"""Stream M, step 2: stage the exams to register on D:, flat <batch>\\<study>\\<exam>\\, k-space excluded.

    python mri_02_stage.py [<plan_stage_files[_tag].csv>]        -> out\\stage_result[_tag].csv

The staged drive copy (J:\\_staging_drive3_MJ\\...\\files) is opened 'rb' only; nothing is written on J:. Each file is
copied to <dst>.part with its SHA-256 computed in the same pass and compared with the drive manifest's (carried in
plan_stage_files.csv); only a match is renamed into place. Re-runnable: a file already staged with the manifest's
size is re-hashed and kept if it matches. 16 workers (small files over SMB). Writes out\\stage_result.csv.

Why a copy and not links: the staged drive copy is on the NAS, the stage on D: (no cross-volume hard links), and
convert_staged_exams.py writes its DICOM into the exam it converts, which must never be the read-only staged copy.
Why flat <study>\\<exam>: original_name = "<study>/<exam>", the shape of every production MRI row, so a later
ingest of the same exam from the platform's archive is skipped as already registered (the staging_dir trap).
"""
import collections
import concurrent.futures as cf
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mri_common as C  # noqa: E402


def copy_verified(src, dst, want_sha, want_size):
    if not os.path.abspath(dst).lower().startswith(C.STAGE.lower() + os.sep):
        raise RuntimeError(f"refusing to write outside {C.STAGE}: {dst}")
    os.makedirs(C.lp(os.path.dirname(dst)), exist_ok=True)
    if os.path.exists(C.lp(dst)) and os.path.getsize(C.lp(dst)) == want_size:
        if C.sha256(dst) == want_sha:
            return "kept"
        os.remove(C.lp(dst))
    tmp = dst + ".part"
    h = hashlib.sha256()
    n = 0
    with open(C.lp(src), "rb") as fi, open(C.lp(tmp), "wb") as fo:
        for b in iter(lambda: fi.read(C.CHUNK), b""):
            fo.write(b)
            h.update(b)
            n += len(b)
    if h.hexdigest() != want_sha or n != want_size:
        os.remove(C.lp(tmp))
        return f"MISMATCH {h.hexdigest()[:12]}/{n} vs manifest {want_sha[:12]}/{want_size}"
    os.replace(C.lp(tmp), C.lp(dst))
    return "copied"


def one(r):
    src = os.path.join(C.DRIVE, r["drive_relpath"])
    dst = os.path.join(C.STAGE, r["staged_rel"])
    try:
        how = copy_verified(src, dst, r["sha256"], int(r["size"]))
    except Exception as e:  # noqa: BLE001 -- recorded per file
        how = f"ERROR {type(e).__name__}: {str(e)[:150]}"
    return {**r, "result": how}


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(C.OUT, "plan_stage_files.csv")
    plan = C.rows(src)
    tag = os.path.splitext(os.path.basename(src))[0].replace("plan_stage_files", "")
    res, n = [], 0
    with cf.ThreadPoolExecutor(16) as ex:
        for r in ex.map(one, plan):
            res.append(r)
            n += 1
            if n % 5000 == 0:
                print(f"{n}/{len(plan)} {dict(collections.Counter(x['result'].split(' ')[0] for x in res))}", flush=True)
    C.write_csv(C.out(f"stage_result{tag}.csv"), res)
    c = collections.Counter(x["result"].split(" ")[0] for x in res)
    print("DONE", dict(c), "per batch", dict(collections.Counter((x["batch"], x["result"].split(" ")[0]) for x in res)))
    bad = [x for x in res if x["result"] not in ("copied", "kept")]
    for b in bad[:20]:
        print("  BAD", b["staged_rel"], b["result"])
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
