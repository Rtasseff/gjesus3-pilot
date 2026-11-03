"""Tests for the content-anchored dedup key (issue #5; design: tasks/dedup_key_design.md).

A case is already ingested when ANY of its keys (ingest.config.dedupe_keys_for) is in the index built from
every live and retired registry row. The original (date, original_name) key stays; a MICROSCOPY .czi also
gets ("czi", instrument, acquisition timestamp to the second, file name). Pinned here, on real (synthetic)
.czi files that czifile parses, in a fake NAS in a temp dir:

  1. the same .czi from a second staging root is skipped (the 22 ZWSI twins of 2026-09-29);
  2. a ZEN re-save (same instrument, timestamp and name; other bytes) is skipped (the 206 of 2026-09-30);
  3. a scene split (same timestamp, another name) is NOT skipped;
  4. a retired row's key still blocks (06 §2.9.2);
  5. the original key alone still works (a folder-dated row has no content key);
  6. a .czi whose device serial names another instrument than the template still meets its twin;
  7. the skip is counted: preview, run_batch(stats=), and the GUI ingest result (Flask test client).

Run: python tools/test_dedup_key.py
"""
import contextlib
import csv
import importlib.util
import io
import json
import os
import struct
import sys
import tempfile
import uuid

import numpy as np

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import ingest_raw  # noqa: E402
from ingest import config as cfg_mod, registry, retired  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


# ---- a minimal CZI writer, copied from tools/test_retire_acquisition_v2.py (that module runs on import) ----

def _seg(sid, data):
    alloc = (len(data) + 31) // 32 * 32
    return sid.encode().ljust(16, b"\0") + struct.pack("<qq", alloc, len(data)) + data + bytes(alloc - len(data))


def _dir_entry(file_pos, c, shape):
    out = b"DV" + struct.pack("<iqiiB5si", 1, file_pos, 0, 0, 0, bytes(5), 3)     # Gray16, uncompressed
    for name, start, size in (("X", 0, shape[1]), ("Y", 0, shape[0]), ("C", c, 1)):
        out += name.encode().ljust(4, b"\0") + struct.pack("<iifi", start, size, 0.0, size)
    return out


def _att_entry(file_pos, guid, ctype, name):
    return (b"A1" + bytes(10) + struct.pack("<qi", file_pos, 0) + guid.bytes
            + ctype.encode().ljust(8, b"\0") + name.encode().ljust(80, b"\0"))


def write_czi(path, xml, planes, attachments, deleted=0, metadata_last=False, order=None, file_guid=None):
    """planes: [2-D uint16 array per channel]; attachments: [(name, type, payload, guid)].
    deleted / metadata_last / order / file_guid vary the CONTAINER only (a ZEN-style re-save)."""
    n_sb, n_att = len(planes), len(attachments)
    pos = 32 + 512
    sbdir_pos = pos
    pos += 32 + (128 + n_sb * (32 + 60) + 31) // 32 * 32
    attdir_pos = pos
    pos += 32 + (256 + n_att * 128 + 31) // 32 * 32
    chunks = ([("deleted", None)] if deleted else []) + ([] if metadata_last else [("meta", None)])
    chunks += [("sb", i) for i in (order or range(n_sb))] + [("att", j) for j in range(n_att)]
    chunks += [("meta", None)] if metadata_last else []
    built, sb_entries, att_entries, meta_pos = [], {}, {}, None
    for kind, i in chunks:
        if kind == "deleted":
            seg = _seg("DELETED", b"\xab" * deleted)
        elif kind == "meta":
            meta_pos = pos
            seg = _seg("ZISRAWMETADATA", struct.pack("<ii", len(xml), 0) + bytes(248) + xml)
        elif kind == "sb":
            data = np.ascontiguousarray(planes[i], dtype="<u2").tobytes()
            entry = _dir_entry(pos, i, planes[i].shape)
            fixed = struct.pack("<iiq", 0, 0, len(data)) + entry
            seg = _seg("ZISRAWSUBBLOCK", fixed + bytes(max(256, len(fixed)) - len(fixed)) + data)
            sb_entries[i] = entry
        else:
            name, ctype, payload, guid = attachments[i]
            entry = _att_entry(pos, guid, ctype, name)
            seg = _seg("ZISRAWATTACH", struct.pack("<i", len(payload)) + bytes(12) + entry + bytes(112) + payload)
            att_entries[i] = entry
        built.append(seg)
        pos += len(seg)
    fg = file_guid or uuid.uuid4()
    hdr = struct.pack("<iiii", 1, 0, 0, 0) + fg.bytes + fg.bytes + struct.pack("<iqqiq", 0, sbdir_pos, meta_pos, 0,
                                                                            attdir_pos)
    out = (_seg("ZISRAWFILE", hdr + bytes(512 - len(hdr)))
           + _seg("ZISRAWDIRECTORY", struct.pack("<i", n_sb) + bytes(124) + b"".join(sb_entries[i] for i in range(n_sb)))
           + _seg("ZISRAWATTDIR", struct.pack("<i", n_att) + bytes(252) + b"".join(att_entries[j] for j in range(n_att)))
           + b"".join(built))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(out)
    return out


# ---- fixtures --------------------------------------------------------------------------------------

ZWSI_SERIAL = "4661000718"       # tools/reference/microscopy_instruments.yaml
TS = "2026-03-04T10:23:45.1234567Z"
RNG = np.random.default_rng(5)
PLANE = RNG.integers(0, 4000, (6, 8)).astype(np.uint16)
ATTS = [("Thumbnail", "JPG", b"jpg-bytes" * 20, uuid.UUID("49ff63e5-692f-7643-bfb9-068a289f5c83"))]


def czi_xml(ts=TS, serial=ZWSI_SERIAL, size_x=8):
    """What czi_metadata reads: Information/Image/AcquisitionDateAndTime (the timestamp) and the device
    serial under Metadata/HardwareSetting (the instrument fingerprint)."""
    hw = (f'<HardwareSetting><Devices><Device Id="Stand" SerialNumber="{serial}"/></Devices></HardwareSetting>'
          if serial else "")
    return (f'<?xml version="1.0" encoding="utf-8"?><ImageDocument><Metadata>{hw}<Information>'
            f'<Instrument><Microscopes><Microscope Name="Axioscan 7"><Type>Upright</Type></Microscope>'
            f'</Microscopes></Instrument><Image><AcquisitionDateAndTime>{ts}</AcquisitionDateAndTime>'
            f'<SizeX>{size_x}</SizeX></Image></Information></Metadata></ImageDocument>').encode()


def make_nas(root):
    nas = os.path.join(root, "nas")
    os.makedirs(os.path.join(nas, "registries"), exist_ok=True)
    with open(os.path.join(nas, "registries", "registry_raw.csv"), "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(registry.REGISTRY_FIELDS)
    return nas


def batch_cfg(staging, pattern, instrument="ZWSI", adt="discovered.czi_acquisition_datetime"):
    return {
        "ingest": {"auto_create_projects": False},
        "auto_discover": {"staging_dir": staging, "pattern": pattern},
        "registry": {"instrument": instrument, "data_ecosystem": "MICROSCOPY",
                     "researcher": "tester", "data_source": "internal",
                     "acquisition_datetime": adt},
    }


def expand(cfg, nas):
    """(cases, stdout, already-list) of one expand_batch run against the fake NAS."""
    buf, already = io.StringIO(), []
    with contextlib.redirect_stdout(buf):
        try:
            cases = cfg_mod.expand_batch(cfg, nas_root=nas, already=already)
        except ValueError as e:
            print(f"ValueError: {e}")
            cases = []
    return cases, buf.getvalue(), already


def register(nas, case, acq_id):
    """Append the registry row ingest_single would write for `case` (only the fields the key reads matter)."""
    r = {f: "" for f in registry.REGISTRY_FIELDS}
    r.update({k: case.get(k, "") for k in ("acquisition_datetime", "data_ecosystem", "instrument",
                                           "researcher", "data_source", "original_name")})
    r.update(acq_id=acq_id, registration_datetime="2026-10-17T10:00:00Z", primary_kind="file",
             primary_file_name=f"{acq_id}.czi", file_format=".czi", file_count="1",
             canonical_path=f"/raw/MICROSCOPY/2026/2026-03/{acq_id}/")
    registry.append_row(os.path.join(nas, "registries", "registry_raw.csv"), r)
    return r


def retire_all(nas):
    """Move every live row into the tombstone file, verbatim (what retire_acquisition does)."""
    reg = os.path.join(nas, "registries", "registry_raw.csv")
    rows = registry.read_registry(reg)
    with open(retired.retired_path(os.path.join(nas, "registries")), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=retired.RETIRED_FIELDS)
        w.writeheader()
        for r in rows:
            line = io.StringIO()
            csv.writer(line).writerow([r.get(k, "") for k in registry.REGISTRY_FIELDS])
            w.writerow({"acq_id": r["acq_id"], "retired_at": "2026-10-17T10:00:00Z", "disposition": "duplicate",
                        "superseded_by": "ACQ-20260304-ZWSI-001", "reason": "test", "bytes_fate": "deleted",
                        "registry_raw_row": line.getvalue().strip("\r\n")})
    with open(reg, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(registry.REGISTRY_FIELDS)


def main():
    with tempfile.TemporaryDirectory() as td:
        nas = make_nas(td)
        a = os.path.join(td, "stagingA")          # the bulk layout: <date>/<file>
        b = os.path.join(td, "stagingB")          # the operator recipe: the date folder itself
        name = "MFB_AUA_1123_ID12_PR_10x.czi"
        write_czi(os.path.join(a, "20260304", name), czi_xml(), [PLANE], ATTS)
        write_czi(os.path.join(b, name), czi_xml(), [PLANE], ATTS)
        with open(os.path.join(a, "20260304", name), "rb") as f1, open(os.path.join(b, name), "rb") as f2:
            same_bytes = f1.read()[600:] == f2.read()[600:]      # past the per-file GUID header

        print("0. the keys themselves")
        cases, out, _ = expand(batch_cfg(a, "[0-9]*/*.czi"), nas)
        check(len(cases) == 1, f"empty registry: the bulk layout yields 1 case ({out.strip()[-200:]})")
        if not cases:
            raise SystemExit(1)
        keys = cfg_mod.dedupe_keys_for(cases[0])
        check(("20260304", f"20260304/{name}") in keys, "the original (date, original_name) key is kept")
        check(("czi", "ZWSI", "2026-03-04T10:23:45", name.lower()) in keys,
              "the content key: instrument, timestamp to the second, file name lower-cased")
        row = {"original_name": "x/IMG.CZI", "acquisition_datetime": TS, "data_ecosystem": "MICROSCOPY",
               "instrument": "LSM9"}
        check(("czi", "LSM9", "2026-03-04T10:23:45", "img.czi") in cfg_mod.dedupe_keys_for(row),
              "a registry row keys its own instrument code; the name is case-insensitive")
        check(len(cfg_mod.dedupe_keys_for(dict(row, data_ecosystem="DICOM"))) == 1, "non-microscopy: old key only")
        check(len(cfg_mod.dedupe_keys_for(dict(row, original_name="x/img.tif"))) == 1, ".tif: old key only")
        check(len(cfg_mod.dedupe_keys_for(dict(row, acquisition_datetime="2026-03-04T00:00:00Z"))) == 1,
              "a folder-dated row (00:00:00) makes no content key")
        check(cfg_mod.dedupe_keys_for(dict(row, original_name="")) == set(), "blank original_name: no key")

        register(nas, cases[0], "ACQ-20260304-ZWSI-001")

        print("1. the same .czi from a second staging root")
        cases, out, already = expand(batch_cfg(b, "*.czi"), nas)
        check(same_bytes, "fixture: the two copies carry the same image bytes")
        check(cases == [], f"skipped: 0 new cases (got {len(cases)})")
        check(f"SKIP {name}: already in registry (same acquisition: ZWSI, .czi timestamp "
              f"2026-03-04T10:23:45, file name {name.lower()})" in out, "the content-key SKIP line")
        check(already == [name], f"counted once in `already` (got {already})")
        prev = _load_preview()
        n_already, dropped = prev._categorize_skips(out.splitlines())
        check(n_already == 1 and not dropped, "the preview counts it as already ingested, not dropped")

        print("2. a ZEN re-save: same instrument, timestamp and name; other bytes")
        c = os.path.join(td, "stagingC")
        write_czi(os.path.join(c, name), czi_xml(), [PLANE], ATTS, deleted=4096, metadata_last=True)
        with open(os.path.join(c, name), "rb") as f1, open(os.path.join(b, name), "rb") as f2:
            check(f1.read() != f2.read(), "fixture: the re-save's bytes differ")
        cases, out, already = expand(batch_cfg(c, "*.czi"), nas)
        check(cases == [] and "same acquisition: ZWSI" in out, "the re-save is skipped")

        print("3. a scene split: same timestamp, another name")
        d = os.path.join(td, "stagingD")
        write_czi(os.path.join(d, "MFB_AUA_1123_ID12_PR_10x-Scene-2.czi"), czi_xml(size_x=4),
                  [PLANE[:, :4]], ATTS)
        cases, out, already = expand(batch_cfg(d, "*.czi"), nas)
        check(len(cases) == 1 and not already, "NOT skipped: a different name is a different file")

        print("6. the device serial names the instrument the template got wrong")
        cases, out, _ = expand(batch_cfg(b, "*.czi", instrument="CELL"), nas)
        check(cases == [] and "same acquisition: ZWSI" in out,
              "an AxioScan file run through the CELL template meets its ZWSI twin")

        print("7. the skip count reaches run_batch and the GUI result")
        stats = {}
        with contextlib.redirect_stdout(io.StringIO()) as so:
            results = ingest_raw.run_batch(batch_cfg(b, "*.czi"), nas, dry_run=True, stats=stats)
        check(results == [] and stats.get("n_already_ingested") == 1,
              f"run_batch(stats=) reports n_already_ingested=1 (got {stats})")
        check("Already ingested (not copied again): 1" in so.getvalue(), "the BATCH SUMMARY says so")
        pr = prev.preview_batch(batch_cfg(b, "*.czi"), nas)
        check(pr.n_already_ingested == 1 and pr.n_new == 0, "preview_batch: 1 already ingested, 0 new")
        gui_check(nas, batch_cfg(b, "*.czi"))

        print("4. a retired row's key still blocks")
        retire_all(nas)
        check(not registry.read_registry(os.path.join(nas, "registries", "registry_raw.csv")),
              "fixture: the live registry is empty")
        cases, out, _ = expand(batch_cfg(b, "*.czi"), nas)
        check(cases == [] and "same acquisition: ZWSI" in out, "the content key of a tombstone blocks")
        cases, out, _ = expand(batch_cfg(a, "[0-9]*/*.czi"), nas)
        check(cases == [] and "already in registry (idempotent re-run)" in out,
              "the original key of a tombstone blocks, with the unchanged wording")

    print("5. the original key alone (a folder-dated batch)")
    with tempfile.TemporaryDirectory() as td:
        nas = make_nas(td)
        a = os.path.join(td, "stagingA")
        name = "Image 1.czi"
        write_czi(os.path.join(a, "20240625", name), czi_xml(serial=""), [PLANE], ATTS)
        cfg = batch_cfg(a, "[0-9]*/*.czi", instrument="CELL", adt="2024-06-25")
        cases, out, _ = expand(cfg, nas)
        check(len(cases) == 1 and cases[0]["acquisition_datetime"] == "2024-06-25T00:00:00Z",
              "fixture: one folder-dated case")
        check(cfg_mod.dedupe_keys_for(cases[0]) == {("20240625", f"20240625/{name}")},
              "its only key is (date, original_name)")
        register(nas, cases[0], "ACQ-20240625-CELL-001")
        cases, out, already = expand(cfg, nas)
        check(cases == [] and f"SKIP 20240625/{name}: already in registry (idempotent re-run)" in out
              and already == [f"20240625/{name}"], "a re-run of the same folder is skipped, as before")

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s)")
        sys.exit(1)
    print("ALL CHECKS PASSED")


def _load_preview():
    """tools/operator/preview.py, through the package's own loader (`operator` collides with the stdlib)."""
    spec = importlib.util.spec_from_file_location("gj_operator_loader",
                                                  os.path.join(TOOLS, "operator", "_loader.py"))
    loader_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader_mod)
    return loader_mod.load().preview


def gui_check(nas, cfg):
    if importlib.util.find_spec("flask") is None:
        print("  skip: Flask not installed - GUI check skipped")
        return
    gui_dir = os.path.join(TOOLS, "operator", "gui")
    if gui_dir not in sys.path:
        sys.path.insert(0, gui_dir)
    import app as gui  # noqa: E402
    real = gui._build_cfg
    gui._build_cfg = lambda *_a, **_k: (cfg, os.path.join(TOOLS, "templates", "instruments", "axioscan7.yaml"),
                                        cfg["auto_discover"]["staging_dir"], "*.czi")
    try:
        resp = gui.app.test_client().post("/api/ingest", json={
            "instrument": "ZWSI", "staging_path": cfg["auto_discover"]["staging_dir"],
            "nas_root": nas, "dry_run": True})
        body = resp.get_data(as_text=True)
    finally:
        gui._build_cfg = real
    done = [json.loads(json.loads(ln[6:])["msg"]) for ln in body.splitlines()
            if ln.startswith("data: ") and json.loads(ln[6:]).get("kind") == "done"]
    ok = resp.status_code == 200 and len(done) == 1
    check(ok, "/api/ingest streams one done event" + ("" if ok else f" ({body[-300:]})"))
    if done:
        check(done[0].get("n_already_ingested") == 1 and done[0].get("total") == 0,
              f"the GUI ingest result carries n_already_ingested=1 (got {done[0]})")
    for js in ("app.js", "mri.js"):
        with open(os.path.join(gui_dir, "static", js), encoding="utf-8") as f:
            src = f.read()
        check("alreadyNote(r)" in src and "n_already_ingested" in src, f"{js}: the result line shows the count")


if __name__ == "__main__":
    main()
