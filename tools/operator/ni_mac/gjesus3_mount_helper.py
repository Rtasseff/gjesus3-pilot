#!/usr/local/bin/python3
"""Mount gjesus3 at ~/.gjesus3 for the NI sync. Installed as ~/.macmounter/gjesus3-mount.py and
run by MacMounter through ~/.macmounter/gjesus3.conf (Data Office, 2026-10-08; INTERIM until Box A).

Three MacMounter copies run on this Mac and all read the same entry. Without a lock, two of them
noticed the same drop and both mounted, stacking two mounts on one folder (seen 2026-10-08). So
the work is serialized: an exclusive lock, released by the OS when this process exits (no stale
lock is possible), then a re-check. The first copy mounts; the others find it mounted and stop.

Also clears dead layers (listed in `mount` but unreachable) before mounting. The password comes
from the login keychain and is URL-encoded into the smb URL; it is never written anywhere.
"""
import fcntl
import os
import subprocess
import sys
import time
import urllib.parse

MP = "/Users/molecubes/.gjesus3"
REG = os.path.join(MP, "gjesus3-data", "registries")
LOCK = "/tmp/gjesus3-mount.lock"
USER, HOST, SHARE = "rtasseff", "10.10.1.73", "gjesus3"


def listed():
    out = subprocess.run(["/sbin/mount"], capture_output=True, text=True).stdout
    return f" on {MP} (" in out


def main():
    with open(LOCK, "w") as lk:
        for _ in range(60):                       # wait up to ~60 s for our turn
            try:
                fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(1)
        else:
            return "another copy is still mounting; leaving it to that one"
        if os.path.isdir(REG):
            return 0                              # already mounted (by another copy)
        for _ in range(5):                        # clear dead layers, top first
            if not listed():
                break
            subprocess.run(["/sbin/umount", "-f", MP])
        os.makedirs(MP, exist_ok=True)
        pw = subprocess.run(["/usr/bin/security", "find-internet-password",
                             "-a", USER, "-s", HOST, "-w"], capture_output=True, text=True)
        if pw.returncode != 0:
            return "no saved gjesus3 password in the login keychain"
        url = "//%s:%s@%s/%s" % (USER, urllib.parse.quote(pw.stdout.rstrip("\n"), safe=""),
                                 HOST, SHARE)
        return subprocess.run(["/sbin/mount_smbfs", "-N", "-o", "nobrowse", url, MP]).returncode


if __name__ == "__main__":
    sys.exit(main())
