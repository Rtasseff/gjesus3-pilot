#!/usr/bin/env python3
"""test_oslink.py — does os.link (hard link) work on THIS mounted gjesus3 share?

gjesus3 project linking uses hard links: a project's ``raw_linked/`` entry is a
real file sharing the raw primary's inode — zero extra storage, and it inherits
raw's read-only security descriptor. Hard links require the *destination*
filesystem to support them. On a Windows SMB mount this is confirmed working;
on a **Linux CIFS** mount (the MRI machine) or a **macOS SMB** mount (the
Mac-fronted NI machine) ``os.link`` can fail (``EPERM`` / ``EOPNOTSUPP``)
depending on the mount options and the negotiated SMB protocol version.

Run this ON each target machine, pointed at a scratch directory INSIDE the
mounted gjesus3 share (NOT a local disk), to find out BEFORE you ingest there.

Per-machine run instructions
----------------------------
  MRI (Linux):     mount the gjesus3 share, then
                     python3 tools/diagnostics/test_oslink.py /path/to/gjesus3/mount/scratch
  NI (via macOS):  if you can SSH into the Mac, run it there against the Mac's
                   mount of the share; otherwise run it locally on the Mac:
                     python3 tools/diagnostics/test_oslink.py /Volumes/gjesus3/scratch
  Windows (sanity): python tools\\diagnostics\\test_oslink.py J:\\gjesus3-sandbox\\scratch
                   (already known to PASS — use it to confirm the tool itself.)

What it checks (creates a temp file + a hard link in a private
``.oslink_test_<pid>/`` subdir, then cleans everything up):
  - os.link succeeds (else prints the errno + message),
  - the link shares the original's inode (st_ino/st_dev) and st_nlink == 2,
  - an edit through one path is visible through the other (both directions),
  - the link survives deleting the original,
and prints a single PASS/FAIL verdict.

If it FAILS — fallbacks (the executor cannot pick one for you; report the
output and choose per instrument):
  (a) Run ingest from a WINDOWS machine that mounts the share (hard links are
      confirmed working there) and reach the instrument data remotely. Preferred
      — the Windows hard-link path is proven.
  (b) SFTP-stage the source from the Linux/Mac machine to where a Windows ingest
      runs (tools/ftp_mirror.py already does SFTP mirroring), then ingest there.
  (c) NAS-side ``cp --reflink`` (zero-copy) if the NAS volume is ZFS/btrfs —
      verify the filesystem type first.
  (d) Fall back to the legacy ``.lnk`` shortcut path (linker.create_lnk still
      exists) — shortcuts instead of real-file links; lower adoption value but
      functional cross-platform.

Dependency-free (stdlib only). Non-destructive: only touches files it creates.
"""

import errno
import os
import sys


def _check(target):
    """Run the hard-link checks under `target`. Returns (results, ok)."""
    workdir = os.path.join(target, f".oslink_test_{os.getpid()}")
    orig = os.path.join(workdir, "original.txt")
    link = os.path.join(workdir, "hardlink.txt")
    results = []           # (label, ok, detail)
    ok = True
    os.makedirs(workdir, exist_ok=True)
    try:
        with open(orig, "w", encoding="utf-8") as f:
            f.write("gjesus3 os.link test payload\n")

        # 1. os.link itself
        try:
            os.link(orig, link)
            results.append(("os.link created a hard link", True, ""))
        except OSError as e:
            name = errno.errorcode.get(e.errno, str(e.errno))
            results.append(("os.link", False, f"OSError {name}: {e.strerror}"))
            return results, False  # nothing else to test

        # 2. shared inode (the reliable SMB-safe signal) + link count (info only)
        so, sl = os.stat(orig), os.stat(link)
        same = (so.st_ino == sl.st_ino and so.st_dev == sl.st_dev and so.st_ino != 0)
        results.append((f"shared inode (st_ino {so.st_ino} / st_dev {so.st_dev})", same, ""))
        # st_nlink is INFORMATIONAL: many SMB redirectors report 1 even for a
        # working hard link, so it must not drive the verdict.
        results.append((
            f"st_nlink = {so.st_nlink} (often 1 over SMB even when hard links "
            f"work; not used for the verdict)", None, ""))
        ok = ok and same

        # 3. edit propagation, both directions
        with open(orig, "a", encoding="utf-8") as f:
            f.write("edit-via-original\n")
        prop1 = "edit-via-original" in open(link, encoding="utf-8").read()
        with open(link, "a", encoding="utf-8") as f:
            f.write("edit-via-link\n")
        prop2 = "edit-via-link" in open(orig, encoding="utf-8").read()
        results.append(("edit via original is visible via the link", prop1, ""))
        results.append(("edit via link is visible via the original", prop2, ""))
        ok = ok and prop1 and prop2

        # 4. survives deleting the original
        os.remove(orig)
        survives = os.path.exists(link) and "edit-via-link" in open(link, encoding="utf-8").read()
        results.append(("link survives deleting the original", survives, ""))
        ok = ok and survives
        return results, ok
    finally:
        for p in (orig, link):
            try:
                os.remove(p)
            except OSError:
                pass
        try:
            os.rmdir(workdir)
        except OSError:
            pass


_FALLBACKS = (
    "         (a) run ingest from a Windows machine that mounts the share (hard\n"
    "             links are proven there) and reach the data remotely;\n"
    "         (b) SFTP-stage the source to that Windows machine (tools/ftp_mirror.py)\n"
    "             and ingest there;\n"
    "         (c) NAS-side `cp --reflink` if the volume is ZFS/btrfs;\n"
    "         (d) fall back to the legacy .lnk shortcut path (linker.create_lnk).\n"
    "         Report the FAIL lines above; choose per instrument (do not guess)."
)


def main(argv):
    if len(argv) != 2 or argv[1] in ("-h", "--help"):
        print("usage: python3 test_oslink.py <scratch-dir-on-the-mounted-gjesus3-share>")
        print(__doc__)
        return 2
    target = argv[1]
    if not os.path.isdir(target):
        print(f"FAIL: not a directory (mount the share first?): {target}")
        return 2

    try:
        results, ok = _check(target)
    except OSError as e:
        print(f"FAIL: could not run the test under {target}: {e}")
        return 2

    print(f"\nos.link diagnostic on: {target}")
    print(f"python {sys.version.split()[0]}  |  platform {sys.platform}\n")
    for label, passed, detail in results:
        tag = "info" if passed is None else ("PASS" if passed else "FAIL")
        line = f"  [{tag}] {label}"
        if detail:
            line += f"  -> {detail}"
        print(line)
    print()
    if ok and results:
        print("VERDICT: PASS — hard links work here. Ingest can run on this machine;")
        print("         project raw_linked/ entries will be real shared-inode files.")
        return 0
    print("VERDICT: FAIL — hard links do NOT work on this mount. Options:")
    print(_FALLBACKS)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
