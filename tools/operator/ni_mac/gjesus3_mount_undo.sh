#!/bin/bash
# Undo gjesus3_mount_setup.sh on the NI Mac: the MacMounter entry, the mount, the mount folder
# and the saved password. Removes only what setup.sh made. Run BY RYAN in his ssh session:
#
#     bash /Volumes/gnuclear/2026/Jesus/Ryan/gjesus3-mount/undo.sh
set -u
MP="$HOME/.gjesus3"
CONF="$HOME/.macmounter/gjesus3.conf"

if [ -f "$CONF" ]; then
    rm "$CONF" && echo "removed $CONF (MacMounter stops re-mounting within seconds)"
    sleep 3
fi
if /sbin/mount | grep -q " on $MP ("; then
    /sbin/umount "$MP" && echo "unmounted $MP" || echo "could not unmount $MP (in use?) -- run undo again"
fi
[ -d "$MP" ] && rmdir "$MP" 2>/dev/null && echo "removed the empty folder $MP"
echo "Removing the saved gjesus3 password (type the molecubes account's login password to unlock):"
security unlock-keychain "$HOME/Library/Keychains/login.keychain-db" \
    && security delete-internet-password -a rtasseff -s 10.10.1.73 >/dev/null 2>&1 \
    && echo "removed the saved gjesus3 password" \
    || echo "no saved gjesus3 password found (or the keychain did not unlock)"
