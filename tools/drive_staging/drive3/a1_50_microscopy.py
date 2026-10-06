"""A1 step 5: microscopy (.czi, .lif/.lifext): SHA-256 against production, then for the rest the
instrument (device serial), re-saves of production acquisitions, same-timestamp groups inside the
drive, derivative signals, and the project each path claims.

Headers are read from the staged copy (read-only): for .czi only the metadata segment, with the
drives-1+2 catalog's own reader (tools/drive_staging/catalog.py czi_read_xml / parse_czi_xml /
fingerprint over tools/reference/microscopy_instruments.yaml); for .lif the XML header.

  re-save of a production acquisition: not byte-identical, but the same instrument, the same
      AcquisitionDateAndTime (to the second) AND the same file name as a production row
  same-timestamp group: several drive files with one (instrument, AcquisitionDateAndTime)
  derivative signals: no HardwareSetting and no Experiment block (czi-processed: an export),
      a name with scale / export / Untitled / crop / subset / copy, or < 5 MB
  project claim: the nearest folder (or file-name chunk) holding a protocol-shaped code NNYY,
      validated against the facility DB's protocol list; when the file names an animal (ID12,
      m12), that animal is looked up in the claimed protocol (SELECT only)

Writes a1\\microscopy_files.csv, a1\\microscopy_summary.txt.

    python a1_50_microscopy.py
"""
import collections
import concurrent.futures as cf
import json
import os
import re
import struct
import sys
import xml.etree.ElementTree as ET

from a1_common import CACHE, TOOLS, cache_load, cache_save, gb, lp, out_path, read_csv_dicts, snapshot, staged, write_csv

sys.path.insert(0, os.path.join(TOOLS, "drive_staging"))
sys.path.insert(0, TOOLS)
import catalog  # noqa: E402  (pure readers: czi_read_xml, parse_czi_xml, fingerprint, load_instruments)
import animal_db  # noqa: E402

CODE_RX = re.compile(r"(?<![0-9])((?:0[1-9]|1[0-9])(?:1[6-9]|2[0-6]))(?![0-9])")
ANIMAL_RX = re.compile(r"(?:^|[^A-Za-z])(?:ID|id|Id)\s?_?(\d{1,4})|(?:^|[_\s-])[mM](\d{1,4})(?=[_\s.-]|$)")
DERIV_RX = re.compile(r"scale|export|untitled|crop|subset|copy|copia|_pt\d|maximum|mip|processed", re.I)


def czi_probe(rp):
    try:
        xml, err = catalog.czi_read_xml(staged(rp))
        if xml is None:
            return rp, {"ok": False, "err": err}
        p = catalog.czi_from_bytes(xml, None)
        try:
            root = ET.fromstring(xml)
            img = root.find(".//Information/Image")
            if img is not None:
                for k in ("SizeX", "SizeY", "SizeC", "SizeZ", "SizeT", "SizeM", "SizeS", "SizeB"):
                    e = img.find(k)
                    p[k] = (e.text or "").strip() if e is not None else ""
            doc = root.find(".//Information/Document/Name")
            p["doc_name"] = (doc.text or "").strip() if doc is not None and doc.text else ""
        except ET.ParseError:
            pass
        return rp, p
    except Exception as e:  # noqa: BLE001
        return rp, {"ok": False, "err": f"{type(e).__name__}: {str(e)[:100]}"}


def lif_probe(rp):
    out = {"ok": False, "err": ""}
    try:
        with open(lp(staged(rp)), "rb") as f:
            head = f.read(13)
            if len(head) < 13 or struct.unpack("<i", head[:4])[0] != 0x70 or head[8] != 0x2A:
                out["err"] = "not a LIF header (no 0x70/0x2A)"
                return rp, out
            nchar = struct.unpack("<i", head[9:13])[0]
            xml = f.read(nchar * 2).decode("utf-16-le", errors="replace")
        out["ok"] = True
        for key in ("SystemTypeName", "SystemSerialNumber", "MicroscopeModel", "MicroscopeType", "UserSettingName"):
            vals = sorted(set(re.findall(rf'{key}="([^"]*)"', xml)))
            out[key] = ";".join(v for v in vals if v)[:200]
        out["n_elements"] = len(re.findall(r"<Element ", xml))
        out["n_images"] = len(re.findall(r"<Image ", xml))
        out["start_times"] = ";".join(sorted(set(re.findall(r'StartTime="([^"]*)"', xml)))[:3])
    except Exception as e:  # noqa: BLE001
        out["err"] = f"{type(e).__name__}: {str(e)[:100]}"
    return rp, out


def claim_of(rp):
    """(code, where, animal) from the path: nearest folder or file-name chunk holding a code."""
    parts = rp.split("\\")
    for i in range(len(parts) - 1, 0, -1):
        seg = parts[i]
        seg_nodate = re.sub(r"(?<!\d)\d{6,8}(?!\d)", " ", seg)
        m = CODE_RX.findall(seg_nodate)
        if m:
            return m[0], ("file name" if i == len(parts) - 1 else seg), m
    return "", "", []


def animal_of(rp):
    name = rp.rsplit("\\", 1)[-1]
    m = ANIMAL_RX.search(re.sub(r"\d{6,8}", " ", name))
    if m:
        return m.group(1) or m.group(2)
    return ""


def main():
    df = cache_load("files")
    sel = df[df["a1class"].isin(["microscopy-czi", "microscopy-lif"])]
    czi = [rp for rp, e in zip(sel["relpath"], sel["ext"]) if e == ".czi"]
    lif = [rp for rp, e in zip(sel["relpath"], sel["ext"]) if e in (".lif", ".lifext")]
    probes = cache_load("czi_probes") or {}
    todo = [rp for rp in czi if rp not in probes]
    print(f".czi {len(czi)} (to read {len(todo)}), .lif/.lifext {len(lif)}")
    with cf.ThreadPoolExecutor(8) as ex:
        for i, (rp, p) in enumerate(ex.map(czi_probe, todo), 1):
            probes[rp] = p
            if i % 500 == 0:
                print(f"  {i}")
                cache_save("czi_probes", probes)
    cache_save("czi_probes", probes)
    with cf.ThreadPoolExecutor(4) as ex:
        lifp = dict(ex.map(lif_probe, lif))
    ref = catalog.load_instruments()
    # production microscopy rows: (instrument, acquisition second) and names
    reg = read_csv_dicts(snapshot("registry_raw.csv"))
    micro = [r for r in reg if r["instrument"] in ("CELL", "LSM9", "ZWSI", "XMIC")]
    by_inst_time = collections.defaultdict(list)
    for r in micro:
        t = re.sub(r"\D", "", r["acquisition_datetime"])[:14]
        by_inst_time[(r["instrument"], t)].append(r)
    # facility DB: the valid protocol list, then (code, animal) lookups
    dbc_p = os.path.join(CACHE, "db_lookups.json")
    dbc = json.load(open(dbc_p, encoding="utf-8")) if os.path.exists(dbc_p) else {}
    from ni_gnuclear_discover import valid_protocol_codes  # SELECT project_code, projectAlias FROM projects
    conn = animal_db.get_connection()
    try:
        valid = valid_protocol_codes(conn)
        rows = []
        for rp, size, sha, top, inprod, acq, mtime in zip(sel["relpath"], sel["size"], sel["sha256"], sel["top"],
                                                          sel["in_prod_raw"], sel["prod_acq_id"], sel["mtime"]):
            name = rp.rsplit("\\", 1)[-1]
            ext = os.path.splitext(name)[1].lower()
            row = {"relpath": rp, "top": top, "size": size, "sha256": sha, "ext": ext,
                   "in_prod_raw": "Y" if inprod else "N", "prod_acq_id": acq, "mtime": mtime}
            if ext == ".czi":
                p = probes.get(rp, {})
                inst, rule, fired = catalog.fingerprint(ref, p.get("serials", []), p.get("keys", []), p.get("stand", "")) \
                    if p.get("ok") else ("unreadable", "", [])
                cls = catalog.czi_class(p) if "ok" in p else "czi-unreadable"
                acq_dt = p.get("acq_dt", "")
                row.update({"czi_class": cls, "instrument": inst, "fp_rule": rule,
                            "fp_conflict": "Y" if len({c for c, _ in fired}) > 1 else "",
                            "serials": ";".join(p.get("serials", [])), "stand_keys": ";".join(p.get("keys", [])),
                            "stand": p.get("stand", ""), "system": p.get("system", ""), "acq_dt": acq_dt,
                            "zen": p.get("zen", ""), "objective": p.get("objective", "")[:80],
                            "size_xy": f"{p.get('SizeX', '')}x{p.get('SizeY', '')}", "size_c": p.get("SizeC", ""),
                            "size_z": p.get("SizeZ", ""), "size_m": p.get("SizeM", ""), "size_s": p.get("SizeS", ""),
                            "doc_name": p.get("doc_name", "")[:80], "read_err": p.get("err", "")})
            else:
                p = lifp.get(rp, {})
                row.update({"czi_class": "lif" if ext == ".lif" else "lifext",
                            "instrument": ("LEICA " + p.get("SystemTypeName", "")).strip() if p.get("ok") else "unreadable",
                            "serials": p.get("SystemSerialNumber", ""), "stand": p.get("MicroscopeModel", ""),
                            "system": p.get("SystemTypeName", ""), "acq_dt": p.get("start_times", ""),
                            "doc_name": f"{p.get('n_images', '')} images / {p.get('n_elements', '')} elements",
                            "read_err": p.get("err", "")})
            # re-save of a production acquisition (same instrument + second + file name, other bytes)
            resave = ""
            if not inprod and row.get("acq_dt") and ext == ".czi":
                t = re.sub(r"\D", "", row["acq_dt"])[:14]
                cands = by_inst_time.get((row["instrument"], t), [])
                same_name = [c for c in cands if c["original_name"].replace("\\", "/").rsplit("/", 1)[-1] == name]
                if same_name:
                    resave = "re-save of " + ";".join(c["acq_id"] for c in same_name)
                elif cands:
                    resave = "same instrument+second as " + ";".join(c["acq_id"] for c in cands[:3]) + " (other name)"
            row["vs_production"] = "byte-identical " + acq if inprod else (resave or "not in production")
            sig = []
            if row.get("czi_class") == "czi-processed":
                sig.append("no hardware/experiment block (export)")
            if DERIV_RX.search(name):
                sig.append("derivative word in name")
            if size < 5_000_000:
                sig.append("small (<5 MB)")
            row["derivative_signals"] = "; ".join(sig)
            code, where, allc = claim_of(rp)
            animal = animal_of(rp)
            verdict, ev = "", ""
            if not code:
                verdict = "no claim"
            elif code not in valid:
                verdict = "B? (not a protocol code in the facility DB)"
            elif animal:
                k = f"{code}|{int(animal)}"
                if k not in dbc:
                    res = animal_db.lookup(code, int(animal), conn=conn, use_cache=False)
                    if res.status == "unreachable":
                        raise SystemExit("DB unreachable")
                    dbc[k] = {"status": res.status, "procedures": (res.subject or {}).get("procedures", []),
                              "species": (res.subject or {}).get("species", ""),
                              "dob": (res.subject or {}).get("date_of_birth", "")}
                found = dbc[k]["status"] == "found"
                verdict = "CONFIRMED (animal in protocol)" if found else "C (animal not in claimed protocol)"
                ev = f"{code}/{animal}: {dbc[k]['status']}"
            else:
                verdict = "claim, protocol valid (no animal id to check)"
            row.update({"claim_code": code, "claim_where": where[:80], "claim_all": ";".join(allc), "animal": animal,
                        "claim_verdict": verdict, "claim_evidence": ev})
            rows.append(row)
    finally:
        conn.close()
        with open(out_path("_cache", "db_lookups.json"), "w", encoding="utf-8") as f:
            json.dump(dbc, f, indent=0)
    # same-timestamp groups inside the drive
    grp = collections.defaultdict(list)
    for r in rows:
        if r.get("acq_dt") and r["ext"] == ".czi":
            grp[(r["instrument"], r["acq_dt"])].append(r)
    for (inst, t), rs in grp.items():
        shas = {r["sha256"] for r in rs}
        for r in rs:
            r["same_ts_group_files"] = len(rs)
            r["same_ts_group_distinct"] = len(shas)
    fields = ["relpath", "top", "size", "sha256", "ext", "in_prod_raw", "prod_acq_id", "vs_production", "czi_class",
              "instrument", "fp_rule", "fp_conflict", "serials", "stand_keys", "stand", "system", "acq_dt", "zen",
              "objective", "size_xy", "size_c", "size_z", "size_m", "size_s", "doc_name", "derivative_signals",
              "same_ts_group_files", "same_ts_group_distinct", "claim_code", "claim_where", "claim_all", "animal",
              "claim_verdict", "claim_evidence", "read_err", "mtime"]
    rows.sort(key=lambda r: r["relpath"])
    write_csv("microscopy_files.csv", rows, fields)
    cache_save("microscopy_rows", rows)
    # ---- summary
    L = []
    first = {}
    for r in rows:
        first.setdefault(r["sha256"], r)
    u = list(first.values())
    L.append(f"files: {len(rows)} ({gb(sum(r['size'] for r in rows)):.1f} GB); distinct by SHA-256 {len(u)} ({gb(sum(r['size'] for r in u)):.1f} GB)")
    L.append("distinct files by production status:")
    for k, v in collections.Counter(r["vs_production"].split(" ")[0] if r["vs_production"].startswith("byte") else
                                    r["vs_production"].split(" of ")[0].split(" as ")[0] for r in u).most_common():
        L.append(f"   {k:45s} {v}")
    L.append("distinct NOT byte-identical, by instrument (fingerprint) x czi class:")
    for (i, c), v in sorted(collections.Counter((r["instrument"], r["czi_class"]) for r in u if r["in_prod_raw"] == "N").items()):
        b = sum(r["size"] for r in u if r["in_prod_raw"] == "N" and r["instrument"] == i and r["czi_class"] == c)
        L.append(f"   {i:28s} {c:16s} {v:5d}  {gb(b):7.1f} GB")
    L.append("distinct NOT in production, claim verdicts:")
    for k, v in collections.Counter(r["claim_verdict"] for r in u if r["in_prod_raw"] == "N").most_common():
        L.append(f"   {k:55s} {v}")
    L.append("distinct NOT in production, claimed codes: " + str(collections.Counter(r["claim_code"] for r in u if r["in_prod_raw"] == "N").most_common()))
    ds = collections.Counter(bool(r["derivative_signals"]) for r in u if r["in_prod_raw"] == "N")
    L.append(f"distinct NOT in production with a derivative signal: {ds[True]}; without: {ds[False]}")
    g2 = [k for k, rs in grp.items() if len({r['sha256'] for r in rs}) > 1]
    L.append(f"same-timestamp groups with >1 distinct file: {len(g2)}")
    txt = "\n".join(L)
    with open(out_path("microscopy_summary.txt"), "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
