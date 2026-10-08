#!/bin/bash
# Undo gjesus3_mount_setup.sh on the NI Mac: the MacMounter entry, the mount helper, every mount
# layer, the mount folder, the lock file and the saved password. Removes only what setup.sh made.
# Run BY RYAN in his ssh session:
#
#     bash /Volumes/gnuclear/2026/Jesus/Ryan/gjesus3-mount/undo.sh
set -u
MP="$HOME/.gjesus3"
CONF="$HOME/.macmounter/gjesus3.conf"
HELPER="$HOME/.macmounter/gjesus3-mount.py"

if [ -f "$CONF" ]; then      # first, so MacMounter stops re-mounting ("File ... is gone!")
    rm "$CONF" && echo "removed $CONF (MacMounter stops re-mounting within seconds)"
    sleep 3
fi
[ -f "$HELPER" ] && rm "$HELPER" && echo "removed $HELPER"
for _ in 1 2 3 4 5; do       # every stacked layer
    /sbin/mount | grep -q " on $MP (" || break
    /sbin/umount "$MP" && echo "unmounted a layer at $MP" || { echo "could not unmount $MP (in use?) -- run undo again"; break; }
done
[ -d "$MP" ] && rmdir "$MP" 2>/dev/null && echo "removed the empty folder $MP"
rm -f /tmp/gjesus3-mount.lock
echo "Removing the saved gjesus3 password (type the molecubes account's login password to unlock):"
security unlock-keychain "$HOME/Library/Keychains/login.keychain-db" \
    && security delete-internet-password -a rtasseff -s 10.10.1.73 >/dev/null 2>&1 \
    && echo "removed the saved gjesus3 password" \
    || echo "no saved gjesus3 password found (or the keychain did not unlock)"
