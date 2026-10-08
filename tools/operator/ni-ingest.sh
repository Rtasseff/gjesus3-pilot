#!/bin/bash
# ni-ingest -- sync your nuclear-imaging data to gjesus3 from the Molecubes Mac.
# What to type: NI_LIVE_RUNBOOK.md. Every option: ni-ingest --help
#
# Runs the copy of tools/ staged next to this file on gnuclear, so nothing has to
# be installed on the Mac. It uses the Mac's Python 3.10 (a remote shell finds
# the older system 3.8 first) and writes no __pycache__ next to the code.
# The NAS root is $GJESUS3_ROOT if set; else the Data Office mount kept up by MacMounter
# (~/.gjesus3, ni_mac/gjesus3_mount_setup.sh); else gjesus3 as mounted in Finder.
here="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$here/ni_ingest.py" ]; then        # still inside tools/operator/
    tools="$(cd "$here/.." && pwd)"
else                                         # staged: <dir>/ni-ingest + <dir>/tools/
    tools="$here/tools"
fi
py=/usr/local/bin/python3
[ -x "$py" ] || py=python3
export PYTHONPATH="$tools"
export PYTHONDONTWRITEBYTECODE=1
if [ -z "${GJESUS3_ROOT:-}" ]; then
    if [ -d "$HOME/.gjesus3/gjesus3-data/registries" ]; then
        GJESUS3_ROOT="$HOME/.gjesus3/gjesus3-data"
    else
        GJESUS3_ROOT=/Volumes/gjesus3/gjesus3-data
    fi
fi
export GJESUS3_ROOT
exec "$py" "$tools/operator/ni_ingest.py" "$@"
