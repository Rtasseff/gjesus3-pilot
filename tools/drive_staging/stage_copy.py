"""Stage a copy of a read-only source drive onto local disk, hashing in the same read pass.

Built for the one-copy historical microscopy drives (gjesus3, 2026-09): the source is read
exactly once per file, SHA-256 is computed from the bytes as they are read, and the copy is
later verified from the destination alone, so the source drive can go back to its owner as
soon as the copy pass ends.

    python stage_copy.py inventory SRC OUT   # metadata only: OUT/inventory.csv + OUT/summary.txt
    python stage_copy.py copy      SRC OUT   # SRC -> OUT/files, OUT/manifest.csv (resumable)
    python stage_copy.py verify    OUT       # re-hash OUT/files against OUT/manifest.csv

Rules it follows:
  * never writes to SRC (lock it read-only with lock_usb.ps1 when admin is available; without it,
    Windows still updates last-access times on read, so the originals are recorded first);
  * bounded read retries -- 3 attempts per file with a short pause, so transient stalls
    (antivirus scanning, USB bus contention) recover instead of losing the file, while a
    genuinely bad sector still gives up quickly; the file is then logged to errors.csv and
    skipped. CONSECUTIVE_FAIL_LIMIT failures in a row trip a circuit breaker and stop the run,
    so a dying drive is not hammered; re-running `copy` retries only what is not in the manifest;
  * modification times are restored on files and folders; creation times cannot be set on
    the copy, so both times are recorded in the manifest;
  * files are written as <name>.part and renamed only after a complete read.
"""
import csv
import ctypes
import datetime as dt
import hashlib
import json
import os
import queue
import shutil
import socket
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from collections import Counter, defaultdict

VERSION = "1.5 (2026-09-30)"
CHUNK = 1024 * 1024            # 1 MB: smaller reads survive I/O contention better
READ_ATTEMPTS = 3              # total tries per file before it is logged and skipped
RETRY_PAUSE = 2.0              # seconds, multiplied by the attempt number
CONSECUTIVE_FAIL_LIMIT = 25    # circuit breaker: stop rather than hammer a failing drive
COPY_WORKERS = 16              # parallel workers for small files (SMB latency hiding)
VERIFY_WORKERS = 16            # verify reads only the staged copy, so it parallelises freely
PARALLEL_MAX_BYTES = 16 * 1024 * 1024   # bigger files are copied one at a time
SKIP_AT_ROOT = {"System Volume Information", "$RECYCLE.BIN", "$Recycle.Bin", "found.000"}
MANIFEST_COLS = ["relpath", "size", "mtime", "birthtime", "atime", "mtime_ns", "sha256"]


# ---------- helpers ----------

def longpath(p):
    p = os.path.abspath(p)
    return p if p.startswith("\\\\?\\") else "\\\\?\\" + p


def iso(ns):
    try:
        return dt.datetime.fromtimestamp(ns / 1e9).isoformat(timespec="seconds") if ns else ""
    except (OSError, OverflowError, ValueError):
        return f"raw_ns:{ns}"


def birth_ns(st):
    return getattr(st, "st_birthtime_ns", None) or st.st_ctime_ns


def gb(n):
    return f"{n / 1e9:,.1f} GB"


def walk(src):
    """Yield ('D'|'F', relpath, stat) for everything under src, depth-first; errors -> ('E', rel, msg)."""
    stack = [""]
    while stack:
        rel = stack.pop()
        try:
            with os.scandir(longpath(os.path.join(src, rel))) as it:
                entries = sorted(it, key=lambda e: e.name.lower())
        except OSError as e:
            yield "E", rel, str(e)
            continue
        for e in entries:
            erel = os.path.join(rel, e.name) if rel else e.name
            if not rel and e.name in SKIP_AT_ROOT:
                continue
            try:
                st = e.stat(follow_symlinks=False)
                if e.is_dir(follow_symlinks=False):
                    yield "D", erel, st
                    stack.append(erel)
                elif e.is_file(follow_symlinks=False):
                    yield "F", erel, st
            except OSError as ex:
                yield "E", erel, str(ex)


def volume_info(root):
    label, fs = ctypes.create_unicode_buffer(261), ctypes.create_unicode_buffer(261)
    serial = ctypes.c_uint32()
    drive = os.path.splitdrive(os.path.abspath(root))[0] + "\\"
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        drive, label, 261, ctypes.byref(serial), None, None, fs, 261)
    return {"drive": drive, "label": label.value, "serial": f"{serial.value:08X}",
            "filesystem": fs.value} if ok else {"drive": drive}


def keep_awake():
    """Stop Windows sleeping while this process runs (ES_CONTINUOUS | ES_SYSTEM_REQUIRED); no admin needed."""
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)


class Log:
    """Logging must never be able to kill a copy.

    Filenames on this data include macOS artefacts with private-use characters (Icon\\r ->
    U+F00D). Printing one of those to a cp1252 console raises UnicodeEncodeError, and if that
    happens inside an except: block it escapes the worker and takes the whole run down. It did,
    once, at 88% of a 1.6 TB copy. So both sinks are encode-proof and any residual failure is
    swallowed.
    """

    def __init__(self, path):
        self.f = open(path, "a", encoding="utf-8", errors="replace")
        self.lock = threading.Lock()

    def __call__(self, msg):
        line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
        with self.lock:
            try:
                print(line, flush=True)
            except Exception:
                try:
                    enc = sys.stdout.encoding or "ascii"
                    print(line.encode(enc, "replace").decode(enc, "replace"), flush=True)
                except Exception:
                    pass
            try:
                self.f.write(line + "\n")
                self.f.flush()
            except Exception:
                pass


# ---------- inventory ----------

def inventory(src, out):
    os.makedirs(out, exist_ok=True)
    files = dirs = errs = 0
    total = 0
    top = defaultdict(lambda: [0, 0])
    ext = defaultdict(lambda: [0, 0])
    years = Counter()
    buckets = Counter()
    edges = [(1e6, "<1 MB"), (1e8, "1-100 MB"), (1e9, "100 MB-1 GB"), (1e10, "1-10 GB"), (float("inf"), ">10 GB")]
    with open(os.path.join(out, "inventory.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["type", "relpath", "size", "mtime", "birthtime", "atime"])
        for kind, rel, st in walk(src):
            if kind == "E":
                errs += 1
                w.writerow(["E", rel, "", st, "", ""])
                continue
            if kind == "D":
                dirs += 1
                w.writerow(["D", rel, "", iso(st.st_mtime_ns), iso(birth_ns(st)), iso(st.st_atime_ns)])
                continue
            files += 1
            total += st.st_size
            w.writerow(["F", rel, st.st_size, iso(st.st_mtime_ns), iso(birth_ns(st)), iso(st.st_atime_ns)])
            t = rel.split(os.sep)[0] if os.sep in rel else "(root files)"
            top[t][0] += 1; top[t][1] += st.st_size
            x = os.path.splitext(rel)[1].lower() or "(none)"
            ext[x][0] += 1; ext[x][1] += st.st_size
            years[iso(st.st_mtime_ns)[:4]] += 1
            buckets[next(lbl for lim, lbl in edges if st.st_size < lim)] += 1

    vi = volume_info(src)
    free = shutil.disk_usage(out).free
    lines = [
        f"Source: {src}  {vi}",
        f"Scanned: {dt.datetime.now():%Y-%m-%d %H:%M}   stage_copy {VERSION}",
        f"Files: {files:,}   Folders: {dirs:,}   Unreadable entries: {errs:,}",
        f"Total: {gb(total)}   Free at destination: {gb(free)}   Fits: {'yes' if total * 1.02 < free else 'NO'}",
        f"Copy time estimate: {total / 150e6 / 3600:.1f} h at 150 MB/s, {total / 100e6 / 3600:.1f} h at 100 MB/s",
        "", "Top-level folders (files, size):",
        *[f"  {gb(s):>12}  {n:>9,}  {t}" for t, (n, s) in sorted(top.items(), key=lambda kv: -kv[1][1])],
        "", "Extensions (files, size) -- top 25 by size:",
        *[f"  {gb(s):>12}  {n:>9,}  {x}" for x, (n, s) in sorted(ext.items(), key=lambda kv: -kv[1][1])[:25]],
        "", "File sizes:", *[f"  {buckets[lbl]:>9,}  {lbl}" for _, lbl in edges],
        "", "Files by modification year:", *[f"  {y}  {n:>9,}" for y, n in sorted(years.items())],
    ]
    text = "\n".join(lines)
    with open(os.path.join(out, "summary.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)


# ---------- copy ----------

def _put(q, item, stop):
    while not stop.is_set():
        try:
            q.put(item, timeout=0.5)
            return True
        except queue.Full:
            pass
    return False


def _reader(path, q, h, stop):
    try:
        with open(path, "rb", buffering=0) as fi:
            while not stop.is_set():
                b = fi.read(CHUNK)
                if not b:
                    break
                h.update(b)
                if not _put(q, b, stop):
                    return
        _put(q, None, stop)
    except BaseException as e:  # hand the error to the writer
        _put(q, e, stop)


def copy_one(src_path, dst_path):
    """Read once, hash while reading, write in parallel. Returns (sha256, bytes)."""
    tmp = dst_path + ".part"
    h = hashlib.sha256()
    q = queue.Queue(maxsize=4)
    stop = threading.Event()
    t = threading.Thread(target=_reader, args=(src_path, q, h, stop), daemon=True)
    n = 0
    try:
        with open(tmp, "wb") as fo:
            t.start()
            while True:
                b = q.get()
                if b is None:
                    break
                if isinstance(b, BaseException):
                    raise b
                fo.write(b)
                n += len(b)
        t.join()
        os.replace(tmp, dst_path)
    except BaseException:
        stop.set()  # lets the reader close the source file and exit
        t.join(timeout=5) if t.is_alive() else None
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return h.hexdigest(), n


def copy_one_retrying(src_path, dst_path, log, rel):
    """copy_one with bounded retries for transient failures.

    Antivirus scanning and USB bus stalls surface as OSError or, under memory pressure,
    MemoryError; both are worth retrying. A real bad sector fails all attempts quickly.
    Re-raises the last error once the attempts are spent, so the caller logs and skips.
    """
    for attempt in range(1, READ_ATTEMPTS + 1):
        try:
            return copy_one(src_path, dst_path)
        except (OSError, MemoryError) as e:
            if attempt == READ_ATTEMPTS:
                raise
            try:
                log(f"  retry {attempt}/{READ_ATTEMPTS - 1} on {rel} after {type(e).__name__}: {e}")
            except Exception:
                pass
            time.sleep(RETRY_PAUSE * attempt)


def load_manifest(path):
    done = {}
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                done[r["relpath"]] = r
    return done


def copy(src, out):
    os.makedirs(os.path.join(out, "files"), exist_ok=True)
    log = Log(os.path.join(out, "copy.log"))
    mpath = os.path.join(out, "manifest.csv")
    done = load_manifest(mpath)
    new_manifest = not os.path.exists(mpath)
    vi = volume_info(src)
    log(f"stage_copy {VERSION} on {socket.gethostname()}  src={src} {vi}  out={out}  already in manifest: {len(done):,}")

    items = list(walk(src))
    files = [(r, st) for k, r, st in items if k == "F"]
    dirs = [(r, st) for k, r, st in items if k == "D"]
    for k, r, msg in items:
        if k == "E":
            log(f"UNREADABLE ENTRY {r}: {msg}")
    total = sum(st.st_size for _, st in files)
    todo = [(r, st) for r, st in files
            if not (r in done and int(done[r]["size"]) == st.st_size
                    and int(done[r]["mtime_ns"]) == st.st_mtime_ns
                    and os.path.exists(longpath(os.path.join(out, "files", r))))]
    todo_bytes = sum(st.st_size for _, st in todo)
    free = shutil.disk_usage(out).free
    log(f"{len(files):,} files, {gb(total)} total; to copy now: {len(todo):,} files, {gb(todo_bytes)}; free {gb(free)}")
    if todo_bytes * 1.02 > free:
        log("ABORT: not enough free space at destination")
        sys.exit(2)

    with open(os.path.join(out, "run_info.json"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"started": dt.datetime.now().isoformat(timespec="seconds"), "version": VERSION,
                            "host": socket.gethostname(), "source": src, "volume": vi,
                            "files": len(files), "bytes": total}) + "\n")

    for r, _ in dirs:
        os.makedirs(longpath(os.path.join(out, "files", r)), exist_ok=True)

    mf = open(mpath, "a", newline="", encoding="utf-8")
    mw = csv.writer(mf)
    if new_manifest:
        mw.writerow(MANIFEST_COLS)
    ef = open(os.path.join(out, "errors.csv"), "a", newline="", encoding="utf-8")
    ew = csv.writer(ef)

    # Big files are bandwidth-bound and go one at a time, so the drive reads them
    # sequentially. Small files are dominated by per-file SMB round trips, so they are
    # copied by a pool: the latency overlaps and the drive still reads in tree order.
    big = [(r, st) for r, st in todo if st.st_size >= PARALLEL_MAX_BYTES]
    smalls = [(r, st) for r, st in todo if st.st_size < PARALLEL_MAX_BYTES]
    log(f"plan: {len(big):,} files >= {PARALLEL_MAX_BYTES // 1024 // 1024} MB sequentially "
        f"({gb(sum(st.st_size for _, st in big))}), then {len(smalls):,} smaller files "
        f"across {COPY_WORKERS} workers ({gb(sum(st.st_size for _, st in smalls))})")

    t0 = last = time.time()
    state = {"copied": 0, "nbytes": 0, "nerr": 0, "run_of_errors": 0, "aborted": False}
    slock = threading.Lock()
    wlock = threading.Lock()

    def progress(force=False):
        nonlocal last
        now = time.time()
        if force or now - last >= 60:
            with slock:
                nb, cp, ne = state["nbytes"], state["copied"], state["nerr"]
            rate = nb / (now - t0) if now > t0 else 0
            eta = (todo_bytes - nb) / rate / 3600 if rate else 0
            log(f"{gb(nb)} / {gb(todo_bytes)}  {cp:,} files  {rate / 1e6:.0f} MB/s  "
                f"ETA {eta:.1f} h  errors {ne}")
            last = now

    def do_one(item):
        r, st = item
        if state["aborted"]:
            return
        sp = longpath(os.path.join(src, r))
        dp = longpath(os.path.join(out, "files", r))
        try:
            sha, n = copy_one_retrying(sp, dp, log, r)
            if n != st.st_size:
                raise OSError(f"size changed during read: expected {st.st_size}, read {n}")
            os.utime(dp, ns=(st.st_atime_ns, st.st_mtime_ns))
            with wlock:
                mw.writerow([r, st.st_size, iso(st.st_mtime_ns), iso(birth_ns(st)),
                             iso(st.st_atime_ns), st.st_mtime_ns, sha])
                mf.flush()
            with slock:
                state["copied"] += 1
                state["nbytes"] += n
                state["run_of_errors"] = 0
        except Exception as e:
            # Anything at all: a mangled filename, an encoding fault, an SMB refusal. One file
            # is logged and skipped. KeyboardInterrupt is a BaseException and still propagates.
            with wlock:
                try:
                    ew.writerow([dt.datetime.now().isoformat(timespec="seconds"), r,
                                 st.st_size, f"{type(e).__name__}: {e}"])
                    ef.flush()
                except Exception:
                    pass
            log(f"ERROR {r}: {type(e).__name__}: {e}")
            with slock:
                state["nerr"] += 1
                state["run_of_errors"] += 1
                if state["run_of_errors"] >= CONSECUTIVE_FAIL_LIMIT and not state["aborted"]:
                    state["aborted"] = True
                    log(f"CIRCUIT BREAKER: {state['run_of_errors']} files failed in a row after "
                        f"{READ_ATTEMPTS} attempts each. Stopping so the drive is not hammered. "
                        f"Check the source drive before re-running; progress is in the manifest.")

    try:
        for item in big:
            if state["aborted"]:
                break
            do_one(item)
            progress()
        if not state["aborted"] and smalls:
            progress(force=True)
            with ThreadPoolExecutor(max_workers=COPY_WORKERS) as ex:
                for _ in ex.map(do_one, smalls):
                    progress()
    except KeyboardInterrupt:
        log("Interrupted -- re-run the same command to resume")
        raise

    copied, nbytes, nerr = state["copied"], state["nbytes"], state["nerr"]
    aborted = state["aborted"]

    # folder times last, deepest first, so writing files does not disturb them
    for r, st in sorted(dirs, key=lambda d: -d[0].count(os.sep)):
        try:
            os.utime(longpath(os.path.join(out, "files", r)), ns=(st.st_atime_ns, st.st_mtime_ns))
        except OSError as e:
            log(f"could not set folder time {r}: {e}")
    mf.close()
    ef.close()
    el = time.time() - t0
    log(f"{'ABORTED BY CIRCUIT BREAKER' if aborted else 'DONE'}: copied {copied:,} files, "
        f"{gb(nbytes)} in {el / 3600:.2f} h "
        f"({nbytes / max(el, 1) / 1e6:.0f} MB/s); errors {nerr}"
        + ("  -- see errors.csv, re-run copy to retry them" if nerr else ""))
    if aborted:
        sys.exit(3)


# ---------- verify ----------

def verify(out):
    log = Log(os.path.join(out, "verify.log"))
    rows = load_manifest(os.path.join(out, "manifest.csv"))
    root = os.path.join(out, "files")
    total = sum(int(r["size"]) for r in rows.values())
    log(f"verify {VERSION}: {len(rows):,} files, {gb(total)}")
    bad = []
    t0 = last = time.time()
    counters = {"nbytes": 0, "done": 0}
    clock = threading.Lock()

    def check(item):
        rel, r = item
        p = longpath(os.path.join(root, rel))
        got = 0
        try:
            h = hashlib.sha256()
            with open(p, "rb", buffering=0) as f:
                while b := f.read(CHUNK):
                    h.update(b)
                    got += len(b)
            problem = None if h.hexdigest() == r["sha256"] else "CHECKSUM MISMATCH"
        except Exception as e:
            problem = f"UNREADABLE: {type(e).__name__}: {e}"
        with clock:
            counters["nbytes"] += got
            counters["done"] += 1
            if problem:
                bad.append((rel, problem))
        return None

    with ThreadPoolExecutor(max_workers=VERIFY_WORKERS) as ex:
        for _ in ex.map(check, list(rows.items())):
            now = time.time()
            if now - last >= 60:
                last = now
                with clock:
                    nb, dn = counters["nbytes"], counters["done"]
                log(f"{gb(nb)} / {gb(total)}  {dn:,} files  {nb / (now - t0) / 1e6:.0f} MB/s  "
                    f"problems {len(bad)}")
    nbytes = counters["nbytes"]
    on_disk = {k_rel for k, k_rel, _ in walk(root) if k == "F"}
    extra = sorted(on_disk - set(rows))
    with open(os.path.join(out, "verify_problems.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["relpath", "problem"])
        w.writerows(bad)
        w.writerows((x, "NOT IN MANIFEST") for x in extra)
    status = "PASS" if not bad and not extra else "FAIL"
    log(f"VERIFY {status}: {len(rows) - len(bad):,} ok, {len(bad):,} bad, {len(extra):,} not in manifest "
        f"({(time.time() - t0) / 3600:.2f} h)")
    return status == "PASS"


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in {"inventory", "copy", "verify"}:
        sys.exit(__doc__)
    mode = sys.argv[1]
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass
    keep_awake()
    if mode != "verify" and len(sys.argv) > 2 and sys.argv[2].rstrip("\\/").endswith(":"):
        sys.argv[2] = sys.argv[2].rstrip("\\/") + "\\"  # "R:" alone means R's current dir, not its root
    if mode == "verify":
        sys.exit(0 if verify(sys.argv[2]) else 1)
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    {"inventory": inventory, "copy": copy}[mode](sys.argv[2], sys.argv[3])
