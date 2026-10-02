"""czi_compare.py -- is one .czi the same INFORMATION as another, even though its bytes differ?

Used by tools/retire_acquisition.py's `equivalent` disposition (retire tool v2, 2026-10-02; spec
06_REGISTRIES §2.9, 10_TOOLS §3.9). ZEN rewrites a .czi when, for example, display settings or metadata
are saved: the container changes (segments move, a DELETED segment is left behind, a new file GUID),
the information does not. The production case: ACQ-20250915-LSM9-016 is a compact re-save of -001.

Two files are CONTENT-EQUIVALENT when all three hold:
  * the metadata XML is identical (exact string equality);
  * the subblocks are identical as a multiset. A subblock is its pixel type, pyramid type, mosaic and
    scene index, dimensions, start, shape and stored shape; the SHA-256 of its DECODED pixels; its own
    metadata XML; and its attachments' payloads. Compression is NOT compared -- a lossless re-encode is
    the same information -- but it is recorded;
  * the top-level attachments are identical as a multiset of (name, content type, payload SHA-256).
    Attachment GUIDs are recorded, not compared (ZEN gives a re-saved Thumbnail a new GUID).
Everything else -- segment order and padding, DELETED segments, the file GUIDs -- is the container. It is
recorded as evidence and never compared.

Reads the whole file (every subblock is decoded). Needs `czifile` (+ `imagecodecs` for compressed
subblocks); imported lazily so nothing else in the toolset depends on them.
"""
import hashlib
import json
import os
from collections import Counter

METHOD = "czi-content/1"


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _enum(v):
    """A stable text form of a czifile enum or plain value."""
    name = getattr(v, "name", None)
    return name if name is not None else str(v)


def _tuple(v):
    return [x if isinstance(x, (int, float, str)) else _enum(x) for x in (v or ())]


def signature(path):
    """The content signature of a .czi (see the module docstring). Raises on an unreadable file.

    Returns a JSON-serialisable dict:
      metadata_xml_sha256, metadata_xml_chars
      subblocks      sorted list of [key, pixels_sha256, metadata_sha256, [attachment sha256s]]
      attachments    sorted list of [name, content type, payload sha256]
      container      {bytes, file_guid, primary_file_guid, file_part, update_pending, version,
                      segments: {type: count}, deleted_bytes, compression: {name: count},
                      attachment_guids: {name: guid}}
    """
    import czifile   # deferred: only the `equivalent` disposition needs it
    import numpy as np

    out = {"path": os.path.basename(path)}
    with czifile.CziFile(path) as czi:
        xml = czi.metadata() or ""
        out["metadata_xml_sha256"] = _sha(xml.encode("utf-8"))
        out["metadata_xml_chars"] = len(xml)

        subblocks, compression = [], Counter()
        for e in czi.subblock_directory:
            seg = e.read_segment_data(czi)
            if not hasattr(seg, "data") or type(seg).__name__ == "CziDeletedSegmentData":
                raise ValueError(f"{path}: a subblock directory entry points at a "
                                 f"{type(seg).__name__}, not a subblock")
            arr = np.ascontiguousarray(seg.data())
            pix = hashlib.sha256()
            pix.update(f"{arr.dtype.str}|{list(arr.shape)}|".encode())
            pix.update(arr.tobytes())
            meta = seg.metadata(fixesc=False) or ""
            atts = sorted(_sha(bytes(b)) for _guid, b in (seg.attachments() or ()))
            key = {"pixel_type": _enum(e.pixel_type), "pyramid_type": _enum(e.pyramid_type),
                   "mosaic_index": e.mosaic_index, "scene_index": e.scene_index,
                   "dims": _tuple(e.dims), "start": _tuple(e.start), "shape": _tuple(e.shape),
                   "stored_shape": _tuple(e.stored_shape)}
            subblocks.append([key, pix.hexdigest(), _sha(meta.encode("utf-8")), atts])
            compression[_enum(e.compression)] += 1
        out["subblocks"] = sorted(subblocks, key=lambda r: json.dumps(r, sort_keys=True))

        attachments, guids = [], {}
        for a in czi.attachment_directory:
            seg = a.read_segment_data(czi)
            if type(seg).__name__ == "CziDeletedSegmentData":
                raise ValueError(f"{path}: the attachment directory entry {a.name!r} points at a "
                                 f"DELETED segment")
            payload = bytes(seg.data(raw=True))
            attachments.append([str(a.name), _enum(a.content_file_type), _sha(payload)])
            guids[str(a.name)] = str(a.content_guid)
        out["attachments"] = sorted(attachments)

        segments, deleted = Counter(), 0
        for s in czi.segments():
            kind = type(s).__name__.replace("Czi", "").replace("SegmentData", "")
            segments[kind] += 1
            if kind == "Deleted":
                deleted += int(s.segment.allocated_size)
        h = czi.header
        out["container"] = {
            "bytes": os.path.getsize(path),
            "file_guid": str(getattr(h, "file_guid", "")),
            "primary_file_guid": str(getattr(h, "primary_file_guid", "")),
            "file_part": getattr(h, "file_part", None),
            "update_pending": bool(getattr(h, "update_pending", False)),
            "version": list(getattr(h, "version", ()) or ()),
            "segments": dict(sorted(segments.items())),
            "deleted_bytes": deleted,
            "compression": dict(sorted(compression.items())),
            "attachment_guids": guids,
        }
    return out


def _key_text(rec):
    k = rec[0]
    pos = ",".join(f"{d}={s}" for d, s in zip(k["dims"], k["start"]))
    return f"[{pos} shape {k['shape']} pyramid {k['pyramid_type']} m {k['mosaic_index']}]"


def compare(a, b):
    """Differences between two signatures, as readable strings. [] means content-equivalent."""
    diffs = []
    if a["metadata_xml_sha256"] != b["metadata_xml_sha256"]:
        diffs.append(f"metadata XML differs ({a['metadata_xml_chars']:,} vs {b['metadata_xml_chars']:,} chars)")

    def keyed(sig):
        d = {}
        for r in sig["subblocks"]:
            d.setdefault(json.dumps(r[0], sort_keys=True), []).append(r)
        return d
    ka, kb = keyed(a), keyed(b)
    if len(a["subblocks"]) != len(b["subblocks"]):
        diffs.append(f"subblock count differs ({len(a['subblocks'])} vs {len(b['subblocks'])})")
    layout = sorted(set(ka) ^ set(kb))
    if layout:
        example = (ka.get(layout[0]) or kb.get(layout[0]))[0]
        diffs.append(f"subblock layout differs: {len(layout)} position(s) in only one file, e.g. "
                     + _key_text(example))
    for k in sorted(set(ka) & set(kb)):
        ra, rb = ka[k], kb[k]
        if Counter(r[1] for r in ra) != Counter(r[1] for r in rb):
            diffs.append(f"decoded pixels differ at subblock {_key_text(ra[0])}")
        elif Counter(r[2] for r in ra) != Counter(r[2] for r in rb):
            diffs.append(f"subblock metadata differs at {_key_text(ra[0])}")
        elif Counter(json.dumps(r[3]) for r in ra) != Counter(json.dumps(r[3]) for r in rb):
            diffs.append(f"subblock attachments differ at {_key_text(ra[0])}")
    aa, ab = Counter(map(tuple, a["attachments"])), Counter(map(tuple, b["attachments"]))
    if aa != ab:
        only_a = sorted(f"{n} ({t})" for n, t, _s in (aa - ab).elements())
        only_b = sorted(f"{n} ({t})" for n, t, _s in (ab - aa).elements())
        diffs.append(f"attachments differ: only in the first {only_a or '-'}, only in the second {only_b or '-'}")
    return diffs


def subblocks_digest(sig):
    """One SHA-256 over the sorted subblock records (pixels, metadata, attachments, position)."""
    return _sha(json.dumps(sig["subblocks"], sort_keys=True, separators=(",", ":")).encode())


def evidence(retiree, survivor, retiree_sha256="", survivor_sha256=""):
    """The compact evidence object recorded in the tombstone for an `equivalent` retirement."""
    def side(sig, file_sha):
        c = sig["container"]
        return {"bytes": c["bytes"], "sha256": file_sha, "file_guid": c["file_guid"],
                "segments": c["segments"], "deleted_bytes": c["deleted_bytes"],
                "compression": c["compression"], "attachment_guids": c["attachment_guids"]}
    return {
        "method": METHOD,
        "identical": ["metadata_xml", "subblocks(decoded pixels, position, metadata, attachments)",
                      "attachments(name, type, payload)"],
        "metadata_xml_sha256": retiree["metadata_xml_sha256"],
        "metadata_xml_chars": retiree["metadata_xml_chars"],
        "subblocks": len(retiree["subblocks"]),
        "subblocks_digest": subblocks_digest(retiree),
        "attachments": [[n, t, s[:16]] for n, t, s in retiree["attachments"]],
        "retiree": side(retiree, retiree_sha256),
        "survivor": side(survivor, survivor_sha256),
    }
