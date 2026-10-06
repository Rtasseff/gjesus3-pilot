"""Place LEONE's NEW content into projects\\DTS24\\working\\historical_drives\\FRIO-X6\\LEONE\\ (Ryan, 2026-10-02).

Layout (accepted by the coordinator 2026-10-04) comes from placement_manifest.csv (s11): header-driven
  LEONE\\<echo|mr_supplements|derived>\\<case from DICOM PatientID>\\<studydate>_<modality>\\[S<n>_<series>\\]<file>
Stream A's module supplies the budget check (<=240 on the UNC measure, components <=255) and the
publishing format (_INDEX.csv, _PATHMAP.csv, README.txt, _ORIGIN.txt), so DTS24 looks like every
other project. Existing _INDEX.csv / _PATHMAP.csv (A's own DTS24 material, if any) are MERGED, never
overwritten; an existing destination file is never overwritten either.

The index carries each file's full original path inside LEONE.zip and its header identity in `note`.
It never carries a patient name or DOB (the manifest has none).

  python s12_place.py --dry-run            # plan + checks, writes the would-be index to the evidence folder
  python s12_place.py --execute --window   # ONLY inside the coordinator's write window
"""
import argparse, csv, hashlib, io, os, sys, time, zipfile

A_MODULE = (r"C:\Users\rtasseff\OneDrive - CIC biomaGUNE\projects\DataInfra\gjesus3-archive\gjesus3-dev"
            r"\drives-nonraw-placement\tools\drive_staging")
sys.path.insert(0, A_MODULE)
import historical_paths as H  # noqa: E402  (read-only import from stream A's worktree, f256a1f)

EVID = r"D:\projects\gjesus3\staging\_analysis\leone-ingest"
SRC_ZIP = r"C:\Users\rtasseff\temp\scratch_leone-ingest\LEONE.zip"
SRC_SHA = "88b4eb462a784de509604b11496c8224838fe50dbc9441137a42a65f0eb8b897"
NAS = r"J:\gjesus3-data"
BASE = r"projects\DTS24\working\historical_drives"
TAG = H.TAGS["D1"]                       # FRIO-X6
ROOT = "LEONE"
KEYP = "D1:LEONE.zip|layout:"            # synthetic node keys: never equal to A's `<drive>:<original path>` keys

LEONE_README = """\
LEONE -- echo, MR supplements and derived files for DTS24
=========================================================

What this folder is
  The part of LEONE.zip (operator drive FRIO X6) that DTS24 did not already
  have. LEONE.zip is the LIONS collaborators' 2021-2023 working set: almost all
  of its MR images are the same images DTS24 already archives (same DICOM
  instance UIDs, identical pixels), so those were NOT copied again.
  Decision: Ryan Tasseff, 2026-10-02 ("clearly part of dts24", no duplicates).

  echo\\            Echocardiography (ultrasound) exams, 36 LIONS cases.
                    These are original scanner output; DTS24's MR archives do
                    not contain them.
  mr_supplements\\  MR objects missing from DTS24's copy of an exam: the
                    3D QFlow series of case 3.02, and Philips "raw data"
                    objects of 28 exams.
  derived\\         Analysis screenshots, key images, reports and
                    presentation states made from the MR/echo.

How the folders are named
  <case>\\<study date>_<modality>\\ ... The case id (LEONE_1.10 etc.) is the
  one written INSIDE each DICOM file. Some of LEONE.zip's own folder names are
  wrong (its "LEONE 1.16" folder holds case 1.10), so they were not used.
  The matching DTS24 MR exam is the acquisition with the same case id and date.

Where each file came from
  ..\\..\\_INDEX.csv: one row per file, with its full path inside LEONE.zip,
  its size and checksum. The `note` column repeats the case id, study date
  and modality read from the file.

Privacy
  These are human clinical images. Like DTS24's own archives, the DICOM files
  keep the patient identifiers in their headers, and echo images may show
  text on screen. Do not copy them outside gjesus3 or share them without the
  Data Office.
"""


def load_manifest():
    with io.open(EVID + r"\placement_manifest.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def plan(rows):
    """-> list of dicts with rel (from share root), plus the checks."""
    out, errs, seen = [], [], set()
    for r in rows:
        below = r["dest_rel"]                                   # echo\LEONE_1.01\20211022_US\file
        rel = "\\".join([BASE, TAG, ROOT, below])
        if H.unc_len(rel) > H.BUDGET:
            errs.append(f"over budget ({H.unc_len(rel)}): {rel}")
        if any(len(c) > H.COMPONENT_MAX for c in rel.split("\\")):
            errs.append(f"component > {H.COMPONENT_MAX}: {rel}")
        if rel.lower() in seen:
            errs.append(f"duplicate destination: {rel}")
        seen.add(rel.lower())
        member = r["source_member_in_LEONE_zip"]
        out.append({**r, "rel": rel, "member": member})
    return out, errs


def index_and_pathmap(items):
    idx, nodes = [], {}
    for it in items:
        new_path = it["rel"][len(BASE) + 1:]                    # FRIO-X6\LEONE\echo\...
        orig = H.original_display("D1", "LEONE.zip", "LEONE.zip", it["member"].replace("!/", H.NESTED_SEP))
        note = (f"case {it['case_id_from_header']} (from DICOM PatientID); {it['category']}; "
                f"study {it['study_date']} {it['modality']}"
                + (f"; series {it['series_number']} {it['series_description']}".rstrip() if it["category"] == "mr_supplements" else ""))
        idx.append({"new_path": new_path, "drive": H.DRIVE_LABELS["D1"], "archive": "LEONE.zip",
                    "original_path": orig, "size": it["size"], "sha256": it["sha256"],
                    "claim_id": "LEONE->DTS24", "shortened": "N", "note": note})
        parts = new_path.split("\\")
        for i in range(1, len(parts) - 1):                      # every folder below the tag
            rendered = "\\".join(parts[: i + 1])
            nodes[KEYP + "\\".join(parts[1: i + 1])] = rendered
    return idx, [{"node_key": k, "rendered": v} for k, v in sorted(nodes.items())]


def merge_csv(path, new_rows, key, fields):
    """Existing rows (A's) + ours. A clash on the key is an error, never a silent overwrite."""
    old = []
    if os.path.exists(path):
        with io.open(path, encoding="utf-8-sig", newline="") as f:
            old = list(csv.DictReader(f))
    have = {r[key].lower(): r for r in old}
    clash = [r[key] for r in new_rows if r[key].lower() in have and have[r[key].lower()] != r]
    merged = {r[key].lower(): r for r in old}
    merged.update({r[key].lower(): r for r in new_rows})
    return [merged[k] for k in sorted(merged)], len(old), clash


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--window", action="store_true", help="assert: the coordinator granted the write window")
    a = ap.parse_args()
    if a.execute and not a.window:
        sys.exit("refusing: --execute needs --window (the coordinator's write window)")
    rows = load_manifest()
    items, errs = plan(rows)
    idx, pm = index_and_pathmap(items)
    base_abs = os.path.join(NAS, BASE)
    idx_path, pm_path = os.path.join(base_abs, H.INDEX_NAME), os.path.join(base_abs, H.PATHMAP_NAME)
    m_idx, n_old_idx, clash_idx = merge_csv(idx_path, idx, "new_path", H.INDEX_FIELDS)
    m_pm, n_old_pm, clash_pm = merge_csv(pm_path, pm, "node_key", ["node_key", "rendered"])
    exists = [it["rel"] for it in items if os.path.exists(os.path.join(NAS, it["rel"]))]
    by = {}
    for it in items:
        c = by.setdefault(it["category"], [0, 0, set()])
        c[0] += 1; c[1] += int(it["size"]); c[2].add(it["case_id_from_header"])
    print(f"destination tree : {base_abs}\\{TAG}\\{ROOT}\\  (exists now: {os.path.exists(os.path.join(base_abs, TAG, ROOT))})")
    print(f"files            : {len(items)}  GB {sum(int(i['size']) for i in items)/1e9:.2f}")
    for k, (n, b, cs) in sorted(by.items()):
        print(f"  {k:15} {n:6d} files {b/1e9:7.2f} GB  cases {len(cs)}")
    print(f"longest UNC path : {max(H.unc_len(i['rel']) for i in items)} (budget {H.BUDGET})")
    print(f"budget/component/duplicate errors: {len(errs)}")
    print(f"destination files already present: {len(exists)}")
    print(f"_INDEX.csv  : {n_old_idx} existing rows + {len(idx)} ours -> {len(m_idx)}; key clashes {len(clash_idx)}")
    print(f"_PATHMAP.csv: {n_old_pm} existing rows + {len(pm)} ours -> {len(m_pm)}; key clashes {len(clash_pm)}")
    print(f"README.txt at base exists: {os.path.exists(os.path.join(base_abs, H.README_NAME))}")
    for e in errs[:10]:
        print("  ERR", e)
    bad = errs or exists or clash_idx or clash_pm
    # dry-run artefacts in the evidence folder (no identifiers)
    H.write_index(EVID + r"\dryrun_INDEX.csv", m_idx)
    H.write_pathmap(EVID + r"\dryrun_PATHMAP.csv", m_pm)
    if a.dry_run or not a.execute:
        print("DRY RUN: nothing written to J:. Would-be index/pathmap in the evidence folder.")
        return 1 if bad else 0
    if bad:
        sys.exit("refusing to execute: fix the errors above first")

    # ---- execute (window only)
    zh = hashlib.sha256()
    with open(SRC_ZIP, "rb") as f:
        for b in iter(lambda: f.read(16 << 20), b""):
            zh.update(b)
    if zh.hexdigest() != SRC_SHA:
        sys.exit("source LEONE.zip copy does not match the drive manifest SHA-256")
    z = zipfile.ZipFile(SRC_ZIP)
    nested = {}
    log = open(EVID + r"\place_execute.log", "a", encoding="utf-8")
    t0 = time.time(); done = errors = 0
    for it in items:
        m = it["member"]
        if "!/" in m:
            outer, inner = m.split("!/", 1)
            if outer not in nested:
                nested[outer] = zipfile.ZipFile(io.BytesIO(z.read(outer)))
            data = nested[outer].read(inner)
        else:
            data = z.read(m)
        if hashlib.sha256(data).hexdigest() != it["sha256"]:
            errors += 1; log.write(f"SRC_SHA_MISMATCH\t{m}\n"); continue
        dst = os.path.join(NAS, it["rel"])
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            errors += 1; log.write(f"EXISTS\t{dst}\n"); continue
        tmp = dst + ".partial"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, dst)                                    # new file only (checked absent above)
        if sha_file(dst) != it["sha256"]:
            errors += 1; log.write(f"DST_SHA_MISMATCH\t{dst}\n"); continue
        done += 1
        if done % 500 == 0:
            print(f"  {done}/{len(items)} copied+verified, {errors} errors, {time.time()-t0:.0f}s", flush=True)
    # publishing files last, so an interrupted run never leaves an index that claims missing files
    root_abs = os.path.join(base_abs, TAG, ROOT)
    with io.open(os.path.join(root_abs, H.README_NAME), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(LEONE_README)
    with io.open(os.path.join(root_abs, H.ORIGIN_NAME), "w", encoding="utf-8", newline="") as f:
        f.write(H.origin_text([H.original_display("D1", "LEONE.zip")]))
    if not os.path.exists(os.path.join(base_abs, H.README_NAME)):
        with io.open(os.path.join(base_abs, H.README_NAME), "w", encoding="utf-8", newline="\r\n") as f:
            f.write(H.PROJECT_README)
    H.write_index(idx_path, m_idx)
    H.write_pathmap(pm_path, m_pm)
    print(f"DONE: {done} copied+verified, {errors} errors, {time.time()-t0:.0f}s", flush=True)
    log.write(f"DONE\t{done}\t{errors}\n"); log.close()
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
