#!/usr/bin/env python3
"""test_stage_copy.py -- tools/drive_staging/stage_copy.py (1.5), end to end, in temp dirs only.

stage_copy copies an external drive that is the ONLY copy of its data onto local disk: each file is
read once, its SHA-256 is computed from the bytes as they are read, a manifest makes the run
resumable, and `verify` re-hashes the copy from the destination alone. The tool accepts any
directory as its source, so a temp directory stands in for the drive. Everything below goes through
the script's own entry points (copy / verify / inventory, then the command line); nothing outside
the temp dir is touched and no real drive, NAS or network is needed.
Windows only: the tool uses ctypes.windll (volume info, keep-awake) and \\\\?\\ paths.

  0. The write guard works. It is a Python audit hook that records every call able to change a
     tree, and every file opened for reading, so the "source untouched" results below are not a
     silent no-op.
  1. A drive with: a 16.5 MB file (the copy takes it on its own), a 5 MB file, an exactly-one-chunk
     file, empty and 1-byte files, 60 small files, an empty folder, a name holding U+F00D (macOS
     stores "Icon\\r" so), AppleDouble `._` files, and the root-level system folders that must be
     skipped (the same names deeper in the tree must not be).
  2. inventory lists exactly those files and folders.
  3. copy: the manifest holds exactly the expected files, each with the right size, mtime and
     SHA-256 (computed here, independently); every staged file is byte-identical; times are
     restored on files and folders; no .part is left; every source file is opened for reading
     exactly once and never for writing; the source tree is unchanged byte for byte; the big file
     is copied first, alone, on the main thread, and the rest on a pool of threads.
  4. verify passes, on a pool of threads, and writes nothing under files\\. A second copy reads
     nothing and copies nothing (resumable); after a source file changes and another appears, only
     those two are copied.
  5. verify fails, naming the file, for a corrupted file, a missing file and a stray file.
  6. Failing files. One fails mid-read (a byte-range lock: PermissionError on the second chunk) and
     its name holds U+F00D, with a cp1252 console that cannot print that character (the failure
     that killed a 1.6 TB copy at 88%). One raises something that is not an I/O error. One fails
     once and then recovers. The run still finishes; the lasting failure is tried READ_ATTEMPTS
     times with 2 s then 4 s pauses, the unexpected error once; both go to errors.csv and
     copy.log, stay out of the manifest and leave no .part; the flaky file is copied after one
     retry; the next run copies just the two that failed.
  7. A file whose size changes between the directory scan and the read is not manifested.
  8. The circuit breaker: failures with a success between them never trip it; CONSECUTIVE_FAIL_LIMIT
     in a row stop the run with exit code 3, later files are never attempted, and the next run
     finishes the job.
  9. The command line: inventory / copy / verify exit codes, stdout forced to UTF-8, usage errors.

Not covered (needs a real drive or machine, or is a known limit): the `R:` -> `R:\\` drive-root
argument fix, volume label/serial of a USB drive, antivirus or USB stalls, a real bad sector,
lock_usb.ps1, SMB/NAS destinations, throughput, Ctrl-C, and a source filename holding a lone UTF-16
surrogate (a known limit, in the README).

Run:  python tools/drive_staging/test_stage_copy.py      (exit 0 = pass)
"""
import collections
import contextlib
import csv
import gc
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "stage_copy.py")
if HERE not in sys.path:
    sys.path.insert(0, HERE)

FAILS = []


def say(msg):
    """ASCII only: under the suite runner stdout is a cp1252 pipe, and these names hold U+F00D."""
    print(str(msg).encode("ascii", "backslashreplace").decode("ascii"), flush=True)


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        say(f"  FAIL: {msg}")
    else:
        say(f"  ok:   {msg}")


if os.name != "nt":
    say("SKIP: stage_copy.py is a Windows tool (ctypes.windll, \\\\?\\ paths); nothing to test here")
    sys.exit(0)

import msvcrt  # noqa: E402  (Windows only)

import stage_copy as sc  # noqa: E402

F00D = "\uf00d"                 # macOS "Icon\r" arrives on an SMB/NTFS drive as "Icon" + U+F00D
KB, MB = 1024, 1024 * 1024
OLD_NS = 1_550_000_000 * 10**9  # 2019-02-12: a restored time is unmistakably not "now"
BIG = os.path.join("big", "large.bin")


# ---------- the write guard ----------

class Guard:
    """An audit hook. While roots are armed it records every call that could change a tree under
    them (`hits`) and every file under them opened for reading (`reads`). Audit hooks cannot be
    removed, so it is installed once and does nothing while no root is armed."""

    MUTATORS = {"os.remove", "os.rename", "os.rmdir", "os.mkdir", "os.chmod", "os.utime", "os.truncate",
                "os.link", "os.symlink", "shutil.rmtree", "shutil.move"}
    WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND

    def __init__(self):
        self.roots, self.hits, self.reads, self.threads = [], [], collections.Counter(), {}
        sys.addaudithook(self._hook)

    @staticmethod
    def norm(p):
        if isinstance(p, bytes):
            p = os.fsdecode(p)
        if not isinstance(p, str):
            return None
        if p.startswith("\\\\?\\"):
            p = p[4:]
        return os.path.normcase(os.path.abspath(p))

    def _under(self, p):
        p = self.norm(p)
        return p is not None and any(p == r or p.startswith(r + os.sep) for r in self.roots)

    def _hook(self, event, args):
        if not self.roots:
            return
        try:
            if event == "open":
                path, mode, flags = args
                if self._under(path):
                    if any(c in (mode or "") for c in "wax+") or (isinstance(flags, int) and flags & self.WRITE_FLAGS):
                        self.hits.append((event, path))
                    else:
                        self.reads[self.norm(path)] += 1
                        self.threads[self.norm(path)] = threading.current_thread().name
            elif event in self.MUTATORS:
                for a in args:
                    if self._under(a):
                        self.hits.append((event, a))
                        break
        except Exception:
            pass  # a guard must never be the thing that breaks the tool under test

    @contextlib.contextmanager
    def watching(self, *roots):
        self.roots = [self.norm(r) for r in roots]
        self.hits, self.reads, self.threads = [], collections.Counter(), {}
        try:
            yield self
        finally:
            self.roots = []


GUARD = Guard()


# ---------- helpers ----------

def tmpdir():
    try:
        return tempfile.TemporaryDirectory(prefix="stage_copy_test_", ignore_cleanup_errors=True)
    except TypeError:  # Python < 3.10
        return tempfile.TemporaryDirectory(prefix="stage_copy_test_")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    with open(path, "rb") as f:
        return sha(f.read())


def blob(seed, n):
    """n deterministic pseudo-random bytes."""
    return hashlib.shake_256(f"stage_copy-test-{seed}".encode()).digest(n)


def stamp(root):
    """Give every file and folder under root a distinct old modification time (folders last, deepest
    first, as the tool restores them), so 'restored' cannot be mistaken for 'just written'."""
    files, dirs = [], []
    for base, dnames, fnames in os.walk(root):
        dirs += [os.path.join(base, d) for d in dnames]
        files += [os.path.join(base, n) for n in fnames]
    for i, p in enumerate(sorted(files)):
        t = OLD_NS + i * 3601 * 10**9 + 123_456_700
        os.utime(p, ns=(t, t))
    for i, p in enumerate(sorted(dirs, key=lambda q: (-q.count(os.sep), q))):
        t = OLD_NS + (i + 1) * 7919 * 10**9 + 76_543_200
        os.utime(p, ns=(t, t))
    os.utime(root, ns=(OLD_NS, OLD_NS))


def make_tree(root, files, empty_dirs=()):
    for rel, data in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
    for d in empty_dirs:
        os.makedirs(os.path.join(root, d), exist_ok=True)
    stamp(root)


def dirs_of(files, empty_dirs=()):
    """Every folder a set of relative file paths (plus empty folders) implies."""
    out = set()
    for d in set(empty_dirs) | {os.path.dirname(r) for r in files}:
        while d:
            out.add(d)
            d = os.path.dirname(d)
    return out


def snapshot(root):
    """Everything under root: folders by mtime, files by size, mtime and content hash."""
    snap = {".": ("D", os.stat(root).st_mtime_ns)}
    for base, dnames, fnames in os.walk(root):
        for d in dnames:
            p = os.path.join(base, d)
            snap[os.path.relpath(p, root)] = ("D", os.stat(p).st_mtime_ns)
        for n in fnames:
            p = os.path.join(base, n)
            st = os.stat(p)
            snap[os.path.relpath(p, root)] = ("F", st.st_size, st.st_mtime_ns, sha_file(p))
    return snap


def untouched(root, before, label):
    after = snapshot(root)
    diff = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    check(not diff, f"{label}: the source tree is unchanged (names, sizes, times, bytes)"
                    + (f" -- differs: {[ascii(k) for k in diff[:4]]}" if diff else ""))


def quiet(label):
    check(not GUARD.hits, f"{label}: nothing written, renamed, deleted or re-timed under the watched tree"
                          + (f" -- saw {GUARD.hits[:3]}" if GUARD.hits else ""))


def manifest_rows(out):
    p = os.path.join(out, "manifest.csv")
    if not os.path.exists(p):
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def problems(out):
    with open(os.path.join(out, "verify_problems.csv"), newline="", encoding="utf-8") as f:
        return [tuple(r) for r in list(csv.reader(f))[1:]]


def errors_rows(out):
    with open(os.path.join(out, "errors.csv"), newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def staged(out):
    """(files, folders) under OUT/files, as relative paths."""
    root = os.path.join(out, "files")
    fs, ds = set(), set()
    for base, dnames, fnames in os.walk(root):
        ds |= {os.path.relpath(os.path.join(base, d), root) for d in dnames}
        fs |= {os.path.relpath(os.path.join(base, n), root) for n in fnames}
    return fs, ds


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class Result:
    def __init__(self, result, code, text, exc):
        self.result, self.code, self.text, self.exc = result, code, text, exc


def call(fn, *args, watch=(), console=None):
    """Call a stage_copy entry point as the command line would, but with a console that, like a
    cp1252 Windows console, raises on U+F00D. SystemExit becomes `code`; any other exception that
    escapes is returned in `exc` (it must not). Every call under `watch` is recorded by the guard."""
    console = console or io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict", write_through=True)
    result, code, exc = None, 0, None
    with GUARD.watching(*watch), contextlib.redirect_stdout(console):
        try:
            result = fn(*args)
        except SystemExit as e:
            code = e.code
        except Exception as e:  # noqa: BLE001
            exc = f"{type(e).__name__}: {e}"
    console.flush()
    buf = getattr(console, "buffer", None)
    text = buf.getvalue().decode("cp1252", "replace") if buf is not None else console.getvalue()
    return Result(result, code, text, exc)


@contextlib.contextmanager
def patched(**kw):
    old = {k: getattr(sc, k) for k in kw}
    try:
        for k, v in kw.items():
            setattr(sc, k, v)
        yield
    finally:
        for k, v in old.items():
            setattr(sc, k, v)


class FakeTime:
    """Stands in for the `time` module inside stage_copy: records sleeps instead of sleeping, so the
    retry pauses are asserted exactly and cost nothing. Everything else is the real module."""

    def __init__(self):
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)

    def __getattr__(self, name):
        return getattr(time, name)


class Spy:
    """Stands in for stage_copy.copy_one: records (relpath, thread) for every attempt, then either
    raises what `fail(relpath)` returns (an exception, or None for no failure) or delegates to the
    real one. `before(relpath)` runs first, for tests that change the source mid-copy."""

    def __init__(self, src, fail=None, before=None):
        self.src, self.fail, self.before, self.real, self.calls = src, fail, before, sc.copy_one, []

    def __call__(self, src_path, dst_path):
        p = src_path[4:] if src_path.startswith("\\\\?\\") else src_path
        rel = os.path.relpath(p, self.src)
        self.calls.append((rel, threading.current_thread().name))
        if self.before:
            self.before(rel)
        err = self.fail(rel) if self.fail else None
        if err is not None:
            raise err
        return self.real(src_path, dst_path)

    def attempts(self):
        return collections.Counter(rel for rel, _ in self.calls)


@contextlib.contextmanager
def byte_range_lock(path, offset, length):
    """Hold a mandatory byte-range lock: another handle reads the bytes before `offset` but gets
    PermissionError on the locked range -- a deterministic stand-in for a bad sector mid-file."""
    f = open(path, "rb")
    try:
        f.seek(offset)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, length)
        try:
            yield
        finally:
            f.seek(offset)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, length)
    finally:
        f.close()


# ---------- 0. the guard ----------

def check_guard():
    print("0. write guard")
    with tmpdir() as td:
        p = os.path.join(td, "f.txt")
        with open(p, "wb") as f:
            f.write(b"x")
        with GUARD.watching(td):
            with open(p, "rb") as f:
                f.read()
            reads, quiet_after_read = dict(GUARD.reads), not GUARD.hits
            os.utime(p, (1, 1))
            with open(p, "ab"):
                pass
            os.rename(p, p + "2")
            os.mkdir(os.path.join(td, "d"))
            os.remove(p + "2")
            events = {e for e, _ in GUARD.hits}
        check(quiet_after_read and list(reads.values()) == [1], "a plain read is counted, and is not a write")
        check(events == {"open", "os.utime", "os.rename", "os.mkdir", "os.remove"},
              f"every kind of change is seen: {sorted(events)}")
        check(not GUARD.roots, "the guard disarms itself")


# ---------- 1-5. the main drive ----------

def build_drive():
    files = {
        BIG: blob("big", sc.PARALLEL_MAX_BYTES + sc.CHUNK // 2 + 7),
        "mid.bin": blob("mid", 5 * MB + 3),
        "one_chunk.bin": blob("one", sc.CHUNK),
        "empty.dat": b"",
        "one_byte.dat": b"x",
        os.path.join("mac", "Icon" + F00D): b"",
        os.path.join("mac", "._Icon" + F00D): b"\x00\x05\x16\x07" + blob("ad1", 4092),
        os.path.join("mac", "._notes.txt"): b"\x00\x05\x16\x07" + blob("ad2", 252),
        os.path.join("mac", "notes.txt"): blob("notes", 700),
        os.path.join("run00", "$RECYCLE.BIN", "nested_kept.txt"): b"skipped only at the root of the drive",
    }
    for d in range(5):
        for i in range(12):
            n = d * 12 + i
            files[os.path.join(f"run{d:02d}", "sub", f"f{i:02d}.dat")] = blob(f"small{n}", (n * 997) % (200 * KB))
    skipped = {
        os.path.join("$RECYCLE.BIN", "S-1-5-21", "desktop.ini"): b"junk",
        os.path.join("System Volume Information", "tracking.log"): b"junk",
        os.path.join("found.000", "file0000.chk"): b"junk",
    }
    return files, skipped, [os.path.join("empty_dir", "inner")]


def check_main_drive(td):
    files, skipped, empty_dirs = build_drive()
    src, out = os.path.join(td, "drive"), os.path.join(td, "staged")
    make_tree(src, {**files, **skipped}, empty_dirs)
    all_dirs = dirs_of(files, empty_dirs)
    nsmall = len(files) - 1
    before = snapshot(src)

    print("2. inventory")
    inv = os.path.join(td, "inventory")
    r = call(sc.inventory, src, inv, watch=(src,), console=io.StringIO())
    check(r.exc is None, f"inventory ran ({r.exc})")
    quiet("inventory")
    with open(os.path.join(inv, "inventory.csv"), newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))[1:]
    listed_files = {r_[1] for r_ in rows if r_[0] == "F"}
    listed_dirs = {r_[1] for r_ in rows if r_[0] == "D"}
    check(listed_files == set(files), f"inventory lists exactly the {len(files)} files (the 3 root system folders are skipped)")
    check(listed_dirs == all_dirs, f"inventory lists exactly the {len(all_dirs)} folders, empty ones included")
    check(f"Files: {len(files):,}" in read_text(os.path.join(inv, "summary.txt")), "summary.txt carries the file count")
    untouched(src, before, "inventory")

    print("3. copy")
    spy = Spy(src)
    with patched(copy_one=spy):
        r = call(sc.copy, src, out, watch=(src,))
    check(r.exc is None and r.code == 0, f"copy finished normally ({r.exc or r.code})")
    check(re.search(r"DONE: copied %d files.*errors 0" % len(files), r.text) is not None, "the last console line says DONE, errors 0")
    quiet("copy")
    check(set(GUARD.reads) == {Guard.norm(os.path.join(src, rel)) for rel in files}
          and set(GUARD.reads.values()) == {1},
          "every source file was opened for reading exactly once, and nothing else was")
    untouched(src, before, "copy")

    rows = manifest_rows(out)
    by_rel = {x["relpath"]: x for x in rows}
    check(len(rows) == len(files) and set(by_rel) == set(files),
          f"the manifest holds exactly the {len(files)} expected files, once each")
    wrong = [rel for rel, data in files.items()
             if by_rel.get(rel, {}).get("sha256") != sha(data)
             or by_rel.get(rel, {}).get("size") != str(len(data))
             or by_rel.get(rel, {}).get("mtime_ns") != str(os.stat(os.path.join(src, rel)).st_mtime_ns)]
    check(not wrong, f"each manifest row has the right size, mtime_ns and SHA-256 (independently computed)"
                     + (f" -- wrong: {[ascii(w) for w in wrong[:3]]}" if wrong else ""))
    check(all(x["birthtime"] and x["mtime"] == sc.iso(int(x["mtime_ns"])) for x in rows), "mtime and birthtime are recorded in the manifest")
    sfiles, sdirs = staged(out)
    check(sfiles == set(files), "the staged tree holds exactly those files: no .part, nothing from the skipped root folders")
    check(sdirs == all_dirs, "the staged tree holds exactly the source's folders, the empty ones too")
    differ = [rel for rel, data in files.items() if sha_file(os.path.join(out, "files", rel)) != sha(data)]
    check(not differ, "every staged file is byte-identical to its source")
    off = [rel for rel in files
           if abs(os.stat(os.path.join(out, "files", rel)).st_mtime_ns - os.stat(os.path.join(src, rel)).st_mtime_ns) > 2 * 10**9]
    off += [d for d in all_dirs
            if abs(os.stat(os.path.join(out, "files", d)).st_mtime_ns - os.stat(os.path.join(src, d)).st_mtime_ns) > 2 * 10**9]
    check(not off, "modification times are restored on files and on folders")
    check(os.path.getsize(os.path.join(out, "errors.csv")) == 0, "errors.csv is empty")
    info = [json.loads(ln) for ln in read_text(os.path.join(out, "run_info.json")).splitlines()]
    check(len(info) == 1 and info[0]["version"] == sc.VERSION and info[0]["files"] == len(files)
          and info[0]["bytes"] == sum(len(d) for d in files.values()) and "drive" in info[0]["volume"],
          "run_info.json records the version, file and byte counts and the source volume")
    first = spy.calls[0]
    check(first == (BIG, "MainThread") and [c[0] for c in spy.calls].count(BIG) == 1,
          "two passes: the big file is copied first, once, on the main thread")
    pool = {t for _, t in spy.calls[1:]}
    check(len(spy.calls) == len(files) and "MainThread" not in pool and len(pool) > 1,
          f"... then the other {nsmall} files on a pool of {len(pool)} threads")

    print("4. verify and resume")
    r = call(sc.verify, out, watch=(os.path.join(out, "files"),))
    check(r.exc is None and r.result is True and "VERIFY PASS" in r.text and f"{len(files)} ok, 0 bad, 0 not in manifest" in r.text,
          "verify passes")
    hashers = set(GUARD.threads.values())
    check(len(GUARD.reads) == len(files) and "MainThread" not in hashers and len(hashers) > 1,
          f"verify reads each staged file once, on a pool of {len(hashers)} threads")
    quiet("verify")
    check(problems(out) == [], "verify_problems.csv lists nothing")

    spy2 = Spy(src)
    with patched(copy_one=spy2):
        r = call(sc.copy, src, out, watch=(src,))
    check(r.exc is None and spy2.calls == [] and len(manifest_rows(out)) == len(files)
          and "to copy now: 0 files" in r.text, "a second copy run copies nothing and adds no manifest rows")
    check(not GUARD.reads and not GUARD.hits, "... and does not even open a source file")

    changed, added = os.path.join("run02", "sub", "f03.dat"), os.path.join("run02", "sub", "added.dat")
    files[changed], files[added] = blob("changed", 70 * KB + 1), blob("added", 123)
    for rel in (changed, added):
        with open(os.path.join(src, rel), "wb") as f:
            f.write(files[rel])
        os.utime(os.path.join(src, rel), ns=(OLD_NS + 10**15, OLD_NS + 10**15))
    before = snapshot(src)
    spy3 = Spy(src)
    with patched(copy_one=spy3):
        r = call(sc.copy, src, out, watch=(src,))
    check(r.exc is None and sorted(spy3.attempts()) == sorted([changed, added]),
          "after one source file changed and another appeared, only those two are copied")
    check(len(manifest_rows(out)) == len(files) + 1 and sc.load_manifest(os.path.join(out, "manifest.csv"))[changed]["sha256"] == sha(files[changed]),
          "the changed file gets a new manifest row, which wins over the old one")
    quiet("resume")
    untouched(src, before, "resume")
    r = call(sc.verify, out)
    check(r.result is True, "verify passes on the resumed tree (the newest row per file counts)")

    print("5. verify fails when it should")
    big_dst = os.path.join(out, "files", BIG)
    with open(big_dst, "r+b") as f:
        f.seek(-3, os.SEEK_END)
        orig = f.read(1)
        f.seek(-3, os.SEEK_END)
        f.write(bytes([orig[0] ^ 0xFF]))
    r = call(sc.verify, out)
    check(r.result is False and "VERIFY FAIL" in r.text and problems(out) == [(BIG, "CHECKSUM MISMATCH")],
          "one flipped byte near the end of the big file: FAIL, and exactly that file is named")
    with open(big_dst, "r+b") as f:
        f.seek(-3, os.SEEK_END)
        f.write(orig)
    check(call(sc.verify, out).result is True, "put the byte back: PASS again")
    os.remove(os.path.join(out, "files", "mid.bin"))
    with open(os.path.join(out, "files", "stray.txt"), "wb") as f:
        f.write(b"not from the drive")
    r = call(sc.verify, out)
    got = {rel: prob for rel, prob in problems(out)}
    check(r.result is False and set(got) == {"mid.bin", "stray.txt"} and got["mid.bin"].startswith("UNREADABLE")
          and got["stray.txt"] == "NOT IN MANIFEST", "a missing file is UNREADABLE and a stray file is NOT IN MANIFEST")


# ---------- 6. failing files ----------

def check_failing_files(td):
    print("6. failing files: a lock mid-read with an unprintable name, an unexpected error, a flaky read")
    src, out = os.path.join(td, "fault_drive"), os.path.join(td, "fault_staged")
    bad = "bad" + F00D + ".bin"
    files = {"a_ok.txt": blob("fa", 1500), bad: blob("fbad", 3 * MB), "flaky.txt": blob("ff", 2000),
             "odd.txt": blob("fo", 1800), "z_ok.txt": blob("fz", 2500)}
    make_tree(src, files)
    before = snapshot(src)
    flaked = []

    def fail(rel):
        if rel == "odd.txt":
            return ValueError("simulated: not an I/O error")  # must be neither retried nor fatal
        if rel == "flaky.txt" and not flaked:                 # a stall that clears on the second attempt
            flaked.append(1)
            return OSError(5, "simulated stall")
        return None

    spy, clock = Spy(src, fail=fail), FakeTime()
    try:
        with patched(time=clock, copy_one=spy), byte_range_lock(os.path.join(src, bad), MB, MB):
            r = call(sc.copy, src, out, watch=(src,))
    except OSError as e:
        check(False, f"could not hold the byte-range lock that simulates the bad sector: {e}")
        return
    check(r.exc is None, f"the run finishes: no exception escaped a worker ({r.exc})")
    att = spy.attempts()
    check(att[bad] == sc.READ_ATTEMPTS and att["flaky.txt"] == 2 and att["odd.txt"] == 1 and att["a_ok.txt"] == 1,
          f"the lasting failure is tried {sc.READ_ATTEMPTS} times, the flaky file twice, the unexpected error once, a good file once")
    check(sorted(clock.sleeps) == sorted([sc.RETRY_PAUSE, 2 * sc.RETRY_PAUSE, sc.RETRY_PAUSE]),
          f"the pauses are {sc.RETRY_PAUSE:g} s then {2 * sc.RETRY_PAUSE:g} s for the lasting failure and {sc.RETRY_PAUSE:g} s for the flaky one")
    check({x["relpath"] for x in manifest_rows(out)} == {"a_ok.txt", "flaky.txt", "z_ok.txt"},
          "the good and the recovered files are manifested; the two failures are not")
    rows = {row[1]: row for row in errors_rows(out)}
    check(set(rows) == {bad, "odd.txt"} and rows[bad][2] == str(3 * MB) and rows[bad][3].startswith("PermissionError")
          and rows["odd.txt"][3].startswith("ValueError"), "errors.csv has the two failures, with size and error type")
    check(re.search(r"retry 1/\d+ on bad.\.bin after PermissionError", r.text) and re.search(r"ERROR bad.\.bin: PermissionError", r.text)
          and "bad?.bin" in r.text and re.search(r"retry 1/\d+ on flaky.txt after OSError", r.text) and "ERROR odd.txt: ValueError" in r.text,
          "the console still gets every retry and ERROR line, the unprintable character degraded to ?")
    check(bad in read_text(os.path.join(out, "copy.log")), "copy.log (UTF-8) keeps the real name")
    check(re.search(r"DONE: copied 3 files.*errors 2", r.text) is not None, "the run ends DONE with errors 2")
    check(not [n for n in staged(out)[0] if n.endswith(".part")], "no .part file is left behind")
    quiet("failing files")
    untouched(src, before, "failing files")

    spy2 = Spy(src)
    with patched(copy_one=spy2):
        call(sc.copy, src, out, watch=(src,))
    check(sorted(spy2.attempts()) == sorted([bad, "odd.txt"]), "once the lock is gone, the next run copies just the two that failed")
    check(call(sc.verify, out).result is True and len(manifest_rows(out)) == len(files), f"verify passes with all {len(files)} files")


# ---------- 7. a file that changes size under the copy ----------

def check_torn_read(td):
    print("7. a file whose size changes between the directory scan and the read")
    src, out = os.path.join(td, "torn_drive"), os.path.join(td, "torn_staged")
    make_tree(src, {"ok.txt": blob("tok", 800), "grow.txt": blob("tgrow", 4000)})
    grown = []

    def grow(rel):
        if rel == "grow.txt" and not grown:
            grown.append(1)
            with open(os.path.join(src, rel), "ab") as f:  # the test itself writes here, so this drive is not guarded
                f.write(b" ...appended while the copy was reading it")

    with patched(time=FakeTime(), copy_one=Spy(src, before=grow)):
        r = call(sc.copy, src, out)
    rows = errors_rows(out)
    check(r.exc is None and {x["relpath"] for x in manifest_rows(out)} == {"ok.txt"}, "the run finishes; the changed file is not manifested")
    check(len(rows) == 1 and rows[0][1] == "grow.txt" and "size changed during read" in rows[0][3],
          "errors.csv says the size changed during the read")
    r = call(sc.verify, out)
    check(r.result is False and problems(out) == [("grow.txt", "NOT IN MANIFEST")], "until it is re-run, verify flags the half-recorded file")
    spy2 = Spy(src)
    with patched(copy_one=spy2):
        call(sc.copy, src, out)
    with open(os.path.join(src, "grow.txt"), "rb") as f:
        now = f.read()
    row = sc.load_manifest(os.path.join(out, "manifest.csv"))["grow.txt"]
    check(list(spy2.attempts()) == ["grow.txt"] and row["size"] == str(len(now)) and row["sha256"] == sha(now),
          "the next run copies it again, with its new size and hash")
    check(call(sc.verify, out).result is True, "verify then passes")


# ---------- 8. the circuit breaker ----------

def check_breaker(td):
    print("8. circuit breaker")
    quiet_src, quiet_out = os.path.join(td, "scattered_drive"), os.path.join(td, "scattered_staged")
    make_tree(quiet_src, {f"f{i}.txt": blob(f"f{i}", 2000 + i) for i in range(1, 8)})
    scattered = Spy(quiet_src, fail=lambda rel: OSError(5, "simulated") if rel in ("f2.txt", "f3.txt", "f5.txt", "f6.txt") else None)
    with patched(CONSECUTIVE_FAIL_LIMIT=3, COPY_WORKERS=1, time=FakeTime(), copy_one=scattered):
        r = call(sc.copy, quiet_src, quiet_out)
    check(r.exc is None and r.code == 0 and re.search(r"DONE: copied 3 files.*errors 4", r.text) is not None,
          "four failures, but never three in a row (a success resets the count): the breaker stays quiet")

    src, out = os.path.join(td, "breaker_drive"), os.path.join(td, "breaker_staged")
    names = ["a1.txt", "a2.txt", "b1.txt", "b2.txt", "b3.txt", "c1.txt", "c2.txt"]
    make_tree(src, {n: blob(n, 3000 + i) for i, n in enumerate(names)})
    spy = Spy(src, fail=lambda rel: OSError(5, "simulated bad sector") if rel.startswith("b") else None)
    with patched(CONSECUTIVE_FAIL_LIMIT=3, COPY_WORKERS=1, time=FakeTime(), copy_one=spy):
        r = call(sc.copy, src, out, watch=(src,))
    check(r.exc is None and r.code == 3, f"3 failures in a row stop the run with exit code 3 ({r.exc or r.code})")
    check("CIRCUIT BREAKER" in r.text and "ABORTED BY CIRCUIT BREAKER" in r.text, "the console says why")
    check(dict(spy.attempts()) == {"a1.txt": 1, "a2.txt": 1, "b1.txt": sc.READ_ATTEMPTS, "b2.txt": sc.READ_ATTEMPTS, "b3.txt": sc.READ_ATTEMPTS},
          f"each failing file got {sc.READ_ATTEMPTS} attempts, and c1/c2 were never attempted")
    check({x["relpath"] for x in manifest_rows(out)} == {"a1.txt", "a2.txt"} and len(errors_rows(out)) == 3,
          "the manifest keeps the progress; errors.csv has the three failures")
    quiet("breaker")
    spy2 = Spy(src)
    with patched(copy_one=spy2):
        r = call(sc.copy, src, out, watch=(src,))
    check(r.code == 0 and sorted(spy2.attempts()) == ["b1.txt", "b2.txt", "b3.txt", "c1.txt", "c2.txt"],
          "the next run copies the other five files and skips the two already done")
    check(call(sc.verify, out).result is True and len(manifest_rows(out)) == len(names), "verify passes with all seven")


# ---------- 9. the command line ----------

def check_cli(td):
    print("9. command line")
    src, out, inv = os.path.join(td, "cli" + F00D + "drive"), os.path.join(td, "cli_staged"), os.path.join(td, "cli_inventory")
    files = {"a.txt": blob("ca", 900), os.path.join("sub", "b.bin"): blob("cb", 2 * MB + 5), "Icon" + F00D: b""}
    make_tree(src, files)
    before = snapshot(src)
    # a stdout that raises on U+F00D, as a cp1252 console does: the script must switch it to UTF-8
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    env["PYTHONIOENCODING"] = "cp1252:strict"

    def cli(*args):
        p = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, env=env, cwd=td, timeout=180)
        return p.returncode, p.stdout, p.stderr.decode("utf-8", "replace")

    rc, so, se = cli("inventory", src, inv)
    with open(os.path.join(inv, "inventory.csv"), newline="", encoding="utf-8") as f:
        nfiles = sum(1 for row in list(csv.reader(f))[1:] if row[0] == "F")
    check(rc == 0 and nfiles == len(files) and f"Files: {len(files)}" in read_text(os.path.join(inv, "summary.txt")),
          f"inventory exits 0 and lists {len(files)} files")
    rc, so, se = cli("copy", src, out)
    check(rc == 0 and b"DONE: copied 3 files" in so and "Traceback" not in se, "copy exits 0")
    check(F00D.encode("utf-8") in so, "stdout was switched to UTF-8: the U+F00D in the source path comes out intact")
    check({x["relpath"] for x in manifest_rows(out)} == set(files), "the manifest has all three files")
    rc, so, se = cli("verify", out)
    check(rc == 0 and b"VERIFY PASS" in so, "verify exits 0 on a good copy")
    with open(os.path.join(out, "files", "sub", "b.bin"), "r+b") as f:
        f.seek(1000)
        b = f.read(1)
        f.seek(1000)
        f.write(bytes([b[0] ^ 0xFF]))
    rc, so, se = cli("verify", out)
    check(rc == 1 and b"VERIFY FAIL" in so, "verify exits 1 on a corrupted copy")
    rc, so, se = cli()
    check(rc != 0 and "inventory" in se and "verify" in se, "no arguments: the usage text and a non-zero exit")
    check(cli("bogus", src)[0] != 0 and cli("copy", src)[0] != 0, "an unknown mode, or copy without a destination: non-zero exit")
    untouched(src, before, "the command line")


def main():
    check_guard()
    with tmpdir() as td:
        td = os.path.abspath(td)  # as stage_copy's own longpath() makes it
        print("1. the drive")
        check_main_drive(td)
        check_failing_files(td)
        check_torn_read(td)
        check_breaker(td)
        check_cli(td)
        gc.collect()  # release the Log file handles before the temp dir is removed
    if FAILS:
        say(f"\n{len(FAILS)} FAILED")
        sys.exit(1)
    say("\nall ok")


if __name__ == "__main__":
    main()
