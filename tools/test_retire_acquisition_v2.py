"""Tests for the retire tool v2 (2026-10-02): the `reidentified` and `equivalent` dispositions of
tools/retire_acquisition.py, and their modules ingest/reidentify.py and ingest/czi_compare.py.

Builds a fake NAS in a temp dir -- registries, /raw/ acquisitions whose primaries are real (synthetic) .czi
files that czifile parses and decodes, projects with real hard links -- and re-identifies and retires in it.
No NAS, no network. v1's behaviour is covered by tools/test_retire_acquisition.py.
Run: python tools/test_retire_acquisition_v2.py
"""
import contextlib
import csv
import hashlib
import io
import json
import os
import re
import stat
import struct
import sys
import tempfile
import uuid

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_acq as FA  # noqa: E402
import retire_acquisition as RA  # noqa: E402
import validate_registries as VR  # noqa: E402
from ingest import acq_id as acq_mod, config as cfg_mod, csv_safe, czi_compare as CC  # noqa: E402
from ingest import registry, reidentify as RI, retired  # noqa: E402

_fail = 0


def check(cond, msg):
    global _fail
    print(("  ok:   " if cond else "  FAIL: ") + msg)
    if not cond:
        _fail += 1


# ---- a minimal CZI writer (czifile reads it back; see section 1) ----------------------------------

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


HW = {
    "CELL": ('<HardwareSetting><StandSpecification><StandCharacteristic Key="Inverted"/></StandSpecification>'
             '</HardwareSetting>', "Axio Observer.Z1 / 7"),
    "LSM9": ('<HardwareSetting><Devices><Device SerialNumber="03761880"/></Devices><StandSpecification>'
             '<StandCharacteristic Key="LSM"/></StandSpecification></HardwareSetting>', "Axio Observer.Z1 / 7"),
    "ZWSI": ('<HardwareSetting><Devices><Device SerialNumber="4661000718"/></Devices></HardwareSetting>',
             "Axioscan 7"),
}


def czi_xml(kind, extra=""):
    hw, stand = HW[kind]
    return (f'<?xml version="1.0" encoding="utf-8"?><ImageDocument><Metadata>{hw}<Information><Instrument>'
            f'<Microscopes><Microscope Name="{stand}"><Type>Inverted</Type></Microscope></Microscopes>'
            f'</Instrument><Image><SizeX>8</SizeX></Image></Information>{extra}</Metadata></ImageDocument>').encode()


RNG = np.random.default_rng(7)
P0, P1 = (RNG.integers(0, 4000, (6, 8)).astype(np.uint16) for _ in range(2))
G_EV, G_TH = uuid.UUID("8d41b196-766a-f942-8bc3-76affa812c64"), uuid.UUID("49ff63e5-692f-7643-bfb9-068a289f5c83")
ATTS = [("EventList", "CZEVL", b"\x00" * 8, G_EV), ("Thumbnail", "JPG", b"jpg-bytes" * 20, G_TH)]


# ---- fake NAS -----------------------------------------------------------------------------------

def W(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:     # csv default terminator = CRLF
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def reg_row(acq, oname, project="", model="Axio Observer.Z1 / 7", adt=None, code=None):
    d = acq.split("-")[1]
    r = {f: "" for f in registry.REGISTRY_FIELDS}
    r.update(acq_id=acq, registration_datetime="2026-06-15T11:24:12Z",
             acquisition_datetime=adt or f"{d[:4]}-{d[4:6]}-{d[6:]}T13:51:26.2306693Z", data_ecosystem="MICROSCOPY",
             instrument=code or acq.split("-")[2], instrument_model=model, researcher="itziar", operator="Jguser",
             data_source="internal", sample_id=os.path.basename(oname), primary_kind="file",
             primary_file_name=f"{acq}.czi", original_name=oname, file_format=".czi", file_size_mb="0.0",
             file_count="1", canonical_path=f"/raw/MICROSCOPY/{d[:4]}/{d[:4]}-{d[4:6]}/{acq}/", checksum_present="Y",
             extended_metadata_present="Y", project_id=project,
             ingest_config="tools/configs/lsm900_bestguess_itziar.yaml",
             notes="BEST-GUESS / LOW-CONFIDENCE — legacy, verify before reuse")
    return r


def sidecar_bytes(row, sha):
    acq, code = row["acq_id"], row["instrument"]
    md = {"acq_id": acq, "generated": "2026-06-15T11:24:12Z", "generator": "ingest_raw.py",
          "user_supplied": {"researcher": "itziar", "operator": "Jguser", "data_source": "internal",
                            "instrument": code, "sample_id": row["sample_id"], "sample_type": "",
                            "original_name": row["original_name"], "notes": "legacy — " + code},
          "discovered": {"filename": os.path.basename(row["original_name"]), "czi_user": "Jguser"},
          "microscopy": {"instrument": {"microscope_name": "Axio Observer.Z1 / 7", "objectives": [1, 2.5]}}}
    mdb = json.dumps(md, indent=2, ensure_ascii=False).replace("\n", "\r\n").encode("utf-8") + b"\r\n"
    cs = json.dumps({"generated": "2026-06-15T11:24:12Z", "algorithm": "sha256",
                     "files": {f"{acq}.czi": sha}}, indent=2).replace("\n", "\r\n").encode()
    rd = (b"============================================================\r\n"
          b"  Raw Acquisition \xe2\x80\x94 " + acq.encode() + b"\r\n"
          b"============================================================\r\n\r\n"
          b"Acquisition ID   : " + acq.encode() + b"\r\n"
          b"Instrument       : " + code.encode() + b"\r\n"
          b"Instrument Model : Axio Observer.Z1 / 7\r\n"
          b"Primary File     : " + acq.encode() + b".czi\r\n\r\n"
          b"Notes:\r\nBEST-GUESS / LOW-CONFIDENCE \x97 legacy " + code.encode() + b"\r\n"     # a cp1252 byte
          b"------------------------------------------------------------\r\nGenerated by ingest_raw.py\r\n")
    return {"metadata.json": mdb, "checksums.json": cs, "README.txt": rd}


def make_acq(nas, row, czi_kind, planes=None, xml_extra="", atts=None, **container):
    d = RA.nas_abs(nas, row["canonical_path"])
    prim = os.path.join(d, row["primary_file_name"])
    data = write_czi(prim, czi_xml(czi_kind, xml_extra), planes or [P0, P1], atts or ATTS, **container)
    for name, b in sidecar_bytes(row, hashlib.sha256(data).hexdigest()).items():
        W(os.path.join(d, name), b)
    return prim


def link(nas, project, name, row, n=None):
    dest = os.path.join(nas, "projects", project, "raw_linked", name)
    RA.link_tree(RA.raw_primary_path(nas, row), dest)
    prov = os.path.join(nas, "projects", project, "provenance.csv")
    with open(prov, "a", encoding="utf-8", newline="") as f:
        n = n or sum(1 for _ in open(prov, encoding="utf-8"))
        csv.writer(f).writerow([f"FILE-{n:04d}", f"raw_linked/{name}", name, "hardlink", "2026-06-15", "Jguser",
                                row["acq_id"], "Auto-created during ingest", "ingest_raw.py", "", "",
                                "Auto-generated entry from ingest"])
    return dest


LSM1, LSM2, LSM3, LSM4, LSM5 = (f"ACQ-20240625-LSM9-00{i}" for i in range(1, 6))
CELL1 = "ACQ-20240625-CELL-001"
EQ_KEEP, EQ_RESAVE, EQ_PIX, EQ_META, EQ_SAME = (f"ACQ-20250915-LSM9-0{i}" for i in ("01", "16", "17", "18", "19"))


def build(nas):
    rows = [
        reg_row(CELL1, "190624/48h/real_cell_obs.czi", "PROJ-0001", adt="2024-06-25T10:00:00Z"),
        reg_row(LSM1, "190624/48h/CS_fijadas_cell obs_1.czi", "PROJ-0001"),
        reg_row(LSM2, "190624/48h/CS_fijadas_cell obs_2.czi", "PROJ-0001", adt="2024-06-25T13:52:43.3496156Z"),
        reg_row(LSM3, "190624/48h/real_lsm.czi", "PROJ-0001", adt="2024-06-25T14:00:00Z"),        # a real LSM 900 file
        reg_row(LSM4, "190624/48h/cited.czi", "PROJ-0001", adt="2024-06-25T14:10:00Z"),           # cited by a dataset
        reg_row(LSM5, "190624/48h/truncated.czi", "PROJ-0001", adt="2024-06-25T14:20:00Z"),       # bad checksums.json
        reg_row(EQ_KEEP, "24h_1.czi", "PROJ-0002", adt="2025-09-15T08:57:01.1949155Z"),
        reg_row(EQ_RESAVE, "Prueba/24h_1.czi", "PROJ-0002", adt="2025-09-15T08:57:01.1949155Z"),
        reg_row(EQ_PIX, "Prueba/24h_1_pix.czi", "PROJ-0002", adt="2025-09-15T08:57:01.1949155Z"),
        reg_row(EQ_META, "Prueba/24h_1_meta.czi", "PROJ-0002", adt="2025-09-15T08:57:01.1949155Z"),
        reg_row(EQ_SAME, "Prueba/24h_1_copy.czi", "PROJ-0002", adt="2025-09-15T08:57:01.1949155Z"),
    ]
    R = {r["acq_id"]: r for r in rows}
    reg = os.path.join(nas, "registries")
    write_csv(os.path.join(reg, "registry_raw.csv"), registry.REGISTRY_FIELDS,
              [[r[f] for f in registry.REGISTRY_FIELDS] for r in rows])
    write_csv(os.path.join(reg, "ingest_manifest.csv"), ["acq_id", "original_name", "canonical_path"],
              [[r["acq_id"], r["original_name"], r["canonical_path"]] for r in rows])
    write_csv(os.path.join(reg, "pending_subject_metadata.csv"),
              ["acq_id", "sidecar_path", "facility_animal_id", "reason", "logged_at", "status", "recovered_at"],
              [[LSM2, f"/raw/MICROSCOPY/2024/2024-06/{LSM2}/metadata.json", "", "db-miss",
                "2026-06-15T10:00:00Z", "pending", ""]])
    write_csv(os.path.join(reg, "registry_projects.csv"),
              ["project_id", "name", "description", "owner", "start_date", "status", "last_activity",
               "folder_location", "notes"],
              [["PROJ-0001", "itziar", "A", "x", "2024-01-01", "active", "2024-09-01", "/projects/itziar/", ""],
               ["PROJ-0002", "irene", "B", "x", "2025-01-01", "active", "2025-09-01", "/projects/irene/", ""],
               ["PROJ-0003", "other", "C", "x", "2025-01-01", "active", "2025-09-01", "/projects/other/", ""]])
    write_csv(os.path.join(reg, "registry_datasets.csv"),
              ["dataset_id", "short_name", "source_acq_ids", "folder_location"],
              [["DS-SEG-0001", "ds", LSM4, "/curated_datasets/segmentation/MICROSCOPY/DS-SEG-0001/"]])
    W(os.path.join(reg, ".acq_id_seq.json"),
      json.dumps({"ACQ-20240625-LSM9-": 5, "ACQ-20240625-CELL-": 1, "ACQ-20250915-LSM9-": 19}).encode())
    for p in ("itziar", "irene", "other"):
        os.makedirs(os.path.join(nas, "projects", p, "raw_linked"), exist_ok=True)
        write_csv(os.path.join(nas, "projects", p, "provenance.csv"), [
            "file_id", "output_path", "output_name", "file_type", "date_created", "creator", "input_refs",
            "process_description", "software_version", "parameters_ref", "lab_notebook_ref", "notes"], [])
    make_acq(nas, R[CELL1], "CELL", planes=[P1, P1])     # a different image
    make_acq(nas, R[LSM1], "CELL")                       # a Cell Observer file coded LSM9: re-identify
    make_acq(nas, R[LSM2], "CELL", planes=[P1, P0])
    make_acq(nas, R[LSM3], "LSM9")                       # really an LSM 900 file
    make_acq(nas, R[LSM4], "CELL")
    make_acq(nas, R[LSM5], "CELL")
    cs5 = os.path.join(RA.nas_abs(nas, R[LSM5]["canonical_path"]), "checksums.json")
    cs5b = open(cs5, "rb").read()
    W(cs5, re.sub(rb'(\.czi": ")([0-9a-f])', lambda m: m.group(1) + (b"0" if m.group(2) != b"0" else b"1"), cs5b))
    make_acq(nas, R[EQ_KEEP], "CELL", deleted=4000, metadata_last=True)   # in-place rewrite: a DELETED segment
    make_acq(nas, R[EQ_RESAVE], "CELL", order=[1, 0])                     # compact re-save, other layout
    pix = P1.copy()
    pix[2, 3] += 1
    make_acq(nas, R[EQ_PIX], "CELL", planes=[P0, pix])
    make_acq(nas, R[EQ_META], "CELL", xml_extra="<DisplaySetting>gamma 0.9</DisplaySetting>")
    keep_prim = RA.raw_primary_path(nas, R[EQ_KEEP])
    same_prim = RA.raw_primary_path(nas, R[EQ_SAME])
    os.makedirs(os.path.dirname(same_prim), exist_ok=True)
    W(same_prim, open(keep_prim, "rb").read())
    for name, b in sidecar_bytes(R[EQ_SAME], hashlib.sha256(open(same_prim, "rb").read()).hexdigest()).items():
        W(os.path.join(os.path.dirname(same_prim), name), b)
    link(nas, "itziar", "LSM9_CS_fijadas_cell obs_1.czi", R[LSM1])
    link(nas, "itziar", "LSM9_CS_fijadas_cell obs_2.czi", R[LSM2])
    link(nas, "other", "shared_obs_2.czi", R[LSM2])                    # a second project shares it
    link(nas, "irene", "LSM9_24h_1.czi", R[EQ_KEEP])
    link(nas, "other", "LSM9_24h_1_prueba.czi", R[EQ_RESAVE])          # a link to the re-save: re-pointed
    return R


def snapshot(nas):
    out = {}
    for root, _d, files in os.walk(nas):
        for fn in files:
            p = os.path.join(root, fn)
            with open(p, "rb") as f:
                out[os.path.relpath(p, nas)] = hashlib.sha256(f.read()).hexdigest()
    return out


def run(nas, bk, *args, fail_after="", allow_recent=True):
    RA.FAIL_AFTER = fail_after
    RA._HASH_CACHE.clear()
    out = io.StringIO()
    extra = ["--allow-recent-registry-writes"] if allow_recent else []
    with contextlib.redirect_stdout(out):
        rc = RA.main(["--nas-root", nas, "--backup-root", bk, "--no-index", *extra, "--retired-by", "tester", *args])
    RA.FAIL_AFTER = ""
    return rc, out.getvalue()


def raw_bytes(nas, fn):
    with open(os.path.join(nas, "registries", fn), "rb") as f:
        return f.read()


def live(nas):
    return RA.read_live(nas)


def tombs(nas):
    return retired.read_retired(retired.retired_path(os.path.join(nas, "registries")))


def validator_errors(nas):
    with contextlib.redirect_stderr(io.StringIO()):
        issues, _n = VR.validate(nas, check_enrich=False)
    return [m for _a, m in issues.errors]


def prov_rows(nas, project):
    with open(os.path.join(nas, "projects", project, "provenance.csv"), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def reid_args(acq, code="CELL", reason="a Cell Observer file in the LSM 900 folder"):
    return ("--acq-id", acq, "--reidentify-as", code, "--reason", reason)


def end_state_reidentified(nas, R, old, new, links):
    """The invariants of a finished re-identify; returns a list of failures (empty = OK)."""
    bad = []
    lv, tb = live(nas), tombs(nas)
    t = tb.get(old)
    if not t or t["disposition"] != "reidentified" or t["superseded_by"] != new or t["bytes_fate"] != "moved":
        bad.append("tombstone")
    if old in lv or new not in lv:
        bad.append("live ids")
    if list(tb).count(old) != 1:
        bad.append("one tombstone")
    raw_text = raw_bytes(nas, "registry_raw.csv")
    if raw_text.count((new + ",").encode()) != 1:
        bad.append("new row exactly once")
    old_dir = RA.nas_abs(nas, R[old]["canonical_path"])
    new_dir = RA.nas_abs(nas, lv.get(new, {}).get("canonical_path", "/x/"))
    new_prim = os.path.join(new_dir, f"{new}.czi")
    if os.path.exists(old_dir) or not os.path.isfile(new_prim):
        bad.append("folders")
    for proj, name in links:
        lk = os.path.join(nas, "projects", proj, "raw_linked", name)
        if not (os.path.exists(lk) and os.path.samefile(lk, new_prim)):
            bad.append(f"link {name}")
        evs = [r for r in prov_rows(nas, proj) if r["notes"] == f"retire_acquisition: {old} reidentified-as {new}"]
        if len(evs) != 1 or evs[0]["input_refs"] != new:
            bad.append(f"event {name}")
    if validator_errors(nas):
        bad.append(f"validator {validator_errors(nas)[:2]}")
    return bad


# ==== 1. czi_compare ==============================================================================
print("1. czi_compare: content signature + comparison on synthetic .czi files")
with tempfile.TemporaryDirectory() as d:
    a = os.path.join(d, "a.czi")
    write_czi(a, czi_xml("CELL"), [P0, P1], ATTS, deleted=4000, metadata_last=True)
    b = os.path.join(d, "b.czi")
    write_czi(b, czi_xml("CELL"), [P0, P1], [ATTS[0], ("Thumbnail", "JPG", ATTS[1][2], uuid.uuid4())], order=[1, 0])
    sa, sb = CC.signature(a), CC.signature(b)
    check(open(a, "rb").read() != open(b, "rb").read(), "the two files differ byte for byte")
    check(CC.compare(sa, sb) == [], "a re-save (DELETED segment, metadata moved, segments reordered, new "
                                    "Thumbnail GUID) is content-equivalent")
    ev = CC.evidence(sb, sa, "r", "s")
    check(ev["subblocks"] == 2 and ev["survivor"]["deleted_bytes"] >= 4000 and ev["retiree"]["deleted_bytes"] == 0
          and ev["retiree"]["attachment_guids"]["Thumbnail"] != ev["survivor"]["attachment_guids"]["Thumbnail"],
          "evidence records the container differences")
    pix = P1.copy()
    pix[0, 0] ^= 1
    c = os.path.join(d, "c.czi")
    write_czi(c, czi_xml("CELL"), [P0, pix], ATTS)
    diffs = CC.compare(CC.signature(c), sa)
    check(len(diffs) == 1 and "decoded pixels differ" in diffs[0] and "C=1" in diffs[0], f"one pixel -> {diffs}")
    e = os.path.join(d, "e.czi")
    write_czi(e, czi_xml("CELL", "<X>1</X>"), [P0, P1], ATTS)
    check(any("metadata XML differs" in x for x in CC.compare(CC.signature(e), sa)), "metadata XML -> differs")
    f_ = os.path.join(d, "f.czi")
    write_czi(f_, czi_xml("CELL"), [P0, P1], [ATTS[0], ("Thumbnail", "JPG", b"other", G_TH)])
    check(any("attachments differ" in x for x in CC.compare(CC.signature(f_), sa)), "attachment payload -> differs")
    g = os.path.join(d, "g.czi")
    write_czi(g, czi_xml("CELL"), [P0], ATTS)
    check(any("subblock" in x for x in CC.compare(CC.signature(g), sa)), "a missing subblock -> differs")

# ==== 2. reidentify + csv_safe helpers ============================================================
print("2. reidentify: byte-exact sidecar rewrites; csv_safe.append_record")
row = reg_row(LSM1, "190624/48h/x.czi")
sc = sidecar_bytes(row, "ab" * 32)
new = "ACQ-20240625-CELL-002"
md2 = RI.rewrite_metadata_json(sc["metadata.json"], LSM1, new, "LSM9", "CELL")
la, lb = sc["metadata.json"].split(b"\n"), md2.split(b"\n")
check(len(la) == len(lb) and sum(x != y for x, y in zip(la, lb)) == 2 and b"\r\n" in md2,
      "metadata.json: exactly 2 lines change (acq_id, user_supplied.instrument), CRLF kept")
check(json.loads(md2)["microscopy"] == json.loads(sc["metadata.json"])["microscopy"]
      and json.loads(md2)["user_supplied"]["notes"].endswith("LSM9"), "free text (notes) and other blocks untouched")
rd2 = RI.rewrite_readme(sc["README.txt"], LSM1, new, "LSM9", "CELL", RI.readme_note(LSM1, "LSM9", "CELL", "2026-10-04", "r"))
check(b"\x97 legacy LSM9" in rd2 and b"Instrument       : CELL\r\n" in rd2 and rd2.count(new.encode()) == 3
      and rd2.endswith(b"(find_acq.py).\r\n") and rd2.count(LSM1.encode()) == 1,
      "README.txt: id + Instrument line rewritten, the cp1252 byte and the notes kept, the note appended")
cs2 = RI.rewrite_checksums_json(sc["checksums.json"], LSM1, new, new + ".czi", "ab" * 32)
check(json.loads(cs2)["files"] == {new + ".czi": "ab" * 32}, "checksums.json: the file key renamed")
for bad, why in ((lambda: RI.rewrite_metadata_json(sc["metadata.json"], LSM2, new, "LSM9", "CELL"), "wrong id"),
                 (lambda: RI.rewrite_metadata_json(sc["metadata.json"].replace(b'"czi_user": "Jguser"', b'"instrument": "LSM9"'),
                                                   LSM1, new, "LSM9", "CELL"), "unexpected value"),
                 (lambda: RI.rewrite_readme(sc["README.txt"] + b"Instrument : LSM9\r\n", LSM1, new, "LSM9", "CELL", "n"),
                  "two Instrument lines"),
                 (lambda: RI.changes_for(row, "ACQ-20240626-CELL-001"), "another date")):
    try:
        bad()
        check(False, f"refuses ({why})")
    except ValueError:
        check(True, f"refuses ({why})")
check(RI.replace_id("ACQ-20240625-LSM9-001 ACQ-20240625-LSM9-0012", LSM1, new) ==
      new + " ACQ-20240625-LSM9-0012", "replace_id never touches a longer id")
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "t.csv")
    W(p, b"acq_id,x\r\nA,1")
    csv_safe.append_record(p, b"B,\"q,\"\"2\"\"\"")
    check(open(p, "rb").read() == b"acq_id,x\r\nA,1\nB,\"q,\"\"2\"\"\"\r\n",
          "append_record: trailing-newline guard, record verbatim, the file's own terminator")

# ==== 3..8: re-identify end to end =================================================================
with tempfile.TemporaryDirectory() as tmp:
    nas, bk = os.path.join(tmp, "nas"), os.path.join(tmp, "bk")
    os.makedirs(bk)
    R = build(nas)
    reg_dir = os.path.join(nas, "registries")

    print("3. re-identify: dry run")
    before = snapshot(nas)
    rc, out = run(nas, bk, *reid_args(LSM1))
    check(rc == 0 and "device fingerprint: CELL (no-serial+keys=Inverted+stand" in out
          and "reidentified as ACQ-20240625-CELL-002" in out and "link: keep" in out, "plan: fingerprint, preview id, link kept")
    check(snapshot(nas) == before and not os.listdir(bk), "dry run wrote nothing")

    print("4. re-identify: refusals (nothing written)")
    cases = [(reid_args(LSM3), "says LSM9"), (reid_args(LSM1, "LSM9"), "already LSM9"),
             (reid_args(LSM1, "XQZ"), "not an instrument code in use"), (reid_args(LSM4), "DS-SEG-0001"),
             (reid_args(LSM5), "not in its checksums.json")]
    for args, want in cases:
        rc, out = run(nas, bk, *args, "--execute")
        check(rc == 2 and want in out, f"{args[1]} -> {args[3]}: refused ({want})")
    extra = os.path.join(RA.nas_abs(nas, R[LSM1]["canonical_path"]), "notes.txt")
    W(extra, b"x")
    rc, out = run(nas, bk, *reid_args(LSM1), "--execute")
    check(rc == 2 and "besides the primary" in out, "an extra file in the folder -> refused")
    os.remove(extra)
    lst = os.path.join(tmp, "bad.csv")
    write_csv(lst, ["acq_id", "disposition", "target_acq_id", "to_project", "reason", "new_instrument"],
              [[LSM1, "reidentified", CELL1, "", "r", "CELL"]])
    rc, out = run(nas, bk, "--list", lst, "--execute")
    check(rc == 2 and "not a target_acq_id" in out, "a target_acq_id on a re-identify -> refused")
    check(snapshot(nas) == before and not os.listdir(bk), "no refusal wrote anything")
    real_link = os.link

    def _no_raw_link(src, dst, *a, **k):
        if RA.PROBE_PREFIX in str(dst):
            raise PermissionError(13, "Access is denied (simulated share policy)", str(dst))
        return real_link(src, dst, *a, **k)
    os.link = _no_raw_link
    try:
        rc, out = run(nas, bk, *reid_args(LSM1), "--execute")
    finally:
        os.link = real_link
    after = {k: v for k, v in snapshot(nas).items()}
    check(rc == 4 and "nothing committed" in out and after == before
          and not [d for d in os.listdir(os.path.dirname(RA.nas_abs(nas, R[LSM1]["canonical_path"].rstrip("/"))))
                   if d.startswith(RA.PROBE_PREFIX)],
          "a share that refuses a hard link inside /raw/: stopped by the probe BEFORE commit A, the NAS "
          "byte-identical, no probe folder left")
    for d in os.listdir(bk):
        RA.remove_tree_or_file(os.path.join(bk, d))      # that run's backup: not part of what follows

    print("5. re-identify: execute")
    raw_before, man_before = raw_bytes(nas, "registry_raw.csv"), raw_bytes(nas, "ingest_manifest.csv")
    old_dir = RA.nas_abs(nas, R[LSM1]["canonical_path"])
    old_prim = RA.raw_primary_path(nas, R[LSM1])
    old_sc = {n: open(os.path.join(old_dir, n), "rb").read() for n in RA.SIDECARS}
    file_sha = hashlib.sha256(open(old_prim, "rb").read()).hexdigest()
    lk1 = os.path.join(nas, "projects", "itziar", "raw_linked", "LSM9_CS_fijadas_cell obs_1.czi")
    rc, out = run(nas, bk, *reid_args(LSM1), "--execute")
    NEW1 = "ACQ-20240625-CELL-002"
    check(rc == 0 and "self-check: OK" in out, f"execute rc=0 (got {rc})")
    bad = end_state_reidentified(nas, R, LSM1, NEW1, [("itziar", "LSM9_CS_fijadas_cell obs_1.czi")])
    check(not bad, f"end state: tombstone, rows, folders, link identity, one event, validator clean {bad or ''}")
    t = tombs(nas)[LSM1]
    reason, ev = retired.split_evidence(t["reason"])
    check(reason == "a Cell Observer file in the LSM 900 folder" and ev["method"] == "reidentify/1"
          and ev["fingerprint"]["instrument"] == "CELL" and ev["changes"]["instrument"] == ["LSM9", "CELL"]
          and t["sha256"] == file_sha and t["moved_to"].endswith(f"/{NEW1}/{NEW1}.czi"),
          "tombstone: reason + evidence (method, fingerprint, changes), sha256, moved_to")
    recs = csv_safe.split_records(raw_before)
    old_rec = [r for r in recs if r.startswith(LSM1.encode() + b",")][0]
    after = csv_safe.split_records(raw_bytes(nas, "registry_raw.csv"))
    check(after[:-1] == [r for r in recs if r is not old_rec], "registry_raw.csv: every other record byte-identical, in order")
    new_r = dict(zip(registry.REGISTRY_FIELDS, csv_safe.record_fields(after[-1])))
    old_r = dict(zip(registry.REGISTRY_FIELDS, csv_safe.record_fields(old_rec)))
    changed = sorted(k for k in registry.REGISTRY_FIELDS if new_r[k] != old_r[k])
    check(changed == sorted(RI.IDENTITY_FIELDS) and new_r["instrument"] == "CELL"
          and new_r["registration_datetime"] == old_r["registration_datetime"] and new_r["notes"] == old_r["notes"],
          f"the new row = the old row with only {changed} changed")
    check(t["registry_raw_row"].encode() + b"\r\n" == old_rec, "the tombstone holds the old row verbatim")
    man = csv_safe.split_records(raw_bytes(nas, "ingest_manifest.csv"))
    man_old = [r for r in csv_safe.split_records(man_before) if r.startswith(LSM1.encode() + b",")]
    check(man[-1] == RI.carry_record(man_old[0], LSM1, NEW1) and man[-1].count(NEW1.encode()) == 2
          and not any(r.startswith(LSM1.encode() + b",") for r in man)
          and len(man) == len(csv_safe.split_records(man_before)), "ingest_manifest: the row carried over to the new id")
    new_dir = os.path.join(os.path.dirname(old_dir), NEW1)
    new_prim = os.path.join(new_dir, NEW1 + ".czi")
    check(os.path.samefile(new_prim, lk1) and open(new_prim, "rb").read() and
          hashlib.sha256(open(new_prim, "rb").read()).hexdigest() == file_sha, "the new primary IS the project link's file")
    for n in RA.SIDECARS:
        a, b = old_sc[n].split(b"\r\n"), open(os.path.join(new_dir, n), "rb").read().split(b"\r\n")
        nch = sum(x != y for x, y in zip(a, b))
        added = b[len(a) - 1:-1]          # lines appended before the final terminator
        want = {"metadata.json": (2, 0), "checksums.json": (1, 0), "README.txt": (4, 1)}[n]
        check((nch - (1 if added else 0), len(added)) == want,
              f"{n}: {nch - (1 if added else 0)} line(s) rewritten, {len(added)} appended, CRLF kept")
    check(os.path.basename(lk1).startswith("LSM9_"), "the link kept its name (Q5)")
    bks = [x for x in os.listdir(bk) if x.startswith("gjesus3_retire_backup_")]
    check(len(bks) == 1 and os.path.exists(os.path.join(bk, bks[0], "acquisitions", LSM1, "README.txt"))
          and os.path.exists(os.path.join(bk, bks[0], "projects", "itziar", "provenance.csv")),
          "backup: registries, the old sidecars, the touched provenance")

    print("6. idempotence, lookups, the allocator and the dedup index")
    before = snapshot(nas)
    rc, out = run(nas, bk, *reid_args(LSM1), "--execute")
    check(rc == 0 and "no-op" in out and snapshot(nas) == before and len(os.listdir(bk)) == 1,
          "re-run: exit 0, no-op, nothing written, no backup")
    rc, out = run(nas, bk, *reid_args(LSM1), "--execute", allow_recent=False)
    check(rc == 0 and "changed" not in out, "the window check knows the last registry write was this tool's")
    r = registry.resolve_acq_id(LSM1, reg_dir)
    check(r["status"] == "retired" and r["resolved"] == NEW1, "resolve_acq_id: the old id resolves to the new one")
    o = io.StringIO()
    with contextlib.redirect_stdout(o):
        FA.main(["--nas-root", nas, LSM1])
    check("re-identified as " + NEW1 in o.getvalue() and "evidence" not in o.getvalue(), "find_acq: says re-identified as")
    keys = cfg_mod._build_dedupe_index(os.path.join(reg_dir, "registry_raw.csv"))
    check(("20240625", R[LSM1]["original_name"]) in keys, "the source stays blocked from re-ingest (new row + tombstone)")
    check(acq_mod.generate_acq_id("20240625", "CELL", os.path.join(reg_dir, "registry_raw.csv")) == "ACQ-20240625-CELL-003"
          and json.load(open(os.path.join(reg_dir, ".acq_id_seq.json")))["ACQ-20240625-CELL-"] == 2,
          "the allocator reserved -002 and moves on to -003")
    check(acq_mod.generate_acq_id("20240625", "LSM9", os.path.join(reg_dir, "registry_raw.csv")) == "ACQ-20240625-LSM9-006",
          "the old id is never reused")

    print("7. a mixed list: re-identify (two links, a pending row) + equivalent (a link re-pointed)")
    lst = os.path.join(tmp, "mixed.csv")
    write_csv(lst, ["acq_id", "disposition", "target_acq_id", "to_project", "reason", "new_instrument"],
              [[LSM2, "reidentified", "", "", "Cell Observer file", "CELL"],
               [EQ_RESAVE, "equivalent", EQ_KEEP, "", "re-save of -001 (Prueba copy)", ""]])
    rc, out = run(nas, bk, "--list", lst)
    check(rc == 0 and "content-equivalent to " + EQ_KEEP in out and "reidentified as ACQ-20240625-CELL-003" in out,
          "dry run: both planned")
    keys_before = cfg_mod._build_dedupe_index(os.path.join(reg_dir, "registry_raw.csv"))
    real_index = cfg_mod._build_dedupe_index

    def _no_dedup(*_a, **_k):
        raise AssertionError("the ingest dedup index was consulted")
    cfg_mod._build_dedupe_index = _no_dedup       # a re-identify must never go through the ingest's dedup
    try:
        rc, out = run(nas, bk, "--list", lst, "--execute")
    finally:
        cfg_mod._build_dedupe_index = real_index
    NEW2 = "ACQ-20240625-CELL-003"
    check(rc == 0, f"execute rc=0 (got {rc}) without ever consulting the ingest dedup index: a re-identify "
                   f"cannot be blocked by its own tombstone")
    keys_after = cfg_mod._build_dedupe_index(os.path.join(reg_dir, "registry_raw.csv"))
    check(("20240625", R[LSM2]["original_name"]) in keys_before and keys_after == keys_before,
          "the dedup index is unchanged by the run: the source stays blocked, nothing else is unblocked")
    bad = end_state_reidentified(nas, R, LSM2, NEW2, [("itziar", "LSM9_CS_fijadas_cell obs_2.czi"),
                                                       ("other", "shared_obs_2.czi")])
    check(not bad, f"re-identified with both links kept, one event each {bad or ''}")
    pend = list(csv.DictReader(open(os.path.join(reg_dir, "pending_subject_metadata.csv"), encoding="utf-8")))
    check(len(pend) == 1 and pend[0]["acq_id"] == NEW2 and f"/{NEW2}/metadata.json" in pend[0]["sidecar_path"],
          "the pending row is carried over (id and sidecar path rewritten)")
    check(json.loads(tombs(nas)[LSM2]["other_rows_removed"]).get("pending_subject_metadata.csv"),
          "... and kept verbatim in the tombstone")
    t = tombs(nas)[EQ_RESAVE]
    _r, ev = retired.split_evidence(t["reason"])
    resave_sha = ev["retiree"]["sha256"]
    check(t["disposition"] == "equivalent" and t["superseded_by"] == EQ_KEEP and t["bytes_fate"] == "deleted"
          and t["sha256"] == resave_sha and ev["method"] == "czi-content/1" and ev["subblocks"] == 2
          and ev["survivor"]["deleted_bytes"] >= 4000, "equivalent tombstone: evidence (method, subblocks, container)")
    lk = os.path.join(nas, "projects", "other", "raw_linked", "LSM9_24h_1_prueba.czi")
    check(os.path.samefile(lk, RA.raw_primary_path(nas, R[EQ_KEEP])) and
          not os.path.exists(RA.nas_abs(nas, R[EQ_RESAVE]["canonical_path"])),
          "the re-save's link now IS the survivor (same name); its /raw/ folder is gone")
    evs = [r for r in prov_rows(nas, "other") if EQ_RESAVE in r["notes"]]
    check(len(evs) == 1 and evs[0]["input_refs"] == EQ_KEEP and "content-equivalent" in evs[0]["process_description"],
          "one replaced-by event")
    check(not validator_errors(nas), "validator: clean")

    print("8. equivalent: refusals")
    for acq, want in ((EQ_PIX, "decoded pixels differ"), (EQ_META, "metadata XML differs"),
                      (EQ_SAME, "byte-identical"), (CELL1, "not content-equivalent")):
        rc, out = run(nas, bk, "--acq-id", acq, "--equivalent-of", EQ_KEEP, "--reason", "r", "--execute")
        check(rc == 2 and want in out, f"{acq} -> refused ({want})")

    print("9. validator: unknown disposition, a wrong superseded_by for a re-identify")
    tp = retired.retired_path(reg_dir)
    good = open(tp, "rb").read()
    W(tp, good.replace(b",reidentified,", b",renamed,", 1))
    check(any("unknown disposition" in e for e in validator_errors(nas)), "unknown disposition -> ERROR")
    W(tp, good.replace(f",reidentified,{NEW1},".encode(), f",reidentified,{CELL1},".encode(), 1))
    check(any("not this acquisition under another instrument code" in e for e in validator_errors(nas)),
          "re-identified as an unrelated live id -> ERROR")
    W(tp, good)
    check(not validator_errors(nas), "validator: clean again")

# ==== 10. a crash at EVERY step resumes to the same end state ======================================
print("10. crash-resume sweep: re-identify, every injection point")
for step in ("tombstone", "built", "commit", "links", "bytes", "provenance"):
    with tempfile.TemporaryDirectory() as tmp:
        nas, bk = os.path.join(tmp, "nas"), os.path.join(tmp, "bk")
        os.makedirs(bk)
        R = build(nas)
        rc1, _ = run(nas, bk, *reid_args(LSM1), "--execute", fail_after=step)
        errs = validator_errors(nas)
        seen = ("is both live" if step in ("tombstone", "built") else
                "still exists" if step in ("commit", "links") else "")
        rc2, out2 = run(nas, bk, *reid_args(LSM1), "--execute")
        rc3, out3 = run(nas, bk, *reid_args(LSM1), "--execute")
        bad = end_state_reidentified(nas, R, LSM1, "ACQ-20240625-CELL-002", [("itziar", "LSM9_CS_fijadas_cell obs_1.czi")])
        ok = (rc1 == 4 and rc2 == 0 and rc3 == 0 and "no-op" in out3 and not bad
              and (not seen or any(seen in e for e in errs)))
        check(ok, f"crash after '{step}': rc {rc1}->{rc2}->{rc3}; validator meanwhile: "
                  f"{(seen or 'no new error') if ok else errs[:2]}; same end state {bad or ''}")

print("11. a run stopped INSIDE the old folder's delete")
for victim in ("ACQ-20240625-LSM9-001.czi", "README.txt"):
    with tempfile.TemporaryDirectory() as tmp:
        nas, bk = os.path.join(tmp, "nas"), os.path.join(tmp, "bk")
        os.makedirs(bk)
        R = build(nas)
        rc1, _ = run(nas, bk, *reid_args(LSM1), "--execute", fail_after="links")
        os.remove(os.path.join(RA.nas_abs(nas, R[LSM1]["canonical_path"]), victim))
        rc2, out2 = run(nas, bk, *reid_args(LSM1), "--execute")
        bad = end_state_reidentified(nas, R, LSM1, "ACQ-20240625-CELL-002", [("itziar", "LSM9_CS_fijadas_cell obs_1.czi")])
        check(rc1 == 4 and rc2 == 0 and "partly deleted" in out2 and not bad,
              f"{victim} already gone -> the re-run finishes the delete {bad or ''}")

print("12. crash-resume sweep: equivalent, every injection point")
for step in ("tombstone", "commit", "links", "bytes", "provenance"):
    with tempfile.TemporaryDirectory() as tmp:
        nas, bk = os.path.join(tmp, "nas"), os.path.join(tmp, "bk")
        os.makedirs(bk)
        R = build(nas)
        args = ("--acq-id", EQ_RESAVE, "--equivalent-of", EQ_KEEP, "--reason", "re-save", "--execute")
        rc1, _ = run(nas, bk, *args, fail_after=step)
        rc2, _ = run(nas, bk, *args)
        rc3, out3 = run(nas, bk, *args)
        lk = os.path.join(nas, "projects", "other", "raw_linked", "LSM9_24h_1_prueba.czi")
        notes = [r["notes"] for r in prov_rows(nas, "other") if "retire_acquisition" in r["notes"]]
        ok = (rc1 == 4 and rc2 == 0 and rc3 == 0 and "no-op" in out3 and list(tombs(nas)) == [EQ_RESAVE]
              and os.path.samefile(lk, RA.raw_primary_path(nas, R[EQ_KEEP]))
              and not os.path.exists(RA.nas_abs(nas, R[EQ_RESAVE]["canonical_path"]))
              and notes == [f"retire_acquisition: {EQ_RESAVE} replaced-by {EQ_KEEP}"] and not validator_errors(nas))
        check(ok, f"crash after '{step}': rc {rc1}->{rc2}->{rc3}, link IS the survivor, one event")

print("13. one name of a read-only file is removed without un-protecting the file")
if os.name == "nt":
    with tempfile.TemporaryDirectory() as d:
        a, b = os.path.join(d, "a.bin"), os.path.join(d, "b.bin")
        W(a, b"x")
        os.link(a, b)
        os.chmod(a, stat.S_IREAD)
        RA.remove_link_name(a, b)
        check(not os.path.exists(a) and os.path.exists(b) and not os.access(b, os.W_OK),
              "the other name survives and is still read-only")
        os.chmod(b, stat.S_IWRITE)
else:
    print("  skip: Windows only")

print("ALL PASSED" if not _fail else f"{_fail} FAILURE(S)")
sys.exit(1 if _fail else 0)
