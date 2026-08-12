#!/usr/bin/env python3
"""pull_ni_gnuclear.py — stage a frozen, verified snapshot of the MFB Nuclear-Imaging
DICOMs from the active working space `S:\\gnuclear` onto gjesus3 staging.

WHY THIS EXISTS (read before changing it)
-----------------------------------------
`S:\\gnuclear` is a *live researcher working space*, not an archive. Two consequences
drove this tool:

  1. **The expensive part of the historical pull is the network transfer**
     (~2.6k DICOMs, ~255 GB across a foreign SMB share), and it does NOT need the
     ingest to be finished. Pulling first, off-hours, decouples the slow part from
     the part still under construction — and lets the ingest be re-run any number
     of times afterwards without ever touching `gnuclear` again.
  2. **It moves under us.** Researchers add, rename and delete in there daily. A
     staged snapshot freezes exactly what we ingested, so the registry's provenance
     means something later.

STRICTLY READ-ONLY ON THE SOURCE. This tool opens files on `S:\\` for reading and
nothing else — no writes, no renames, no deletes, no temp files. Verified by
inspection: the only `open()` against a source path uses mode "rb".

WHAT IT SELECTS
---------------
Files whose *basename* matches the Molecubes reconstructed-DICOM grammar:

    <14-digit timestamp>_<MODALITY>_<ALGO>_<recon>[_frame<F>][_iter<N>][_<extra>].dcm

An **acquisition** is one *reconstruction*: the key is
`(timestamp, modality, algo, recon_idx)`. This deliberately matches the
one-acquisition-per-reconstruction model that the live-box sync landed
(`ingest/config.py::fanout_ni_recons`) so the two sources produce the same shape
and reconcile on the same key. Dynamic-PET per-frame files (`_frame7_iter30`) are
*members of* one reconstruction, not separate acquisitions.

`frameMULTI` handling differs — deliberately and narrowly — from the box path.
The box copy (`ingest_raw.copy_ni_acquisition`) skips `frameMULTI` bundles
unconditionally because per-frame DICOMs always exist alongside them there. In
THIS source they often do not: 63 reconstructions have a `frameMULTI` file and
nothing else, so an unconditional skip would stage 63 empty acquisitions and
silently lose that dynamic PET. Rule here: **drop the `frameMULTI` bundle only
when per-frame siblings of the same reconstruction are present.**

Relative paths are preserved under the destination. That is load-bearing, not
tidiness: per-frame DICOMs of one reconstruction share an identical basename
across `frame_1/iter_30/`, `frame_2/iter_30/`, … so a flattened copy would
overwrite 47 of 48 frames.

USAGE
-----
    # what would be pulled, no bytes moved (safe, ~1 min):
    python tools/pull_ni_gnuclear.py --plan

    # the real pull (resumable — just re-run it if it dies):
    python tools/pull_ni_gnuclear.py --go

    # re-read every staged file and prove it against the recorded hash:
    python tools/pull_ni_gnuclear.py --verify

Resume is automatic: a file already present at the destination with the expected
size is skipped, so re-running after an interruption costs one directory scan.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import time

# --- the reconstructed-DICOM filename grammar (validated against all 2,700
# .dcm under S:\gnuclear\<year>\Jesus\ on 2026-08-12: 2,690 match, and the 10
# that do not are analysis derivatives — ATTMAP, CT_PET_coreg, *-suv — which we
# correctly do not want).
DCM_RE = re.compile(
    r"^(?P<ts>\d{14})_(?P<modality>PET|CT|SPECT|OI)_(?P<algo>[A-Za-z]+)_(?P<recon>\d+)"
    r"(?:_frame(?P<frame>MULTI|\d+))?"
    r"(?:_iter(?P<iter>\d+))?"
    r"(?:_(?P<extra>[^.]+))?"
    r"\.dcm$",
    re.IGNORECASE,
)

DEFAULT_SOURCE = r"S:\gnuclear"
DEFAULT_DEST = r"J:\gjesus3-data\staging\ni_gnuclear"
CHUNK = 8 * 1024 * 1024


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def _scandir_retry(path, attempts=5):
    """os.scandir with retries. `S:\\` is a busy foreign SMB share and throws
    transient `WinError 59 / 64 / 1236` under load; a bare walk loses whole
    subtrees silently (it cost us all of 2026 on the first run). Retry with
    backoff, and RAISE if it never succeeds — a scan that quietly returns fewer
    files than exist is the one failure mode we cannot allow, because it would
    read downstream as "that year has no data".
    """
    last = None
    for i in range(attempts):
        try:
            return list(os.scandir(path))
        except OSError as e:
            last = e
            time.sleep(0.5 * (2 ** i))
    raise IOError(f"could not list {path} after {attempts} attempts: {last}")


def scan(source, years, group):
    """Walk the source and return ({acq_key: [file records]}, skipped_names).

    Only descends `<source>/<year>/<group>/…`, which is what scopes this to the
    MFB group — every MFB folder sits under a `Jesus\\` level (other groups have
    their own siblings we must not touch).

    Sizes come from the directory entry (`DirEntry.stat()`), which on Windows is
    already populated by the directory listing itself. The first version called
    `os.path.getsize()` per file — a second SMB round-trip each — and the share
    started refusing them partway through. Reading the cached entry is both far
    faster and far more reliable.
    """
    acqs = {}
    skipped_names = []
    for year in years:
        base = os.path.join(source, year, group)
        if not os.path.isdir(base):
            log(f"  {year}/{group}: not present, skipping")
            continue
        n_before = sum(len(v) for v in acqs.values())
        stack = [base]
        while stack:
            d = stack.pop()
            for entry in _scandir_retry(d):
                try:
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(entry.path)
                        continue
                    if not entry.name.lower().endswith(".dcm"):
                        continue
                    m = DCM_RE.match(entry.name)
                    if not m:
                        skipped_names.append(entry.path)
                        continue
                    size = entry.stat(follow_symlinks=False).st_size
                except OSError as e:
                    log(f"  WARN unreadable entry, skipped: {entry.path} ({e})")
                    continue
                g = m.groupdict()
                key = f"{g['ts']}_{g['modality'].upper()}_{g['algo'].upper()}_{int(g['recon'])}"
                acqs.setdefault(key, []).append({
                    "src": entry.path,
                    "rel": os.path.relpath(entry.path, source).replace(os.sep, "/"),
                    "size": size,
                    "frame": (g["frame"] or ""),
                })
        log(f"  {year}/{group}: {sum(len(v) for v in acqs.values()) - n_before} matching DICOMs")
    if skipped_names:
        log(f"  ({len(skipped_names)} non-conforming .dcm ignored — analysis derivatives)")
    return acqs, skipped_names


def select(acqs):
    """Apply the frameMULTI rule and de-duplicate identical copies.

    Returns (wanted_files, stats). `acqs` maps acq_key -> file records.
    """
    wanted = []
    stats = {"multi_dropped": 0, "multi_kept": 0, "dup_copies_dropped": 0}
    for key, files in sorted(acqs.items()):
        has_per_frame = any(f["frame"] and f["frame"].upper() != "MULTI" for f in files)
        members = []
        for f in files:
            is_multi = f["frame"].upper() == "MULTI"
            if is_multi and has_per_frame:
                stats["multi_dropped"] += 1
                continue
            if is_multi:
                stats["multi_kept"] += 1
            members.append(f)

        # The same reconstruction is frequently copied into several analysis
        # folders (one scan appears in 48 directories in the worst case). Stage
        # ONE copy per (acq_key, basename, size); prefer the shallowest path,
        # which is consistently the original rather than a working copy.
        seen = {}
        for f in sorted(members, key=lambda x: (x["rel"].count("/"), x["rel"])):
            sig = (os.path.basename(f["rel"]).lower(), f["size"])
            if sig in seen:
                stats["dup_copies_dropped"] += 1
                continue
            seen[sig] = f
            f["acq_key"] = key
            wanted.append(f)
    return wanted, stats


def copy_one(src, dst, expect_size, attempts=4):
    """Copy one file, returning (sha256, bytes). Source is opened READ-ONLY.

    Writes to `<dst>.part` and renames only on a fully-verified read, so an
    interrupted transfer can never leave a truncated file that the resume logic
    would mistake for a finished one. Retries the whole file on the transient
    SMB errors this share throws under load.
    """
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".part"
    last = None
    for i in range(attempts):
        h = hashlib.sha256()
        n = 0
        try:
            with open(src, "rb") as fi, open(tmp, "wb") as fo:
                while True:
                    b = fi.read(CHUNK)
                    if not b:
                        break
                    fo.write(b)
                    h.update(b)
                    n += len(b)
            if n != expect_size:
                raise IOError(f"short read: got {n} of {expect_size} bytes")
            os.replace(tmp, dst)
            return h.hexdigest(), n
        except OSError as e:
            last = e
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            time.sleep(1.0 * (2 ** i))
    raise IOError(f"{last}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    ap.add_argument("--dest", default=DEFAULT_DEST)
    ap.add_argument("--group", default="Jesus",
                    help="the group level under each year (default: Jesus = MFB)")
    ap.add_argument("--years", default="2022,2023,2024,2025,2026")
    ap.add_argument("--plan", action="store_true", help="scan + report, move no bytes")
    ap.add_argument("--go", action="store_true", help="perform the pull")
    ap.add_argument("--verify", action="store_true",
                    help="re-hash every staged file against the manifest")
    ap.add_argument("--limit", type=int, default=0, help="stop after N files (testing)")
    args = ap.parse_args(argv)

    if not (args.plan or args.go or args.verify):
        ap.error("choose one of --plan / --go / --verify")

    years = [y.strip() for y in args.years.split(",") if y.strip()]
    log(f"source : {args.source}   (READ-ONLY)")
    log(f"dest   : {args.dest}")
    log(f"scope  : {'/'.join(years)} -> {args.group}/")

    manifest_path = os.path.join(args.dest, "_manifest.jsonl")

    if args.verify:
        if not os.path.exists(manifest_path):
            log(f"ERROR: no manifest at {manifest_path} — nothing to verify.")
            return 1
        ok = bad = missing = 0
        for line in open(manifest_path, encoding="utf-8"):
            rec = json.loads(line)
            dst = os.path.join(args.dest, rec["rel"].replace("/", os.sep))
            if not os.path.exists(dst):
                missing += 1
                log(f"  MISSING {rec['rel']}")
                continue
            h = hashlib.sha256()
            with open(dst, "rb") as f:
                for b in iter(lambda: f.read(CHUNK), b""):
                    h.update(b)
            if h.hexdigest() == rec["sha256"]:
                ok += 1
            else:
                bad += 1
                log(f"  CORRUPT {rec['rel']}")
        log(f"VERIFY: {ok} ok, {bad} corrupt, {missing} missing")
        return 0 if (bad == 0 and missing == 0) else 1

    log("scanning source ...")
    t0 = time.time()
    acqs, skipped = scan(args.source, years, args.group)
    wanted, stats = select(acqs)
    total_bytes = sum(f["size"] for f in wanted)
    log(f"scan done in {time.time()-t0:.0f}s")
    log("")
    log(f"  acquisitions (one per reconstruction) : {len(acqs)}")
    log(f"  files to stage                        : {len(wanted)}")
    log(f"  bytes to stage                        : {human(total_bytes)}")
    log(f"  frameMULTI bundles dropped (per-frame present) : {stats['multi_dropped']}")
    log(f"  frameMULTI bundles KEPT (only copy of that recon): {stats['multi_kept']}")
    log(f"  duplicate working copies skipped      : {stats['dup_copies_dropped']}")
    log(f"  non-conforming .dcm ignored           : {len(skipped)}")
    log("")

    if args.plan:
        os.makedirs(args.dest, exist_ok=True)
        plan_csv = os.path.join(args.dest, "_plan.csv")
        with open(plan_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["acq_key", "rel", "size_bytes"])
            for x in wanted:
                w.writerow([x["acq_key"], x["rel"], x["size"]])
        log(f"PLAN ONLY — no bytes moved. Wrote {plan_csv}")
        return 0

    # --go
    os.makedirs(args.dest, exist_ok=True)
    done = set()
    if os.path.exists(manifest_path):
        for line in open(manifest_path, encoding="utf-8"):
            try:
                done.add(json.loads(line)["rel"])
            except Exception:
                pass
        log(f"resuming: {len(done)} file(s) already recorded in the manifest")

    copied = skipped_existing = failed = 0
    bytes_copied = 0
    t0 = time.time()
    with open(manifest_path, "a", encoding="utf-8") as mf:
        for i, f in enumerate(wanted, 1):
            if args.limit and copied >= args.limit:
                log(f"--limit {args.limit} reached, stopping")
                break
            dst = os.path.join(args.dest, f["rel"].replace("/", os.sep))
            if f["rel"] in done and os.path.exists(dst) and os.path.getsize(dst) == f["size"]:
                skipped_existing += 1
                continue
            try:
                sha, n = copy_one(f["src"], dst, f["size"])
            except Exception as e:
                failed += 1
                log(f"  FAIL {f['rel']}: {e}")
                continue
            mf.write(json.dumps({
                "acq_key": f["acq_key"], "rel": f["rel"],
                "size": n, "sha256": sha,
            }) + "\n")
            mf.flush()
            copied += 1
            bytes_copied += n
            if copied % 25 == 0 or bytes_copied > 0 and copied == 1:
                el = time.time() - t0
                rate = bytes_copied / el if el else 0
                remain = total_bytes - bytes_copied
                eta = remain / rate if rate else 0
                log(f"  {i}/{len(wanted)}  {human(bytes_copied)} copied  "
                    f"{human(rate)}/s  ETA {eta/3600:.1f}h")

    log("")
    log(f"PULL DONE: {copied} copied ({human(bytes_copied)}), "
        f"{skipped_existing} already staged, {failed} failed")
    log(f"manifest: {manifest_path}")
    if failed:
        log("Re-run the same command to retry the failures (it resumes).")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
