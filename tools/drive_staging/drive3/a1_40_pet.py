"""A1 step 4: PET / CT on the drive (PET\\ and anywhere else): what the files are, and their coverage.

Every standalone DICOM (not inside a Bruker exam) except the pig MRI under Otros\\ is opened for its
header (pydicom, stop_before_pixels; no patient element is written). Molecubes reconstructions
are named <YYYYMMDDhhmmss>_<PET|CT|SPECT>_<ALGO>_<recon>[_frame<f>|_frameMULTI][_iter<n>].dcm, the
only reliable anchor on the NI side (memory: ni_live_machine_layout); production's NI rows carry
original_name = <ts14>_<MOD>_<ALGO>_<recon> (the S:\\gnuclear backfill) and acquisition_datetime =
that timestamp.

Coverage of each file, three ways:
  sha       its SHA-256 is in production /raw/ (prod_raw_sha256.csv)
  name      a production PET/CT/SPECT row has original_name ending in <ts14>_<MOD>_<ALGO>_<recon>
  time      a production PET/CT/SPECT row has acquisition_datetime == ts14 and the same modality
and against the S:\\gnuclear snapshot of 2026-08-12 (J:\\gjesus3-data\\staging\\ni_gnuclear_20260812\\
_manifest.jsonl, 2,485 files; part of it was held back pending protocol codes): by SHA-256 and by key.

Writes a1\\pet_files.csv (one row per file) and a1\\pet_summary.txt.

    python a1_40_pet.py
"""
import collections
import concurrent.futures as cf
import json
import os
import re

from a1_common import NAS, cache_load, gb, load_prod_index, lp, out_path, read_csv_dicts, snapshot, staged, write_csv

NI_RX = re.compile(r"^(?P<ts>\d{14})_(?P<mod>PET|CT|SPECT)_(?P<algo>[A-Z0-9]+)_(?P<recon>\d+)"
                   r"(?:_frame(?P<frame>MULTI|\d+))?(?:_iter(?P<iter>\d+))?(?:\.dcm)+$", re.I)
GN = os.path.join(NAS, "staging", "ni_gnuclear_20260812", "_manifest.jsonl")
TAGS = ["Modality", "Manufacturer", "ManufacturerModelName", "SeriesDescription", "StudyDate", "StudyTime",
        "AcquisitionDate", "AcquisitionTime", "NumberOfFrames", "Rows", "Columns", "SOPClassUID",
        "InstitutionName", "SoftwareVersions", "ImageType", "SeriesNumber"]


def header(rp):
    import pydicom
    try:
        with open(lp(staged(rp)), "rb") as f:
            ds = pydicom.dcmread(f, stop_before_pixels=True, force=True, specific_tags=TAGS)

        def g(k):
            v = ds.get(k, "")
            if isinstance(v, (list, tuple)) or type(v).__name__ == "MultiValue":
                v = "\\".join(str(x) for x in v)
            return " ".join(str(v or "").split())
        out = {k: g(k) for k in TAGS}
        try:
            out["SOPClassUID"] = ds.SOPClassUID.name
        except Exception:  # noqa: BLE001
            pass
        out["hdr_err"] = ""
        return rp, out
    except Exception as e:  # noqa: BLE001
        return rp, {"hdr_err": f"{type(e).__name__}: {str(e)[:100]}"}


def main():
    df = cache_load("files")
    prod = load_prod_index()
    reg = read_csv_dicts(snapshot("registry_raw.csv"))
    ni = [r for r in reg if r["instrument"] in ("PET", "CT", "SPECT")]
    by_key = collections.defaultdict(list)
    by_time = collections.defaultdict(list)
    for r in ni:
        m = re.search(r"(\d{14})_(PET|CT|SPECT)_([A-Z0-9]+)_(\d+)", r["original_name"], re.I)
        if m:
            by_key[f"{m.group(1)}_{m.group(2).upper()}_{m.group(3).upper()}_{m.group(4)}"].append(r["acq_id"])
        t = re.sub(r"\D", "", r["acquisition_datetime"])[:14]
        by_time[(t, r["instrument"])].append(r["acq_id"])
    gn_sha, gn_key = {}, collections.defaultdict(list)
    with open(lp(GN), encoding="utf-8") as f:
        for line in f:
            j = json.loads(line)
            gn_sha[j["sha256"]] = j["rel"]
            gn_key[j["acq_key"].upper()].append(j["rel"])
    # candidate files: every standalone DICOM except the Otros\ pig MRI, everything under PET\,
    # and the PET-derived formats anywhere (.v ECAT, Analyze .hdr/.img, Amira .am)
    sel = df[((df["a1class"].isin(["dicom-standalone", "dicom-noext"])) & (df["top"] != "Otros"))
             | (df["top"] == "PET")
             | (df["ext"].isin([".v", ".hdr", ".img", ".am"]))]
    dcm_rps = [rp for rp, c in zip(sel["relpath"], sel["a1class"]) if c in ("dicom-standalone", "dicom-noext")]
    with cf.ThreadPoolExecutor(16) as ex:
        hdrs = dict(ex.map(header, dcm_rps))
    rows = []
    for rp, size, sha, cls, top, name, ext in zip(sel["relpath"], sel["size"], sel["sha256"], sel["a1class"],
                                                   sel["top"], sel["name"], sel["ext"]):
        h = hdrs.get(rp, {})
        m = NI_RX.match(name)
        key, ts, mod, algo, recon, frame = "", "", "", "", "", ""
        if m:
            key = f"{m.group('ts')}_{m.group('mod').upper()}_{m.group('algo').upper()}_{m.group('recon')}"
            ts, mod, algo, recon, frame = (m.group("ts"), m.group("mod").upper(), m.group("algo").upper(),
                                           m.group("recon"), m.group("frame") or "")
        elif h.get("Manufacturer", "").startswith("Molecubes"):
            # a Molecubes reconstruction saved under another name (e.g. `CT.dcm.dcm`): its own header
            # gives the acquisition time and modality; it can be matched by bytes and time, not by name
            d_, t_ = (h.get("AcquisitionDate") or h.get("StudyDate", "")), (h.get("AcquisitionTime") or h.get("StudyTime", ""))
            ts = (d_ + re.sub(r"\D", "", t_)[:6]) if d_ and t_ else ""
            mod = {"PT": "PET", "CT": "CT", "NM": "SPECT"}.get(h.get("Modality", ""), "")
        renamed = bool(not m and ts and mod)
        kind = ("molecubes-recon" if (m or renamed) else
                "pmod-export" if h.get("Manufacturer", "").startswith("PMOD") else
                "dicom-other" if cls.startswith("dicom") else
                "pet-derived-volume" if ext in (".v", ".hdr", ".img", ".am", ".nii", ".nii.gz") else cls)
        p_sha = prod.get(sha, ("",))[0]
        p_name = by_key.get(key, []) if key else []
        p_time = by_time.get((ts, mod), []) if (ts and mod) else []
        g_sha = gn_sha.get(sha, "")
        g_key = gn_key.get(key, []) if key else []
        if p_sha:
            cov = "in production (bytes)"
        elif p_name or p_time:
            cov = "in production by name/time, bytes differ"
        elif g_sha:
            cov = "only in the S:\\gnuclear snapshot (bytes), not in production"
        elif g_key:
            cov = "in the S:\\gnuclear snapshot by name only, bytes differ"
        elif m or renamed:
            cov = "NEW: not in production, not in the snapshot"
        else:
            cov = "not a reconstruction (derived/other)"
        rows.append({
            "relpath": rp, "top": top, "size": size, "sha256": sha, "a1class": cls, "kind": kind,
            "ni_key": key or (f"{ts}_{mod}_(renamed)" if renamed else ""), "ts": ts, "modality_name": mod,
            "algo": algo, "recon": recon, "frame": frame,
            "coverage": cov, "prod_acq_sha": p_sha, "prod_acq_name": ";".join(p_name), "prod_acq_time": ";".join(p_time),
            "gnuclear_sha_rel": g_sha, "gnuclear_key_rel": ";".join(g_key[:3]),
            "hdr_modality": h.get("Modality", ""), "hdr_manufacturer": h.get("Manufacturer", ""),
            "hdr_model": h.get("ManufacturerModelName", ""), "hdr_series": h.get("SeriesDescription", ""),
            "hdr_study_date": h.get("StudyDate", ""), "hdr_frames": h.get("NumberOfFrames", ""),
            "hdr_rows_cols": f"{h.get('Rows', '')}x{h.get('Columns', '')}" if h else "",
            "hdr_sop_class": h.get("SOPClassUID", ""), "hdr_software": h.get("SoftwareVersions", ""),
            "hdr_err": h.get("hdr_err", ""), "n_copies": 0, "first_copy": ""})
    # copies by sha inside this selection
    cnt = collections.Counter(r["sha256"] for r in rows)
    seen = set()
    for r in sorted(rows, key=lambda r: ({"PET": 0, "biomaGUNE MJ": 2, "Pili y Mili": 1}.get(r["top"], 3), r["relpath"])):
        r["n_copies"] = cnt[r["sha256"]]
        r["first_copy"] = "Y" if r["sha256"] not in seen else "N"
        seen.add(r["sha256"])
    rows.sort(key=lambda r: r["relpath"])
    write_csv("pet_files.csv", rows, list(rows[0].keys()))
    # summary
    L = []
    recon = [r for r in rows if r["kind"] == "molecubes-recon"]
    L.append(f"files considered: {len(rows):,} ({gb(sum(r['size'] for r in rows)):.2f} GB); Molecubes reconstructions "
             f"{len(recon)} ({gb(sum(r['size'] for r in recon)):.2f} GB), distinct by SHA-256 "
             f"{len({r['sha256'] for r in recon})}")
    L.append("kinds: " + "; ".join(f"{k} {v}" for k, v in collections.Counter(r["kind"] for r in rows).most_common()))
    L.append("header manufacturer/model of the reconstructions: " + str(collections.Counter(
        (r["hdr_manufacturer"], r["hdr_model"]) for r in recon)))
    u = [r for r in recon if r["first_copy"] == "Y"]
    L.append("DISTINCT reconstructions by coverage:")
    for k, v in collections.Counter(r["coverage"] for r in u).most_common():
        b = sum(r["size"] for r in u if r["coverage"] == k)
        L.append(f"   {k:62s} {v:4d}  {gb(b):6.2f} GB")
    L.append("distinct reconstructions per top folder x coverage:")
    for (t, c), v in sorted(collections.Counter((r["top"], r["coverage"]) for r in u).items()):
        L.append(f"   {t:14s} {c:62s} {v}")
    # per PET\<sub> folder (all copies)
    L.append("per folder (PET\\<x>\\<y>, all files):")
    per = collections.defaultdict(collections.Counter)
    for r in rows:
        k = "\\".join(r["relpath"].split("\\")[:3]) if r["top"] == "PET" else "\\".join(r["relpath"].split("\\")[:2])
        per[k][r["coverage"]] += 1
    for k in sorted(per):
        L.append(f"   {k[:80]:80s} " + "; ".join(f"{c.split(':')[0][:40]} {n}" for c, n in per[k].most_common()))
    txt = "\n".join(L)
    with open(out_path("pet_summary.txt"), "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
