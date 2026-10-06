#!/usr/bin/env python3
"""c_crosscheck.py -- stream C (drive 3): the pixel check's decisions re-checked by ANOTHER ROUTE.

The pixel check (c_groups.py, r4_groups.py's tests) compares stored tile payloads by SHA-256 and byte search.
This script instead DECODES whole images with czifile (`asarray`, the library's own mosaic assembly) and
compares the arrays, on:
  * every planned file dropped as a re-save of a PRODUCTION acquisition, against that production file;
  * a sample of the same-name re-saves dropped within the plan (the smallest N), against the file kept;
  * every crop routed to non-raw: the crop's image is found, pixel for pixel, inside its original's image;
  * the held ID187 case: production's single downsampled subblock against the drive file's image reduced to
    the same size (rank correlation: is it a preview of the same image?).
Read-only (J:\\ production primaries and the local mirror). Writes <plan>\\crosscheck.txt.

    python tools/drive_staging/drive3/c_crosscheck.py [--sample 12]
"""
import argparse
import collections
import io
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.dirname(HERE)
sys.path.insert(0, DS)
import ingest_plan as P  # noqa: E402
import r4_groups as R  # noqa: E402

P.use_profile("drive3_2026-10")
MAX_BYTES = 1_200_000_000            # decode files up to this size (memory); larger ones are reported, not skipped silently


def image(path):
    import czifile
    import numpy as np
    with czifile.CziFile(R.longpath(path)) as czi:
        a = czi.asarray()
    return np.squeeze(a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=12)
    args = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    import numpy as np
    L = []

    def say(m):
        L.append(m)
        print(m, flush=True)

    cand = list(P.rcsv(os.path.join(P.OUT, "pixel_candidates.csv")))
    path_of = {(r["group"], r["member"]): r["path"] for r in cand}
    size_of = {(r["group"], r["member"]): int(r["size"]) for r in cand}
    dec = list(P.rcsv(os.path.join(P.OUT, "pixel_decisions.csv")))
    exc = {x["sha256"]: x for x in P.rcsv(os.path.join(P.OUT, "excluded.csv"))}
    nonraw = list(P.rcsv(os.path.join(P.OUT, "nonraw_derived.csv")))
    group_of = {d["member"]: d["group"] for d in dec if d["role"] == "plan"}
    tally = collections.Counter()

    def compare(label, g, a, b):
        pa, pb = path_of[(g, a)], path_of[(g, b)]
        if max(size_of[(g, a)], size_of[(g, b)]) > MAX_BYTES:
            say(f"  NOT DECODED (over {MAX_BYTES / 1e9:.1f} GB): {label}")
            tally["not decoded"] += 1
            return
        x, y = image(pa), image(pb)
        same = x.shape == y.shape and np.array_equal(x, y)
        tally["identical" if same else "DIFFERENT"] += 1
        say(f"  {'identical' if same else 'DIFFERENT'} {x.shape} {label}")

    say("1. planned files dropped as re-saves of a PRODUCTION acquisition, decoded and compared:")
    for sha, x in exc.items():
        if x["reason"] == "resave-of-production" and sha in group_of:
            g = group_of[sha]
            kept = x["detail"].split("; kept ")[-1]
            compare(f"{x['path'].split('/')[-1]} vs {kept}", g, sha, kept)
    say(f"2. the {args.sample} smallest same-name re-saves dropped within the plan, against the file kept:")
    within = sorted((x for sha, x in exc.items() if x["reason"] == "resave-within-plan" and sha in group_of),
                    key=lambda x: int(x["size"]))[:args.sample]
    for x in within:
        g = group_of[x["sha256"]]
        compare(x["path"].split("/")[-1], g, x["sha256"], x["detail"].split("; kept ")[-1])
    say("3. every crop routed to non-raw: found pixel for pixel inside its original:")
    for r in nonraw:
        if r["class"] != "export: crop":
            continue
        g = group_of[r["sha256"]]
        parent = r["parent_sha256"] or r["parent_acq_id"]
        if max(size_of[(g, r["sha256"])], size_of[(g, parent)]) > MAX_BYTES:
            say(f"  NOT DECODED: {r['relpath'].split(chr(92))[-1]}")
            tally["not decoded"] += 1
            continue
        a, b = image(path_of[(g, r["sha256"])]), image(path_of[(g, parent)])
        if a.ndim == 2:
            a, b = a[..., None], b[..., None]
        if a.ndim == 3 and a.shape[0] <= 4 and a.shape[0] == b.shape[0]:      # channels first -> last
            a, b = np.moveaxis(a, 0, -1), np.moveaxis(b, 0, -1)
        hits = R.Haystack(np.ascontiguousarray(b)).locate(np.ascontiguousarray(a)) if a.ndim == 3 else []
        tally["crop found" if hits else "crop NOT FOUND"] += 1
        say(f"  {'found at ' + str(hits[0]) if hits else 'NOT FOUND'} {a.shape} in {b.shape}: "
            f"{r['relpath'].split(chr(92))[-1]}")
    say("4. the held ID187 case: production's preview against the drive file reduced to the preview's size:")
    for d in dec:
        if d["role"] == "production" and d["complete"] == "N":
            g = d["group"]
            drv = next(x for x in dec if x["group"] == g and x["role"] == "plan")
            import czifile
            with czifile.CziFile(R.longpath(path_of[(g, d["member"])])) as czi:
                e = czi.filtered_subblock_directory[0]
                prev = np.squeeze(e.read_segment_data(czi).data())
            full = image(path_of[(g, drv["member"])])
            chans = full if full.ndim == 3 else full[None]
            h, w = prev.shape[-2:]
            for c, ch in enumerate(chans):
                ch = ch.astype(np.float64)
                ys = np.linspace(0, ch.shape[0], h + 1).astype(int)        # block means: a pyramid level is an
                xs = np.linspace(0, ch.shape[1], w + 1).astype(int)        # area average, not a point sample
                mean = np.add.reduceat(np.add.reduceat(ch, ys[:-1], axis=0), xs[:-1], axis=1) \
                    / np.outer(np.diff(ys), np.diff(xs))
                rho = R.rank_correlation(prev.astype(np.float64), mean)
                pr = float(np.corrcoef(prev.astype(np.float64).ravel(), mean.ravel())[0, 1])
                say(f"  {drv['name']}: production's preview {prev.shape} vs the drive file's channel {c} "
                    f"{ch.shape} as block means: rank correlation {rho:.3f}, Pearson {pr:.3f}")
                tally[f"preview rho C{c}"] = round(rho, 3)
    say("RESULT: " + ", ".join(f"{k} {v}" for k, v in tally.items()))
    with io.open(os.path.join(P.OUT, "crosscheck.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
