#!/bin/bash
# Keep gjesus3 mounted on the NI Mac with the Data Office login -- INTERIM, until Box A
# (Ryan, 2026-10-08). Run BY RYAN, in his own ssh session on the Mac:
#
#     bash /Volumes/gnuclear/2026/Jesus/Ryan/gjesus3-mount/setup.sh
#
# What it writes on the Mac, and nothing else:
#   1. one item in the molecubes login keychain: account rtasseff, server 10.10.1.73 (SMB)
#   2. the empty folder ~/.gjesus3 (the mount point; hidden from Finder)
#   3. ~/.macmounter/gjesus3-mount.py (the mount helper) and ~/.macmounter/gjesus3.conf (the
#      MacMounter entry), both copied from next to this script, so MacMounter re-mounts gjesus3
#      whenever it drops. The helper locks /tmp/gjesus3-mount.lock while it mounts.
# It asks for two passwords: the molecubes account's (to unlock the keychain over ssh) and
# yours for gjesus3 (saved in that keychain, never printed, never written to a file). Safe to
# run again: it always asks for the gjesus3 password afresh and replaces the saved one, so a
# mistyped password never sticks.
# Every step is checked; on any failure it stops and changes nothing further.
# Undo everything: bash /Volumes/gnuclear/2026/Jesus/Ryan/gjesus3-mount/undo.sh
set -u
here="$(cd "$(dirname "$0")" && pwd)"
NAS_USER=rtasseff
HOST=10.10.1.73
MP="$HOME/.gjesus3"
CONF="$HOME/.macmounter/gjesus3.conf"
HELPER="$HOME/.macmounter/gjesus3-mount.py"

stop() {
    echo
    echo "STOPPED: $*"
    echo "Nothing after this step was done. Send this output to the data office."
    exit 1
}

echo "1/5  Unlock the keychain for this ssh session (type the molecubes account's login password)."
security unlock-keychain "$HOME/Library/Keychains/login.keychain-db" || stop "the keychain did not unlock"

echo "2/5  Save the gjesus3 password for '$NAS_USER' (type YOUR gjesus3 password, twice; it is not shown)."
security delete-internet-password -a "$NAS_USER" -s "$HOST" >/dev/null 2>&1   # replace, never keep a typo
security add-internet-password -a "$NAS_USER" -s "$HOST" -r "smb " \
    -l "gjesus3 (Data Office, NI sync)" -T /usr/bin/security -T /sbin/mount_smbfs -w \
    || stop "could not save the password"

echo "3/5  Create the mount folder $MP"
mkdir -p "$MP" || stop "could not create $MP"

echo "4/5  Install the mount helper, then test-mount gjesus3 with exactly the command MacMounter will use"
# The helper goes in BEFORE the entry: MacMounter re-reads ~/.macmounter when a file is added,
# and must find the helper already there when the entry appears in step 5.
if ! cmp -s "$here/gjesus3-mount.py" "$HELPER"; then
    cp "$here/gjesus3-mount.py" "$HELPER" || stop "could not install $HELPER"
fi
if [ -d "$MP/gjesus3-data/registries" ]; then
    echo "     already mounted"
else
    mount_cmd="$(sed -n 's/^MOUNT_CMD=//p' "$here/gjesus3.conf")"
    [ -n "$mount_cmd" ] || stop "no MOUNT_CMD in $here/gjesus3.conf"
    if ! out="$(/bin/sh -c "$mount_cmd" 2>&1)"; then
        echo "     $out"
        case "$out" in
            *uthentication*) stop "gjesus3 rejected the password -- most likely a typo. Run setup.sh again; it asks again." ;;
            *) stop "the mount failed (see the line above)" ;;
        esac
    fi
fi
test -d "$MP/gjesus3-data/registries" || stop "mounted, but $MP/gjesus3-data/registries is not visible"
echo "     OK: gjesus3 is mounted at $MP (hidden from Finder)"

echo "5/5  Hand it to MacMounter, which re-mounts it whenever it drops"
if [ -f "$CONF" ] && cmp -s "$here/gjesus3.conf" "$CONF"; then
    echo "     already installed"
else
    # Never overwrite the entry in place: MacMounter would start a SECOND thread for it in each
    # of its copies (it relaunches any .conf newer than its last look). Removing it stops the
    # old threads ("File ... is gone!"); the fresh copy then starts exactly one per copy.
    if [ -f "$CONF" ]; then
        rm "$CONF" && sleep 5
    fi
    cp "$here/gjesus3.conf" "$CONF" || stop "could not install $CONF"
    echo "     installed $CONF"
fi

echo
echo "Done. To check at any time:  test -d ~/.gjesus3/gjesus3-data/registries && echo mounted"
