#!/bin/bash
# TEST-KIT launcher: the real launcher, but ALWAYS pointed at the pretend gjesus3 next to it
# (<kit>/nas3), whatever is mounted and whatever GJESUS3_ROOT says. Staged as <kit>/ni-ingest so
# a test types exactly what a researcher would, and cannot reach the real gjesus3.
here="$(cd "$(dirname "$0")" && pwd)"
echo "*** TEST KIT: writing only to the pretend gjesus3 at $here/nas3 ***" >&2
GJESUS3_ROOT="$here/nas3" exec bash "$here/tools/operator/ni-ingest.sh" "$@"
