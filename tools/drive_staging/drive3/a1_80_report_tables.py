"""A1 step 8: the side checks and the tables quoted in tasks/drive3_raw_coverage.md, from the A1 outputs.

Reads only a1\\ outputs (and the a1\\_inputs\\ snapshots). Writes a1\\report_tables.txt.

    python a1_80_report_tables.py
"""
import collections
import os

import pandas as pd

from a1_common import OUT, cache_load, out_path

BS = "\\"
L = []


def p(*a):
    L.append(" ".join(str(x) for x in a))


def table(df):
    L.append(df.to_string())


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 500)
    pd.set_option("display.max_colwidth", 80)
    files = cache_load("files")
    ex = pd.read_csv(os.path.join(OUT, "mri_exams.csv"), dtype=str, keep_default_na=False)
    for c in ("n_dcm", "dcm_bytes", "bytes", "distinct_bytes_all_copies", "n_copies"):
        ex[c] = ex[c].astype(int)
    copies = cache_load("mri_copies")

    p("== 1. Whole drive, raw vs production (decimal GB)")
    raw = files[files["a1class"].isin(["mri-dicom", "mri-2dseq", "mri-kspace", "mri-params", "mri-study-params",
                                       "dicom-standalone", "dicom-noext", "microscopy-czi", "microscopy-lif"])]
    p(f"files {len(files):,} {files['size'].sum()/1e9:.1f} GB; in prod raw {int(files['in_prod_raw'].sum()):,} "
      f"{files.loc[files['in_prod_raw'], 'size'].sum()/1e9:.1f} GB")
    p(f"zero-byte files: {int((files['size'] == 0).sum())}; of them in raw classes: "
      + str(files[(files['size'] == 0)].groupby('a1class').size().to_dict()))
    z = files[(files["size"] == 0) & files["a1class"].isin(["mri-dicom", "mri-kspace", "mri-2dseq"])]
    for rp in z["relpath"]:
        p("   zero-byte raw file:", rp)

    p("\n== 2. MRI exam copies")
    sd = collections.defaultdict(set)
    for c in copies.values():
        sd[c["study"]].add(c["study_dir"])
    p(f"study names {len(sd)}; with 2 copies {sum(1 for v in sd.values() if len(v) > 1)}; copy places: "
      + str(collections.Counter(" + ".join(sorted({x.split(BS)[0] for x in v})) for v in sd.values() if len(v) > 1)))
    p("vs canonical: " + str(collections.Counter(c["vs_canonical"].split(" (")[0] for c in copies.values())))
    p("exam folders per top folder: " + str(collections.Counter(c["top"] for c in copies.values())) +
      "; canonical copies per top folder: " + str(collections.Counter(c["top"] for c in copies.values() if c["canonical"])))
    exk = ex.copy()
    exk["tops"] = exk["tops"].fillna("")
    p("exam keys by the top folders their copies sit in: " + str(exk["tops"].value_counts().to_dict()))
    dv = [c for c in copies.values() if c["vs_canonical"].startswith("divergent")]
    p("divergent copies by study: " + str(collections.Counter(c["study"] for c in dv)))

    p("\n== 3. MRI classes")
    table(ex.groupby(["class", "class_detail"]).agg(exams=("exam_key", "size"),
                                                      studies=("study", "nunique")))
    st = ex.groupby("study")["class"].agg(lambda s: "".join(sorted(set(s))))
    p("studies by the set of exam classes they hold: " + str(st.value_counts().to_dict()))
    inprod_st = st[st.str.contains("a|b")]
    p(f"studies with any exam in production: {len(inprod_st)}; every exam byte-identical (a only): "
      f"{int((inprod_st == 'a').sum())}; holding some (b): {int(inprod_st.str.contains('b').sum())}")
    bdet = ex[ex["class"] == "b"].groupby("study")["class_detail"].agg(lambda s: "; ".join(sorted({x.split(' (')[0] for x in s})))
    p("studies with (b) exams, by reason set: " + str(bdet.value_counts().to_dict()))
    c_ = ex[ex["class"] == "c"]
    miss = c_.apply(lambda r: len(set(x for x in r.seq_recons.split(";") if x) - set(x for x in r.dcm_recons.split(";") if x)), axis=1)
    p(f"class c exams with a reconstruction that has 2dseq but no DICOM: {(miss > 0).sum()} "
      f"(studies: {c_[miss > 0]['study'].nunique()})")
    new = ex[ex["class"].isin(["c", "d", "e"])]
    dset = set(ex[ex["class"] == "d"]["canonical_dir"])
    seq_b = files[(files["a1class"] == "mri-2dseq") & files["exam_dir"].isin(dset)]["size"].sum()
    p(f"class d (convertible): 2dseq bytes in their canonical copies {seq_b/1e9:.2f} GB "
      f"(the DICOM Dicomifier writes is of that order; not measured)")
    p(f"class c: DICOM bytes {c_dcm/1e9:.2f} GB" if (c_dcm := ex[ex['class'] == 'c']['dcm_bytes'].sum()) else "")
    p("new exams by scanner station: " + str(new.groupby("station").size().to_dict()))
    p("new 11.7T (BIOSPEC 500) studies: " + "; ".join(sorted(new[new["station"] == "BIOSPEC 500"]["study"].unique())))

    p("\n== 4. production project vs the drive's folder claim, exams in production")
    projects = pd.read_csv(os.path.join(OUT, "_inputs", "registry_projects.csv"), dtype=str, keep_default_na=False)
    code_of = {r.project_id: r["name"].replace("AE-biomaGUNE-", "") for _, r in projects.iterrows()}
    inp = ex[ex["class"].isin(["a", "b"])].copy()
    inp["prod_code"] = inp["prod_project"].map(lambda x: code_of.get(x, "(blank)") if x else "(blank)")
    inp["agree"] = inp.apply(lambda r: "no claim" if not r.path_claim_nearest else (
        "agree" if r.prod_code in r.path_claim_nearest.split(";") else "differ"), axis=1)
    table(inp.groupby(["agree", "prod_code", "path_claim_nearest"]).agg(exams=("exam_key", "size"),
                                                                        studies=("study", "nunique")))
    mic = pd.read_csv(os.path.join(OUT, "microscopy_files.csv"), dtype=str, keep_default_na=False)
    reg = pd.read_csv(os.path.join(OUT, "_inputs", "registry_raw.csv"), dtype=str, keep_default_na=False).set_index("acq_id")
    mi = mic[mic["in_prod_raw"] == "Y"].copy()
    mi["prod_code"] = mi["prod_acq_id"].map(lambda a: code_of.get(reg["project_id"].get(a, ""), "(blank)"))
    mi["agree"] = mi.apply(lambda r: "no claim" if not r.claim_code else ("agree" if r.prod_code == r.claim_code else "differ"), axis=1)
    p("microscopy files in production, production project vs path claim:")
    table(mi.groupby(["agree", "prod_code", "claim_code"]).size().to_frame("files"))

    p("\n== 5. retired acquisitions")
    t = pd.read_csv(os.path.join(OUT, "_inputs", "retired_acquisitions.csv"), dtype=str, keep_default_na=False)
    rs = {s: r.disposition for _, r in t.iterrows() for s in str(r.sha256).replace(";", " ").split() if len(s) == 64}
    hit = files[files["sha256"].isin(rs)]
    p(f"drive files byte-identical to a retired acquisition: {len(hit)}: "
      + "; ".join(f"{rp} ({rs[s]})" for rp, s in zip(hit["relpath"], hit["sha256"])))

    p("\n== 6. MRI not in production, by project and year (studies with any exam not in production)")
    ms = pd.read_csv(os.path.join(OUT, "mri_missing_studies.csv"), dtype=str, keep_default_na=False)
    for c in ("exams_not_in_prod", "c_native_dicom", "d_convertible", "e_not_convertible", "a_b_in_prod",
              "distinct_bytes_new_exams", "dcm_bytes_new"):
        ms[c] = ms[c].astype(int)

    def agg(g):
        return pd.Series({"studies": len(g), "exams": g.exams_not_in_prod.sum(), "c": g.c_native_dicom.sum(),
                          "d": g.d_convertible.sum(), "e": g.e_not_convertible.sum(),
                          "GB_source": round(g.distinct_bytes_new_exams.sum() / 1e9, 1),
                          "GB_dicom": round(g.dcm_bytes_new.sum() / 1e9, 2)})
    for keys in (["decided_code", "year"], ["year"], ["regex_parse"], ["initials"], ["verdict"], ["stations"]):
        table(ms.groupby(keys).apply(agg, include_groups=False))
    table(agg(ms).to_frame("all").T)

    def who(r):
        s = (r.canonical_location + "\\" + r.study).lower()
        if "ermal" in s:
            return "Ermal (study name)"
        if "lucia" in s or "lucía" in s:
            return "Lucia (folder name)"
        if "_mj" in s or " mj" in s or "mj\\" in s:
            return "MJ (folder name)"
        return "(none in the path)"
    ms["researcher_in_path"] = ms.apply(who, axis=1)
    table(ms.groupby(["researcher_in_path"]).apply(agg, include_groups=False))

    p("\n== 7. PET/CT reconstructions (distinct), by coverage and folder")
    pet = pd.read_csv(os.path.join(OUT, "pet_files.csv"), dtype=str, keep_default_na=False)
    pr = pet[(pet["kind"] == "molecubes-recon") & (pet["first_copy"] == "Y")].copy()
    pr["size"] = pr["size"].astype(int)
    pr["folder"] = pr["relpath"].map(lambda s: BS.join(s.split(BS)[:3]))
    table(pr.groupby(["coverage", "folder"]).agg(files=("size", "size"), GB=("size", lambda s: round(s.sum() / 1e9, 2)),
                                                 dates=("ts", lambda s: ",".join(sorted({x[:8] for x in s}))[:60])))

    p("\n== 8. microscopy (distinct files), by folder x instrument x status")
    mic["size"] = mic["size"].astype(int)
    u = mic.drop_duplicates("sha256").copy()
    u["status"] = u["vs_production"].map(lambda v: "byte-identical" if v.startswith("byte") else
                                         ("re-save" if v.startswith("re-save") else "new"))
    u["folder"] = u["relpath"].map(lambda s: BS.join(s.split(BS)[:3]))
    table(u.groupby(["folder", "instrument", "status"]).agg(files=("size", "size"),
                                                           GB=("size", lambda s: round(s.sum() / 1e9, 1))))
    table(u[u["status"] == "new"].groupby(["instrument", "claim_verdict"]).agg(
        files=("size", "size"), GB=("size", lambda s: round(s.sum() / 1e9, 1))))
    g = mic[mic["same_ts_group_distinct"].replace("", "0").astype(int) > 1]
    p(f"same-timestamp groups with >1 distinct file: {g.groupby(['instrument', 'acq_dt']).ngroups} groups, "
      f"{len(g)} files, of which not in production {int((g['in_prod_raw'] == 'N').sum())}")
    ext = u[(u["instrument"] == "unknown") & (u["serials"] == "4661000340")]
    p(f"Axioscan 7 serial 4661000340: {len(ext)} distinct files, {ext['size'].sum()/1e9:.1f} GB, acquired "
      f"{ext['acq_dt'].min()[:10]} .. {ext['acq_dt'].max()[:10]}; ZEN users: "
      + str(collections.Counter(ext['zen']).most_common(3)))
    txt = "\n".join(L)
    with open(out_path("report_tables.txt"), "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
