#!/usr/bin/env python3
"""test_mri_archive.py -- the MRI platform archive's access module is read-only by construction.

Covers the three rules of Ryan, 2026-10-07 ("critical importance"), as `tools/mri_archive.py` enforces them:

  1. No write path exists. The wrapper exposes only listdir_attr / stat / open("rb") / close; every write,
     rename, chmod, delete, shell or command method is ABSENT (the attribute does not exist), nothing can be
     added later (__slots__), it holds no SFTP client, and a non-"rb" open is refused before the remote is
     touched. The file it returns can only read / seek / tell / close. Paths outside the archive root are
     refused. connect() opens only the SFTP subsystem (no exec_command, no shell). An AST scan of the module
     finds no call to any remote-write method name.
  2. One connection, sequential calls: a second connect() while one is live is refused; file contents are
     refused 08:00-18:00 Monday-Friday (listing is allowed then, paced).
  3. Credentials: only the [mri_archive] section is read, never [mri]; a missing section or field is an
     error; the password never appears in a message or a summary.

No network, no NAS, no pytest: fakes and temporary files only.

Run:  python tools/test_mri_archive.py      (exit 0 = pass)
"""

import ast
import datetime as dt
import io
import os
import shutil
import stat
import sys
import tempfile
import types

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import mri_archive as ma  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    except Exception as e:  # noqa: BLE001
        print(f"        (raised {type(e).__name__}: {e})")
        return False
    return False


# Every remote-changing (or shell) method name of paramiko's SFTPClient / SFTPFile / Transport / SSHClient.
FORBIDDEN = {
    "put", "putfo", "get", "getfo", "remove", "unlink", "rename", "posix_rename", "mkdir", "rmdir", "chmod",
    "chown", "utime", "truncate", "symlink", "file", "chdir", "normalize", "readlink", "listdir", "lstat",
    "exec_command", "invoke_shell", "invoke_subsystem", "open_session", "open_channel", "get_channel",
    "get_transport", "sftp", "_sftp", "client", "_client", "transport", "_transport", "write", "writelines",
    "flush", "set_pipelined", "setstat", "fsetstat",
}
# Names that may never be CALLED as an attribute anywhere in mri_archive.py (remote writes / shell).
FORBIDDEN_CALLS = {
    "put", "putfo", "remove", "unlink", "rename", "posix_rename", "mkdir", "rmdir", "chmod", "chown", "utime",
    "truncate", "symlink", "exec_command", "invoke_shell", "open_session", "get_channel", "setstat", "fsetstat",
}

WED = dt.datetime(2026, 10, 7, 10, 0)    # a Wednesday, 10:00
WED_EVE = dt.datetime(2026, 10, 7, 19, 0)
SAT = dt.datetime(2026, 10, 10, 10, 0)


class Attr:
    def __init__(self, name, mode, size=0, mtime=1_700_000_000):
        self.filename, self.st_mode, self.st_size, self.st_mtime = name, mode, size, mtime


class FakeRemoteFile:
    def __init__(self, data):
        self._b = io.BytesIO(data)
        self.closed = False
        self.on_read = None

    def read(self, size=None):
        if self.on_read is not None:
            self.on_read()
        return self._b.read() if size is None else self._b.read(size)

    def seek(self, off, whence=0):
        return self._b.seek(off, whence)

    def tell(self):
        return self._b.tell()

    def close(self):
        self.closed = True

    def write(self, data):  # present on the remote object, must be unreachable through the wrapper
        raise AssertionError("write reached the remote file")


class FakeSFTP:
    """A stand-in SFTP client with the dangerous methods too: none of them may ever be called."""

    def __init__(self, tree=None, files=None, on_read=None):
        self.calls = []
        self.tree = tree or {}
        self.files = files or {}
        self.on_read = on_read
        self.opened = []

    def listdir_attr(self, p):
        self.calls.append(("listdir_attr", p))
        return self.tree.get(p, [])

    def stat(self, p):
        self.calls.append(("stat", p))
        return Attr(p.rsplit("/", 1)[-1], stat.S_IFREG | 0o644, 5)

    def open(self, p, mode="r"):
        self.calls.append(("open", p, mode))
        f = FakeRemoteFile(self.files.get(p, b"hello"))
        if self.on_read is not None:
            f.on_read = self.on_read
        self.opened.append(f)
        return f

    def close(self):
        self.calls.append(("close",))

    def __getattr__(self, name):  # remove, rename, put, chmod, ...
        def _danger(*a, **kw):
            self.calls.append(("DANGER", name))
            raise AssertionError(f"forbidden remote call: {name}")
        return _danger


def make(fake=None, now=WED_EVE, sleeps=None):
    fake = fake or FakeSFTP()
    rec = sleeps if sleeps is not None else []
    return fake, ma.ReadOnlyArchive(fake.listdir_attr, fake.stat, fake.open, fake.close,
                                     now=lambda: now, sleep=rec.append)


# ----------------------------------------------------------------------------------------------------------
print("1. The wrapper has no write path")
fake, arc = make()
public = {n for n in dir(arc) if not n.startswith("_")}
check(public == {"listdir_attr", "stat", "open", "close", "calls", "label"},
      f"public surface is exactly listdir_attr/stat/open/close (+ calls, label): {sorted(public)}")
present = sorted(n for n in FORBIDDEN if hasattr(arc, n))
check(not present, f"no forbidden attribute exists on the wrapper ({len(FORBIDDEN)} names checked){': ' + str(present) if present else ''}")
check(raises(AttributeError, setattr, arc, "remove", lambda p: None), "nothing can be added to the wrapper (__slots__)")
check(raises(AttributeError, getattr, arc, "_sftp"), "the wrapper keeps no SFTP client attribute")
held = [getattr(arc, s) for s in ma.ReadOnlyArchive.__slots__ if hasattr(arc, s)]
check(not any(isinstance(v, FakeSFTP) for v in held), "no slot holds the SFTP client object")
remote_fns = sorted(getattr(v, "__name__", "") for v in held if getattr(v, "__self__", None) is fake)
check(remote_fns == ["close", "listdir_attr", "open", "stat"],
      f"the only remote callables held are listdir_attr, stat, open and close: {remote_fns}")

for mode in ("wb", "w", "r+", "rb+", "ab", "a", "x", "r", "w+b", ""):
    before = len(fake.calls)
    ok = raises(ma.ReadOnlyViolation, arc.open, ma.ARCHIVE_ROOT + "/2019_pv6/x.tar.gz", mode)
    check(ok and len(fake.calls) == before, f"open(mode={mode!r}) refused before the remote is touched")

f = arc.open(ma.ARCHIVE_ROOT + "/2019_pv6/x.tar.gz")
check(fake.calls[-1] == ("open", ma.ARCHIVE_ROOT + "/2019_pv6/x.tar.gz", "rb"), "open() asks the remote for 'rb' only")
fpublic = {n for n in dir(f) if not n.startswith("_")}
check(fpublic == {"read", "seek", "tell", "close"}, f"the opened file exposes only read/seek/tell/close: {sorted(fpublic)}")
check(not any(hasattr(f, n) for n in ("write", "writelines", "truncate", "chmod", "flush", "set_pipelined")),
      "the opened file has no write / truncate / chmod / flush")
check(raises(AttributeError, setattr, f, "write", lambda b: None), "nothing can be added to the opened file")
with f:
    check(f.read(2) == b"he" and f.tell() == 2 and f.read() == b"llo", "read / tell work")
check(raises(ValueError, f.read), "read after close is refused")
check(not any(c[0] == "DANGER" for c in fake.calls), "no forbidden remote method was ever called")

# ----------------------------------------------------------------------------------------------------------
print("2. Paths stay inside the archive root")
check(ma.archive_path("2019_pv6") == ma.ARCHIVE_ROOT + "/2019_pv6", "a relative path is joined to the root")
check(ma.archive_path(ma.ARCHIVE_ROOT) == ma.ARCHIVE_ROOT, "the root itself is allowed")
for bad in ("/share/homes/mriuser", "/", "../x", ma.ARCHIVE_ROOT + "/../other", ma.ARCHIVE_ROOT + "_x/y",
            "/opt/PV6.0.1/data/nmr", ""):
    before = len(fake.calls)
    check(raises(ma.OutsideArchiveError, arc.listdir_attr, bad) and len(fake.calls) == before,
          f"outside the root refused before the remote is touched: {bad!r}")
check(raises(ma.OutsideArchiveError, arc.stat, "/etc/passwd"), "stat outside the root refused")

# ----------------------------------------------------------------------------------------------------------
print("3. File contents only outside 08:00-18:00 Monday-Friday; listing paced in those hours")
cases = [(dt.datetime(2026, 10, 7, 7, 59), True), (dt.datetime(2026, 10, 7, 8, 0), False),
         (dt.datetime(2026, 10, 7, 17, 59), False), (dt.datetime(2026, 10, 7, 18, 0), True),
         (dt.datetime(2026, 10, 5, 12, 0), False), (dt.datetime(2026, 10, 9, 12, 0), False),
         (SAT, True), (dt.datetime(2026, 10, 11, 12, 0), True)]
for when, allowed in cases:
    fk, a = make(now=when)
    if allowed:
        a.open("2019_pv6/x.tar.gz").close()
        check(fk.calls and fk.calls[-1][0] == "open", f"{when:%a %H:%M}: open allowed")
    else:
        check(raises(ma.WorkingHoursError, a.open, "2019_pv6/x.tar.gz") and not fk.calls,
              f"{when:%a %H:%M}: open refused, the remote untouched")
check(ma.in_working_hours(WED) and not ma.in_working_hours(WED_EVE) and not ma.in_working_hours(SAT),
      "in_working_hours: Wed 10:00 yes, Wed 19:00 no, Sat 10:00 no")
sleeps = []
fk, a = make(now=WED, sleeps=sleeps)
a.listdir_attr(ma.ARCHIVE_ROOT)
a.listdir_attr(ma.ARCHIVE_ROOT)
a.stat("2019_pv6")
check(len(fk.calls) == 3 and a.calls == 3, "listing and stat are allowed during working hours")
check(len(sleeps) >= 1 and all(0 < s <= ma.WORKING_HOURS_PACE_S for s in sleeps),
      f"calls are paced during working hours (slept {len(sleeps)}x, each <= {ma.WORKING_HOURS_PACE_S}s)")
sleeps2 = []
fk, a = make(now=WED_EVE, sleeps=sleeps2)
a.listdir_attr(ma.ARCHIVE_ROOT)
a.listdir_attr(ma.ARCHIVE_ROOT)
check(not sleeps2, "no pacing outside working hours")
a.close()
check(raises(ma.ArchiveError, a.listdir_attr, ma.ARCHIVE_ROOT), "a closed wrapper refuses every call")
check(fk.calls[-1] == ("close",), "close() closes the connection")

# ----------------------------------------------------------------------------------------------------------
print("4. Credentials: [mri_archive] only, never printed")
tmp = tempfile.mkdtemp(prefix="test_mri_archive_")
SECRET = "s3cr3t-Pa55"


def cred_file(text):
    p = os.path.join(tmp, f"c{len(os.listdir(tmp))}.cred")
    with io.open(p, "w", encoding="utf-8") as fh:
        fh.write(text)
    return p


def msg_of(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {e}"
    return ""


m = msg_of(ma.load_credentials, os.path.join(tmp, "absent.cred"))
check(m.startswith("CredentialsError"), "a missing credentials file is an error")
only_mri = cred_file(f"[mri]\nhost = kenia.example\nuser = mriuser\npassword = {SECRET}\n")
m = msg_of(ma.load_credentials, only_mri)
check(m.startswith("CredentialsError") and "mri_archive" in m and SECRET not in m,
      "a file with only [mri] is refused (never falls back to the scanner's section); no password in the message")
check(raises(ma.CredentialsError, ma.load_credentials, only_mri, "mri"), "asking for the [mri] section is refused")
no_pw = cred_file("[mri_archive]\nhost = 10.0.0.1\nuser = mriuser\n")
m = msg_of(ma.load_credentials, no_pw)
check(m.startswith("CredentialsError") and "password" in m, "a missing password is an error naming the field")
bad_port = cred_file(f"[mri_archive]\nhost = 10.0.0.1\nuser = u\npassword = {SECRET}\nport = twenty\n")
m = msg_of(ma.load_credentials, bad_port)
check(m.startswith("CredentialsError") and SECRET not in m, "a bad port is an error; no password in the message")
good = cred_file(f"[mri]\nhost = kenia.example\nuser = mriuser\npassword = other\n\n"
                 f"[mri_archive]\nhost = 10.0.0.1\nuser = mriuser\npassword = {SECRET}%x\n")
c = ma.load_credentials(good)
check(c == {"host": "10.0.0.1", "user": "mriuser", "password": SECRET + "%x", "port": 22},
      "the [mri_archive] section is read (port defaults to 22; '%' is literal)")
check(SECRET not in ma.describe_credentials(c) and "password present: True" in ma.describe_credentials(c),
      "describe_credentials says only whether a password is present")

# ----------------------------------------------------------------------------------------------------------
print("5. connect(): the SFTP subsystem only, one connection per process")


class FakeKey:
    def asbytes(self):
        return b"key"

    def get_name(self):
        return "ssh-ed25519"


class FakeTransport:
    instances = []

    def __init__(self, addr):
        self.addr, self.calls = addr, []
        FakeTransport.instances.append(self)

    def connect(self, username=None, password=None, **kw):
        self.calls.append(("connect", username, bool(password)))

    def get_remote_server_key(self):
        return FakeKey()

    def close(self):
        self.calls.append(("close",))

    def __getattr__(self, name):  # exec_command, open_session, invoke_shell, ...
        if name.startswith("__"):
            raise AttributeError(name)

        def _danger(*a, **kw):
            self.calls.append(("DANGER", name))
            raise AssertionError(f"forbidden transport call: {name}")
        return _danger


SFTPS = []


class FakeSFTPClient:
    @staticmethod
    def from_transport(t):
        s = FakeSFTP()
        SFTPS.append(s)
        return s


fake_paramiko = types.SimpleNamespace(Transport=FakeTransport, SFTPClient=FakeSFTPClient)
saved = sys.modules.get("paramiko")
sys.modules["paramiko"] = fake_paramiko
logs = []
try:
    ma._ACTIVE["archive"] = None
    a1 = ma.connect(good, log=logs.append)
    t1 = FakeTransport.instances[-1]
    check(isinstance(a1, ma.ReadOnlyArchive), "connect() returns the read-only wrapper")
    check(t1.addr == ("10.0.0.1", 22) and t1.calls[0] == ("connect", "mriuser", True),
          "it connects with the [mri_archive] host, port and user")
    check(not any(c[0] == "DANGER" for c in t1.calls), "no exec_command, shell or channel was opened")
    check(logs and SECRET not in logs[0] and "ssh-ed25519" in logs[0], "the log line names the host key, never the password")
    check(raises(ma.ConnectionInUseError, ma.connect, good, log=None), "a second connection while one is live is refused")
    a1.listdir_attr(ma.ARCHIVE_ROOT)
    a1.close()
    check(t1.calls[-1] == ("close",) and SFTPS[0].calls[-1] == ("close",), "close() closes the SFTP session and the transport")
    a2 = ma.connect(good, log=None)
    check(isinstance(a2, ma.ReadOnlyArchive), "after close, a new connection is allowed")
    a2.close()
    check(not any(c[0] == "DANGER" for s in SFTPS for c in s.calls), "no forbidden SFTP method was called")
finally:
    ma._ACTIVE["archive"] = None
    if saved is not None:
        sys.modules["paramiko"] = saved
    else:
        sys.modules.pop("paramiko", None)

# ----------------------------------------------------------------------------------------------------------
print("6. The module never calls a remote-write or shell method (AST scan)")
src_path = os.path.join(_THIS_DIR, "mri_archive.py")
with io.open(src_path, encoding="utf-8") as fh:
    tree = ast.parse(fh.read())
called = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        called.add(node.func.attr)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) > 1 \
            and isinstance(node.args[1], ast.Constant):
        called.add(node.args[1].value)
bad = sorted(called & FORBIDDEN_CALLS)
check(not bad, f"no call to {sorted(FORBIDDEN_CALLS)[:6]}... in mri_archive.py{': ' + str(bad) if bad else ''}")
opens = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
         and n.func.attr == "_open"]
check(len(opens) == 1 and isinstance(opens[0].args[1], ast.Name) and opens[0].args[1].id == "READ_ONLY_MODE",
      "the one remote open passes READ_ONLY_MODE")
check(ma.READ_ONLY_MODE == "rb", "READ_ONLY_MODE is 'rb'")

# ----------------------------------------------------------------------------------------------------------
print("7. The listing helper: sequential, depth-limited, links not followed, written locally")
R = ma.ARCHIVE_ROOT
tree = {
    R: [Attr("2019_pv6", stat.S_IFDIR | 0o755), Attr("link", stat.S_IFLNK | 0o777)],
    R + "/2019_pv6": [Attr("a_1_1.tar.gz", stat.S_IFREG | 0o644, 10), Attr("a_1_1.tar.gz.sha1", stat.S_IFREG | 0o644, 41),
                      Attr("configurations", stat.S_IFDIR | 0o755)],
    R + "/2019_pv6/configurations": [Attr("deep", stat.S_IFREG | 0o644, 1)],
}
fk, a = make(fake=FakeSFTP(tree))
rows = list(ma.walk(a, R, max_depth=2))
names = [(r["name"], r["kind"], r["depth"]) for r in rows]
check(names == [("2019_pv6", "dir", 1), ("link", "link", 1), ("a_1_1.tar.gz", "file", 2),
                ("a_1_1.tar.gz.sha1", "file", 2), ("configurations", "dir", 2)],
      f"walk yields every entry to max_depth, in order: {names}")
check([c[1] for c in fk.calls] == [R, R + "/2019_pv6"], "one listing per folder, sequentially; the link and the deeper folder are not listed")
out = os.path.join(tmp, "listing.csv")
n = ma.write_listing(rows, out)
with io.open(out, encoding="utf-8") as fh:
    text = fh.read()
check(n == 5 and text.startswith(",".join(ma.LISTING_FIELDS)) and "a_1_1.tar.gz" in text, "write_listing writes a local csv")

# ----------------------------------------------------------------------------------------------------------
print("8. fetch: the pull plan's archives to LOCAL disk, verified; after hours only; resumable")
import csv  # noqa: E402
import gzip  # noqa: E402
import hashlib  # noqa: E402
import lzma  # noqa: E402
import posixpath  # noqa: E402
import random  # noqa: E402
import tarfile  # noqa: E402

THU_0758 = dt.datetime(2026, 10, 8, 7, 58)
THU_0800 = dt.datetime(2026, 10, 8, 8, 0)
rnd = random.Random(7)


def tarball(compression, members):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tf:
        for name_, data_ in members.items():
            ti = tarfile.TarInfo(name_)
            ti.size = len(data_)
            tf.addfile(ti, io.BytesIO(data_))
    return gzip.compress(raw.getvalue()) if compression == "tar.gz" else lzma.compress(raw.getvalue())


Y19, Y22 = R + "/2019_pv6", R + "/2022_pv6"
TIER = {"A": "A: MFB animal session, new", "A2": "A2: MFB, a second session of an animal production holds that day",
        "B": "B: MFB phantom/QC, new", "C": "C: stream M originals check (no ingest)",
        "D": "D: MFB, in production under another folder name (no pull; listed)",
        "E": "E: MFB-linked, needs a ruling (no pull until ruled)", "X": "X: empty archive (no pull)"}
# (tier, study, folder, compression, checksum file kind, what is wrong)
SPECS = [
    ("C", "20190301_100000_jrc190301_m1_0219_1_1", Y19, "tar.gz", "sha1", ""),
    ("A", "20190201_100000_jrc190201_m2_0219_1_1", Y19, "tar.gz", "sha1", ""),
    ("A2", "20220127_141444_jrc220127_m153_post_0618_1_1", Y22, "tar.xz", "", ""),
    ("B", "20220324_151835_jrc220324_Phantom_AB_1_1", Y22, "tar.gz", "sha256", ""),
    ("B", "20190105_090000_jrc190105_qa_1_1", Y19, "tar.gz", "sha1", "wrong checksum"),
    ("B", "20220110_090000_jrc220110_x_1_1", Y22, "tar.gz", "", "corrupt"),
    ("E", "20190110_090000_sp190110_ABH_1116_1_1", Y19, "tar.gz", "sha1", ""),
    ("X", "20190111_090000_jrc190111_empty_1_1", Y19, "tar.gz", "sha1", ""),
    ("D", "20190112_090000_jrc190112_m9_0219_1_1", Y19, "tar.gz", "sha1", ""),
]
FILES, TREE, PLAN, BY = {}, {Y19: [], Y22: []}, [], {}
for code, study, folder, comp, kind, wrong in SPECS:
    data = tarball(comp, {f"{study}/1/fid": rnd.randbytes(30000), f"{study}/subject": b"##$SUBJECT_id=<m1>\n"})
    if wrong == "corrupt":
        data = data[:len(data) // 2] + bytes([data[len(data) // 2] ^ 0xFF]) + data[len(data) // 2 + 1:]
    path = f"{folder}/{study}.{comp}"
    FILES[path] = data
    TREE[folder].append(Attr(f"{study}.{comp}", stat.S_IFREG | 0o666, len(data)))
    if kind:
        digest = getattr(hashlib, kind)(data).hexdigest()
        if wrong == "wrong checksum":
            digest = "0" * len(digest)
        side = (f"{digest}  {study}.{comp}\n" if kind == "sha1" else f"{digest}  /mnt/backup/7T/{study}.{comp}\n").encode()
        FILES[path + "." + kind] = side
        TREE[folder].append(Attr(f"{study}.{comp}.{kind}", stat.S_IFREG | 0o666, len(side)))
    PLAN.append({"tier": TIER[code], "study": study, "date": study[:8], "owner": "MFB", "chosen_path": path,
                 "compression": comp, "size": len(data), "checksum": kind})
    BY[study] = path
TREE[Y19].append(Attr("00_LOGFILE_sha1.txt", stat.S_IFREG | 0o666, 100))

ftmp = tempfile.mkdtemp(prefix="test_mri_fetch_")
plan_csv = os.path.join(ftmp, "pull_plan.csv")
with io.open(plan_csv, "w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(PLAN[0].keys()))
    w.writeheader()
    w.writerows(PLAN)
FAKES = []


def new_arc(now_fn, on_read=None):
    fk_ = FakeSFTP(TREE, FILES, on_read)
    FAKES.append(fk_)
    return fk_, ma.ReadOnlyArchive(fk_.listdir_attr, fk_.stat, fk_.open, fk_.close, now=now_fn, sleep=lambda s: None)


def opens(fk_):
    return [c[1] for c in fk_.calls if c[0] == "open"]


def files_under(d):
    return sorted(os.path.relpath(os.path.join(r, f), d) for r, _, fs in os.walk(d) for f in fs)


def manifest_of(d):
    return ma.Manifest(os.path.join(d, ma.MANIFEST_NAME)).latest()


QUIET = []
# -- selection -----------------------------------------------------------------------------------------------
rows = ma.load_plan(plan_csv)
pull, skipped = ma.select_plan(rows)
order = [it["study"][:8] for it in pull]
check(order == ["20190301", "20190105", "20190201", "20220110", "20220127", "20220324"],
      f"the pulled tiers (C, A, A2, B) in fetch order: C first, then by date: {order}")
check(sorted(ma.tier_code(r["tier"]) for r in skipped) == ["D", "E", "X"], "tiers D, E and X are not pulled")
check(raises(ma.ArchiveError, ma.select_plan, rows + [dict(rows[0], tier="F: something new", study="z")]),
      "an unknown tier is refused (nothing is guessed)")
check(raises(ma.OutsideArchiveError, ma.select_plan, [dict(rows[0], chosen_path="/share/homes/mriuser/x/y.tar.gz")]),
      "a chosen path outside the archive root is refused")
check(raises(ma.ArchiveError, ma.select_plan, [rows[0], dict(rows[0], study="again")]),
      "two plan rows for the same archive are refused")
summ = ma.plan_summary(pull, skipped)
check(any(s.startswith("  C ") and " 1 archives" in s for s in summ)
      and any(s.startswith("  B ") and " 3 archives" in s and "none 1, sha1 1, sha256 1" in s for s in summ)
      and any(s.startswith("not pulled: D 1") and "E 1" in s and "X 1" in s for s in summ),
      "the summary gives counts, GB and checksum kinds per tier, and the tiers not pulled")

# -- small pieces ------------------------------------------------------------------------------------------------
check(ma.next_work_start(WED_EVE) == THU_0800 and ma.next_work_start(dt.datetime(2026, 10, 8, 7, 0)) == THU_0800
      and ma.next_work_start(dt.datetime(2026, 10, 9, 19, 0)) == dt.datetime(2026, 10, 12, 8, 0)
      and ma.next_work_start(SAT) == dt.datetime(2026, 10, 12, 8, 0),
      "the deadline is the next 08:00 of a weekday (Wed eve -> Thu; Fri eve and Sat -> Mon)")
check(ma.parse_stop_at("07:30", WED_EVE) == dt.datetime(2026, 10, 8, 7, 30)
      and ma.parse_stop_at("23:00", WED_EVE) == dt.datetime(2026, 10, 7, 23, 0)
      and raises(ma.ArchiveError, ma.parse_stop_at, "7.30", WED_EVE), "--stop-at HH:MM is its next occurrence")
check(ma.deadline_for(WED_EVE, dt.datetime(2026, 10, 8, 9, 0)) == THU_0800, "--stop-at never extends past 08:00")
h40, h64 = "ab" * 20, "cd" * 32
check(ma.parse_digest(f"{h40.upper()}  x.tar.gz\n".encode(), "sha1") == h40
      and ma.parse_digest(f"{h64}  /some/path/x.tar.gz\n".encode(), "sha256") == h64
      and ma.parse_digest(f"{h64}  x\n".encode(), "sha1") == "" and ma.parse_digest(b"", "sha1") == "",
      "checksum files: the first digest of the right length (never part of a longer hex run)")
check(raises(ma.ArchiveError, ma.check_local_dest, r"\\GJESUS3\gjesus3\pull"), "a network destination is refused")
xz_good = tarball("tar.xz", {"s/1/fid": b"x" * 5000})
for label, blob, want in (("a good tar.xz", xz_good, True), ("a truncated tar.xz", xz_good[:-30], False),
                          ("a file that is not gz or xz", b"PK\x03\x04 not a tarball", False)):
    p = os.path.join(ftmp, "probe.bin")
    with io.open(p, "wb") as fh:
        fh.write(blob)
    ok_, note_ = ma.verify_tar_listing(p)
    check(ok_ is want, f"crc+listing on {label}: {'accepted' if want else 'refused'} ({note_})")

# -- the dry run: listing only, in working hours ---------------------------------------------------------------
fk, a = new_arc(lambda: WED)
dest = os.path.join(ftmp, "pull")
res = ma.dry_run(a, pull, skipped, dest, log=QUIET.append)
check(not opens(fk) and [c[0] for c in fk.calls] == ["listdir_attr", "listdir_attr"],
      "dry run (Wed 10:00): two folder listings, no file opened")
check(res["missing"] == 0 and res["size_differs"] == 0 and res["checksum_files_missing"] == 0 and res["left"] == 6,
      f"dry run: all 6 present, sizes as planned, checksum files present: {res}")
check(not os.path.exists(dest), "dry run writes nothing locally")

# -- the hours ----------------------------------------------------------------------------------------------------
fk, a = new_arc(lambda: WED)
check(raises(ma.WorkingHoursError, ma.fetch, a, pull, dest, now=lambda: WED, log=QUIET.append)
      and not fk.calls and not os.path.exists(dest), "fetch refuses to start at Wed 10:00; the remote untouched")
fk, a = new_arc(lambda: THU_0758)
dest0 = os.path.join(ftmp, "pull0")
res = ma.fetch(a, pull, dest0, now=lambda: THU_0758, log=QUIET.append)
check(not opens(fk) and "would not end before Thu 08:00" in res["stop_reason"] and files_under(dest0) == [],
      f"Thu 07:58: no file is started that cannot end before 08:00 ({res['stop_reason'][:60]}...)")
fk, a = new_arc(lambda: WED_EVE)
res = ma.fetch(a, pull, dest0, now=lambda: WED_EVE, max_bytes=1, log=QUIET.append)
check(not opens(fk) and "--max-gb" in res["stop_reason"] and files_under(dest0) == [], "--max-gb stops before exceeding it")
c_ = [dt.datetime(2026, 10, 8, 7, 59)]
fk, a = new_arc(lambda: c_[0])
f = a.open("2019_pv6/x.tar.gz")
first = f.read(1)
c_[0] = THU_0800
check(first == b"h" and raises(ma.WorkingHoursError, f.read, 1),
      "a file opened at 07:59 cannot be read from 08:00 (the guard runs on every read)")
f.close()

# -- a full run in the evening ------------------------------------------------------------------------------------
fk, a = new_arc(lambda: WED_EVE)
res = ma.fetch(a, pull, dest, now=lambda: WED_EVE, log=QUIET.append, chunk=4096)
man = manifest_of(dest)
st = {posixpath.basename(p).split("_")[0] + "/" + r["method"]: r["status"] for p, r in man.items()}
check(st == {"20190301/sha1": "verified", "20190201/sha1": "verified", "20220127/crc+listing": "verified",
             "20220324/sha256": "verified", "20190105/sha1": "bad", "20220110/crc+listing": "bad"},
      f"verified by .sha1, .sha256 and crc+listing; a SHA-1 mismatch and a corrupt no-checksum archive are bad: {st}")
check(res["verified"] == 4 and res["bad"] == 2 and res["error"] == 0 and res["stopped"] == 0, f"the run's counts: {res}")
same = all(io.open(os.path.join(dest, BY[s].split("/")[-2], BY[s].split("/")[-1]), "rb").read() == FILES[BY[s]]
           for s in BY if s[:8] in ("20190301", "20190201", "20220127", "20220324"))
check(same, "each verified archive is byte-identical to the remote one, under <dest>\\<year folder>\\<name>")
lay = files_under(dest)
check(not any(p.endswith(".part") for p in lay), "no .part is left after a complete run")
check(os.path.join("2019_pv6", "20190105_090000_jrc190105_qa_1_1.tar.gz.bad") in lay
      and os.path.join("2019_pv6", "20190105_090000_jrc190105_qa_1_1.tar.gz") not in lay
      and os.path.join("2022_pv6", "20220110_090000_jrc220110_x_1_1.tar.gz.bad") in lay,
      "a mismatch is kept as .bad, never renamed to the final name")
check(os.path.join("2019_pv6", "20190301_100000_jrc190301_m1_0219_1_1.tar.gz.sha1") in lay
      and os.path.join("2022_pv6", "20220324_151835_jrc220324_Phantom_AB_1_1.tar.gz.sha256") in lay,
      "the checksum files are fetched too, kept beside the archives")
rc = man[BY["20190301_100000_jrc190301_m1_0219_1_1"]]
check(rc["expected_sha1"] == rc["computed_sha1"] == hashlib.sha1(FILES[BY["20190301_100000_jrc190301_m1_0219_1_1"]]).hexdigest()
      and rc["started"] and rc["ended"] and rc["bytes_per_s"] and rc["size"] == str(len(FILES[BY["20190301_100000_jrc190301_m1_0219_1_1"]])),
      "the manifest row: path, size, expected and computed SHA-1, method, status, start, end, bytes per second")
rb = man[BY["20190105_090000_jrc190105_qa_1_1"]]
check(rb["expected_sha1"] == "0" * 40 and rb["computed_sha1"] != rb["expected_sha1"] and "differs" in rb["note"],
      "the mismatch is recorded with both digests")
check("tar members" in man[BY["20220127_141444_jrc220127_m153_post_0618_1_1"]]["note"],
      "crc+listing records the member count")
not_pulled = {BY[sp[1]] for sp in SPECS if sp[0] in ("D", "E", "X")}
check(not (set(opens(fk)) & {p for q in not_pulled for p in (q, q + ".sha1")}), "nothing of tiers D, E or X is opened")
check([c[0] for c in fk.calls[:2]] == ["listdir_attr", "listdir_attr"] and all(c[2] == "rb" for c in fk.calls if c[0] == "open"),
      "the run lists the folders once, then opens each file 'rb' only")

# -- resume -------------------------------------------------------------------------------------------------------
fk, a = new_arc(lambda: WED_EVE)
res = ma.fetch(a, pull, dest, now=lambda: WED_EVE, log=QUIET.append)
check(not fk.calls and res["verified"] == 0 and res["bad"] == 0, "a re-run skips the verified and keeps the bad: no remote call")
fk, a = new_arc(lambda: WED_EVE)
res = ma.fetch(a, pull, dest, now=lambda: WED_EVE, retry_bad=True, log=QUIET.append)
check(sorted(p for p in opens(fk) if not p.endswith(".sha1")) == sorted([BY["20190105_090000_jrc190105_qa_1_1"],
                                                                         BY["20220110_090000_jrc220110_x_1_1"]]),
      "--retry-bad fetches only the two bad archives again")

# -- stopping mid-file --------------------------------------------------------------------------------------------
clock = [WED_EVE]


def tick():
    clock[0] += dt.timedelta(minutes=1)


fk, a = new_arc(lambda: clock[0], on_read=tick)
dest3 = os.path.join(ftmp, "pull3")
res = ma.fetch(a, pull[:1], dest3, now=lambda: clock[0], stop_at=WED_EVE + dt.timedelta(minutes=3), margin_s=0,
               chunk=1024, log=QUIET.append)
cpath = BY["20190301_100000_jrc190301_m1_0219_1_1"]
cpart = os.path.join(dest3, "2019_pv6", cpath.split("/")[-1] + ".part")
check(res["stopped"] == 1 and "deadline" in res["stop_reason"] and os.path.isfile(cpart)
      and 0 < os.path.getsize(cpart) < len(FILES[cpath]) and not os.path.exists(cpart[:-5]),
      f"--stop-at reached mid-file: a clean stop, only a LOCAL .part ({os.path.getsize(cpart) if os.path.isfile(cpart) else '-'} bytes)")
check(manifest_of(dest3)[cpath]["status"] == "stopped" and all(x.closed for x in fk.opened),
      "the stop is recorded, and the remote file is closed")

arc_clock = [WED_EVE]


def flip():
    arc_clock[0] = THU_0800


fk, a = new_arc(lambda: arc_clock[0], on_read=flip)
dest4 = os.path.join(ftmp, "pull4")
a2 = [it for it in pull if it["tier"] == "A2"]
res = ma.fetch(a, a2, dest4, now=lambda: WED_EVE, chunk=1024, log=QUIET.append)
a2part = os.path.join(dest4, "2022_pv6", a2[0]["name"] + ".part")
check(res["stopped"] == 1 and "guard" in res["stop_reason"] and os.path.isfile(a2part)
      and os.path.getsize(a2part) == 1024 and not os.path.exists(a2part[:-5]),
      "the working-hours guard tripping mid-file stops cleanly, leaving only a LOCAL .part")
check(manifest_of(dest4)[a2[0]["path"]]["status"] == "stopped" and all(x.closed for x in fk.opened),
      "... recorded as stopped, the remote file closed")

fk, a = new_arc(lambda: WED_EVE)
res = ma.fetch(a, pull[:1], dest3, now=lambda: WED_EVE, log=QUIET.append)
check(res["verified"] == 1 and not os.path.exists(cpart)
      and io.open(cpart[:-5], "rb").read() == FILES[cpath], "a re-run restarts the stopped file and verifies it")

# -- nothing remote was written -------------------------------------------------------------------------------------
check(not any(c[0] == "DANGER" for fk_ in FAKES for c in fk_.calls), f"no forbidden remote call in any fetch test ({len(FAKES)} fakes)")
check(all(c[2] == "rb" for fk_ in FAKES for c in fk_.calls if c[0] == "open")
      and {c[0] for fk_ in FAKES for c in fk_.calls} <= {"listdir_attr", "open"},
      "the remote saw only folder listings and 'rb' opens")
check(all(p.startswith(("pull", "probe.bin", "pull_plan.csv")) for p in files_under(ftmp)),
      "everything fetch wrote is under its local --dest")

shutil.rmtree(ftmp, ignore_errors=True)
shutil.rmtree(tmp, ignore_errors=True)
print()
if FAILS:
    print(f"FAILED: {len(FAILS)} check(s)")
    sys.exit(1)
print("ALL CHECKS PASS")
