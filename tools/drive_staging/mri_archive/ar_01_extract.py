"""Stream AR, step 1: extract the pulled archives (local copies only) to D:\\projects\\gjesus3\\mri_archive\\extract\\.

    python ar_01_extract.py [--workers N] [--tiers C,A2,B,A] [--limit N]

Reads only the tarballs the fetch has VERIFIED (fetch_manifest.csv status 'verified', file present); never writes
under pull\\. Resumable: a study with extract\\_manifests\\<study>.done is skipped. One study per tarball:
  * stream-read (tarfile 'r|*', gz or xz) through a wrapper that computes the SHA-1 and SHA-256 of the compressed bytes
    in the same pass, compared with the fetch manifest's computed value: the tarball extracted is the one verified;
  * every member validated by tarfile.data_filter (no absolute path, no '..', no link out); every member must sit under
    the top folder <study>/;
  * k-space (fid, ser, rawdata.job*) is NOT extracted (the ingest keeps DICOM; conversion needs 2dseq and the parameter
    files): listed with its size only. Links and special files are listed, not extracted;
  * every extracted file's SHA-256 computed while it is written;
  * written to <tier dir>\\<study>.partial\\, renamed to <tier dir>\\<study>\\ when complete. Tier dirs: C for the
    originals check, _in for the new studies (A, A2, B), sorted into batch folders later (ar_05_plan.py --sort).
A tarball that ends early (the archive's own copy is short: its .sha1 was made from it) is salvaged: every member read
completely is kept, the member being read is removed, and .done records "truncated" with the incomplete exam.
Writes extract\\_manifests\\<study>.csv (member, kind, size, mtime, sha256, action) and <study>.done (JSON), and
out\\extract_<time>.log.
"""
import argparse
import concurrent.futures as cf
import datetime
import hashlib
import json
import lzma
import os
import shutil
import sys
import tarfile
import time
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ar_common as C  # noqa: E402

ORDER = {"C": 0, "A2": 1, "B": 2, "A": 3}


class HashReader:
    def __init__(self, f):
        self.f, self.h1, self.h2, self.n = f, hashlib.sha1(), hashlib.sha256(), 0

    def read(self, n=-1):
        b = self.f.read(n)
        self.h1.update(b)
        self.h2.update(b)
        self.n += len(b)
        return b


def home(tier):
    return "C" if tier == "C" else "_in"


def extract_one(study, tier, tarpath, expect_sha1, expect_sha256):
    t0 = time.time()
    dest = C.w(C.EXTRACT, home(tier), study + ".partial")     # creates only the tier dir
    dest_final = dest[:-len(".partial")]
    if os.path.exists(C.lp(dest)):
        shutil.rmtree(C.lp(dest))
    if os.path.exists(C.lp(dest_final)):
        raise RuntimeError(f"{dest_final} exists without a .done: remove it by hand after a look")
    os.makedirs(C.lp(dest))
    recs, errors = [], []
    n_x = b_x = n_k = b_k = 0
    truncated = None
    current = {}
    with open(tarpath, "rb") as raw:
        hr = HashReader(raw)
        try:
          with tarfile.open(fileobj=hr, mode="r|*") as tf:
            for m in tf:
                name = m.name.rstrip("/")
                kind = ("dir" if m.isdir() else "file" if m.isfile() else "symlink" if m.issym()
                        else "hardlink" if m.islnk() else "other")
                rec = {"member": name, "kind": kind, "size": m.size if m.isfile() else 0, "mtime": int(m.mtime),
                       "sha256": "", "action": ""}
                recs.append(rec)
                try:
                    tarfile.data_filter(m, dest)
                except tarfile.FilterError as e:
                    rec["action"] = f"refused: {type(e).__name__}"
                    errors.append(f"{name}: {rec['action']}")
                    continue
                parts = name.split("/")
                if parts[0] != study:
                    rec["action"] = "refused: outside the study folder"
                    errors.append(f"{name}: {rec['action']}")
                    continue
                inner = parts[1:]
                if kind == "dir":
                    try:
                        if inner:
                            os.makedirs(C.lp(os.path.join(dest, *inner)), exist_ok=True)
                        rec["action"] = "dir"
                    except OSError as e:
                        rec["action"] = f"error: {e}"
                        errors.append(f"{name}: {e}")
                    continue
                if kind != "file":
                    rec["action"] = f"not extracted ({kind})"
                    continue
                if C.is_kspace(parts[-1]):
                    rec["action"] = "not extracted (k-space)"
                    n_k += 1
                    b_k += m.size
                    continue
                target = os.path.join(dest, *inner)
                h = hashlib.sha256()
                src = tf.extractfile(m)
                current = {"rec": rec, "target": target}
                try:
                    os.makedirs(C.lp(os.path.dirname(target)), exist_ok=True)
                    with open(C.lp(target), "wb") as f:
                        for b in iter(lambda: src.read(C.CHUNK), b""):
                            h.update(b)
                            f.write(b)
                except OSError as e:
                    rec["action"] = f"error: {e}"
                    errors.append(f"{name}: {e}")
                    continue
                os.utime(C.lp(target), (m.mtime, m.mtime))
                rec["sha256"] = h.hexdigest()
                rec["action"] = "extracted"
                n_x += 1
                b_x += m.size
                current = {}
        except (tarfile.ReadError, EOFError, zlib.error, lzma.LZMAError) as e:
            # the archive's own copy ends early (its .sha1 was made from the short file): keep every member that was
            # read completely; the member being read is removed, and its exam is marked incomplete
            last = recs[-1]["member"] if recs else ""
            if current:
                if os.path.exists(C.lp(current["target"])):
                    os.remove(C.lp(current["target"]))
                current["rec"]["action"] = "truncated (incomplete, removed)"
                current["rec"]["sha256"] = ""
            parts = last.split("/")
            truncated = {"error": f"{type(e).__name__}: {e}", "last_member_seen": last,
                         "incomplete_exam": parts[1] if len(parts) > 2 and parts[1][:1].isdigit() else ""}
        while hr.read(C.CHUNK):
            pass
    s1, s2 = hr.h1.hexdigest(), hr.h2.hexdigest()
    match = (s1 == expect_sha1) if expect_sha1 else (s2 == expect_sha256) if expect_sha256 else None
    if match is False:
        errors.append(f"tarball hash differs from the fetch manifest: sha1 {s1} / {expect_sha1}, sha256 {s2} / {expect_sha256}")
    C.write_csv(C.w(C.XMAN, study + ".csv"), recs, ["member", "kind", "size", "mtime", "sha256", "action"])
    done = {"study": study, "tier": tier, "tarball": tarpath, "tar_bytes": hr.n, "sha1": s1, "sha256": s2,
            "hash_matches_fetch": match, "members": len(recs), "extracted_files": n_x, "extracted_bytes": b_x,
            "kspace_files": n_k, "kspace_bytes": b_k, "errors": errors, "truncated": truncated, "dir": dest_final,
            "seconds": round(time.time() - t0, 1), "when": datetime.datetime.now().isoformat(timespec="seconds")}
    if errors:
        json.dump(done, open(C.w(C.XMAN, study + ".failed"), "w", encoding="utf-8"), indent=1)
        return done
    os.rename(C.lp(dest), C.lp(dest_final))
    json.dump(done, open(C.w(C.XMAN, study + ".done"), "w", encoding="utf-8"), indent=1)
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--tiers", default="C,A2,B,A")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    tiers = a.tiers.split(",")
    plan = C.pull_plan()
    got = C.fetched()
    done = C.extracted()
    todo = []
    for study, f in got.items():
        p = plan.get(study)
        if not p or p["tier"] not in tiers or study in done:
            continue
        todo.append((ORDER[p["tier"]], study, p["tier"], f["local_path"], f.get("computed_sha1", ""),
                     f.get("computed_sha256", ""), int(f["size"])))
    todo.sort()
    if a.limit:
        todo = todo[:a.limit]
    logp = C.out(f"extract_{datetime.datetime.now():%Y%m%d_%H%M%S}.log")
    log = open(logp, "a", encoding="utf-8")

    def say(s):
        line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {s}"
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()

    say(f"verified locally {len(got)}; already extracted {len(done)}; to extract now {len(todo)} "
        f"({sum(t[6] for t in todo) / 1e9:.1f} GB compressed), workers {a.workers}")
    ok = bad = 0
    with cf.ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(extract_one, s, t, p, e1, e2): s for _, s, t, p, e1, e2, _ in todo}
        for i, fu in enumerate(cf.as_completed(futs), 1):
            s = futs[fu]
            try:
                d = fu.result()
            except Exception as e:  # noqa: BLE001 -- reported per study, the run goes on
                bad += 1
                say(f"[{i}/{len(todo)}] FAILED {s}: {type(e).__name__}: {e}")
                continue
            if d["errors"]:
                bad += 1
                say(f"[{i}/{len(todo)}] ERRORS {s}: {d['errors'][:3]}")
            else:
                ok += 1
                say(f"[{i}/{len(todo)}] OK {d['tier']} {s}: {d['extracted_files']} files {d['extracted_bytes'] / 1e9:.2f} GB, "
                    f"k-space {d['kspace_files']} ({d['kspace_bytes'] / 1e9:.2f} GB) not extracted; hash==fetch "
                    f"{d['hash_matches_fetch']}; {d['seconds']} s"
                    + (f"; TRUNCATED ARCHIVE: {d['truncated']}" if d.get("truncated") else ""))
    say(f"END: ok {ok}, failed {bad}; extracted now in total {len(C.extracted())}")


if __name__ == "__main__":
    main()
