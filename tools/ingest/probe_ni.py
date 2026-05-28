"""Read-only probe of a Molecubes NI acquisition folder's metadata.

Standalone utility — not part of the ingest pipeline. Intended to be
run once per representative sample to verify the `ni_metadata.py`
extractor populates correctly before a real ingest.

Usage:
    python -m ingest.probe_ni <path-to-acquisition-folder> [--out _probes/<basename>.json]

Reads metadata only — does not load `data.raw`, does not modify the
source.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import ni_metadata


def probe(folder_path):
    """Walk an NI acquisition folder; return a JSON-able snapshot.

    The snapshot is the complete `ni_metadata` parse result — parsed
    bundle, structured `ni:` block, curated `discovered.ni_*` subset.
    Useful for diff-ing before/after extractor changes and for
    pre-ingest sanity check.
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        raise RuntimeError(f"Not a directory: {folder_path}")
    if not ni_metadata.is_ni_acquisition(folder):
        raise RuntimeError(
            f"Folder does not look like a Molecubes NI acquisition "
            f"(needs protocol.txt + at least one recon_<idx>/): {folder_path}"
        )
    md = ni_metadata.load_ni_acquisition(folder)
    discovered = ni_metadata.build_discovered_subset(md)
    section = ni_metadata.build_ni_section(md)
    return {
        "path": str(folder),
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "discovered_ni_*": discovered,
        "ni_section": section,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("folder", help="Path to one extracted NI acquisition folder")
    p.add_argument(
        "--out", default=None,
        help="Output JSON file path (default: _probes/<basename>.json)",
    )
    args = p.parse_args()

    try:
        snap = probe(args.folder)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.out:
        out_path = args.out
    else:
        out_dir = os.path.join(os.getcwd(), "_probes")
        os.makedirs(out_dir, exist_ok=True)
        basename = Path(args.folder).name or "probe"
        out_path = os.path.join(out_dir, f"{basename}.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=2, ensure_ascii=False, default=str)
    print(f"Wrote {out_path}")
    print(f"  discovered.ni_* fields populated: "
          f"{sum(1 for v in snap['discovered_ni_*'].values() if v)} / "
          f"{len(snap['discovered_ni_*'])}")
    print(f"  recons present: {snap['ni_section']['reconstruction']['recons_present']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
