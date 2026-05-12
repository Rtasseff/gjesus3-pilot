"""Read-only probe of a Zeiss .czi file's embedded metadata.

Standalone utility — not part of the ingest pipeline. Intended to be run
once per representative sample to inform the follow-up extraction work
(09_MODALITIES §1.1 / 4.6.A) by dumping every embedded XML element to a
JSON snapshot reviewers can grep.

Usage:
    python -m ingest.probe_czi <path-to.czi> [--out _probes/<basename>.json]

Reads metadata only — does not load image pixel data, does not write to
the source.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from xml.etree import ElementTree as ET


def _xml_to_dict(elem):
    """Recursive Element -> nested dict. Preserves attributes and text."""
    node = {}
    if elem.attrib:
        node["@attrs"] = dict(elem.attrib)
    text = (elem.text or "").strip()
    if text:
        node["#text"] = text
    children = list(elem)
    if children:
        for child in children:
            tag = child.tag
            sub = _xml_to_dict(child)
            existing = node.get(tag)
            if existing is None:
                node[tag] = sub
            elif isinstance(existing, list):
                existing.append(sub)
            else:
                node[tag] = [existing, sub]
    return node


def probe(czi_path):
    """Open a .czi file and return its embedded metadata as a JSON-able dict.

    Requires the `czifile` package. Returns dict with:
        path, file_size_mb, probed_at, xml_root_tag, xml_dict, raw_xml_excerpt.
    """
    try:
        import czifile  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "czifile is not installed. Run: pip install czifile"
        ) from e

    size_mb = round(os.path.getsize(czi_path) / 1_000_000, 2)
    with czifile.CziFile(czi_path) as czi:
        meta_xml = czi.metadata()  # str (XML) on modern czifile

    if isinstance(meta_xml, bytes):
        meta_xml = meta_xml.decode("utf-8", errors="replace")

    root = ET.fromstring(meta_xml)
    return {
        "path": os.path.abspath(czi_path),
        "file_size_mb": size_mb,
        "probed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "xml_root_tag": root.tag,
        "xml_dict": _xml_to_dict(root),
        "raw_xml_excerpt": meta_xml[:4000],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("czi_path", help="Path to a .czi file to probe (read-only)")
    p.add_argument(
        "--out",
        default=None,
        help="Output JSON file (default: _probes/<basename>.json relative to cwd)",
    )
    args = p.parse_args(argv)

    if not os.path.isfile(args.czi_path):
        print(f"ERROR: file not found: {args.czi_path}", file=sys.stderr)
        return 2

    out_path = args.out
    if out_path is None:
        os.makedirs("_probes", exist_ok=True)
        base = os.path.splitext(os.path.basename(args.czi_path))[0]
        out_path = os.path.join("_probes", f"{base}.json")

    try:
        result = probe(args.czi_path)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3

    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote {out_path} ({result['file_size_mb']} MB source)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
