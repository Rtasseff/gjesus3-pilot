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

    def read(self, size=None):
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

    def __init__(self, tree=None):
        self.calls = []
        self.tree = tree or {}

    def listdir_attr(self, p):
        self.calls.append(("listdir_attr", p))
        return self.tree.get(p, [])

    def stat(self, p):
        self.calls.append(("stat", p))
        return Attr(p.rsplit("/", 1)[-1], stat.S_IFREG | 0o644, 5)

    def open(self, p, mode="r"):
        self.calls.append(("open", p, mode))
        return FakeRemoteFile(b"hello")

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

shutil.rmtree(tmp, ignore_errors=True)
print()
if FAILS:
    print(f"FAILED: {len(FAILS)} check(s)")
    sys.exit(1)
print("ALL CHECKS PASS")
