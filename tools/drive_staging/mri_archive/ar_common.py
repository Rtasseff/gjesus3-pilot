"""The MRI platform's archive ingest (stream AR): shared paths and helpers.

Source: the LOCAL copies of the archive pulled by `tools/mri_archive.py fetch` to D:\\projects\\gjesus3\\mri_archive\\pull\\
(read-only here: never modified, never extracted into). Nothing in this stream connects to the archive.
Every script writes only under D:\\projects\\gjesus3\\mri_archive\\ (extract\\, out\\, rehearsal_nas\\); w() refuses
anything else, and anything under pull\\. Production (J:\\gjesus3-data) is read-only; the ingest itself writes only to
the --nas-root it is given (the rehearsal root, in this branch).

Gate documents: tasks/drive3_mri_archive_check.md (Part 1), tasks/mri_archive_ingest_gate.md (Part 2).
Census: tasks/mri_archive_census.md. Stream M (repeated here for another source): tasks/drive3_mri_gate.md.
"""
import csv
import hashlib
import io
import os
import sys

sys.dont_write_bytecode = True
csv.field_size_limit(2 ** 31 - 1)

BASE = r"D:\projects\gjesus3\mri_archive"
PULL = os.path.join(BASE, "pull")
FETCH_MANIFEST = os.path.join(PULL, "fetch_manifest.csv")
CENSUS = os.path.join(BASE, "census")
PULL_PLAN = os.path.join(CENSUS, "pull_plan_20261007.csv")
EXTRACT = os.path.join(BASE, "extract")
XMAN = os.path.join(EXTRACT, "_manifests")          # one member list + one .done per extracted study
OUT = os.path.join(BASE, "out")
REH = os.path.join(BASE, "rehearsal_nas")
NAS = r"J:\gjesus3-data"
M_BASE = r"D:\projects\gjesus3\drive3_streams\mri"   # stream M's outputs and staged copy (read-only here)
HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))   # the worktree root
CFG_DIR_REL = "tools/configs/mri_archive"
CFG_DIR = os.path.join(WT, *CFG_DIR_REL.split("/"))
KSPACE = ("fid", "ser")                                         # + rawdata.job<N>
CHUNK = 8 << 20
TIER = {"A:": "A", "A2": "A2", "B:": "B", "C:": "C"}


def tier_of(label):
    return TIER.get(label[:2], "")


def w(*parts):
    """A path under BASE (parent created). Refuses anything outside it, and anything under pull\\."""
    p = os.path.abspath(os.path.join(*parts))
    low = p.lower()
    if not low.startswith(BASE.lower() + os.sep) or low.startswith(PULL.lower() + os.sep) or low == PULL.lower():
        raise RuntimeError(f"refusing to write outside {BASE} or under pull\\: {p}")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def out(name):
    return w(OUT, name)


def lp(path):
    """Long-path form."""
    if os.name != "nt" or path.startswith("\\\\?\\"):
        return path
    ap = os.path.abspath(path)
    if ap.startswith("\\\\"):
        return "\\\\?\\UNC\\" + ap[2:]
    return "\\\\?\\" + ap


def sha256(path):
    h = hashlib.sha256()
    with open(lp(path), "rb") as f:
        for b in iter(lambda: f.read(CHUNK), b""):
            h.update(b)
    return h.hexdigest()


def is_kspace(name):
    n = name.lower()
    return n in KSPACE or n.startswith("rawdata.job")


def rows(path, encoding="utf-8-sig"):
    with io.open(lp(path), encoding=encoding, newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, recs, fields=None):
    fields = fields or (list(recs[0].keys()) if recs else ["empty"])
    with open(path, "w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        wr.writeheader()
        wr.writerows(recs)
    return path


def live_registry(nas=NAS):
    return rows(os.path.join(nas, "registries", "registry_raw.csv"))


def live_projects(nas=NAS):
    return rows(os.path.join(nas, "registries", "registry_projects.csv"))


def pull_plan():
    """{study: census pull-plan row} for the 780 pulled studies (tiers A, A2, B, C), with 'tier' shortened."""
    res = {}
    for r in rows(PULL_PLAN):
        t = tier_of(r["tier"])
        if t:
            res[r["study"]] = {**r, "tier_label": r["tier"], "tier": t}
    return res


def fetched():
    """{study: fetch-manifest row} for every archive verified on local disk now (latest row per study)."""
    res = {}
    for r in rows(FETCH_MANIFEST):
        if r["status"] == "verified" and os.path.isfile(r["local_path"]):
            res[r["study"]] = r
    return res


def study_dir(tier_or_batch, study):
    return os.path.join(EXTRACT, tier_or_batch, study)


def extracted():
    """{study: its .done record} for every study whose extraction completed; 'dir' is where it is NOW (a study may
    have been moved from extract\\_in\\ into its batch folder by ar_04_sort.py)."""
    res = {}
    if not os.path.isdir(XMAN):
        return res
    import json
    homes = [d for d in os.listdir(EXTRACT) if os.path.isdir(os.path.join(EXTRACT, d)) and not d.startswith("_m")]
    for n in os.listdir(XMAN):
        if n.endswith(".done"):
            d = json.load(open(os.path.join(XMAN, n), encoding="utf-8"))
            if not os.path.isdir(d["dir"]):
                hits = [os.path.join(EXTRACT, h, d["study"]) for h in homes
                        if os.path.isdir(os.path.join(EXTRACT, h, d["study"]))]
                d["dir"] = hits[0] if len(hits) == 1 else ""
            res[d["study"]] = d
    return res


def jcamp_get(path, *keys):
    """The values of a few ParaVision JCAMP-DX parameters (##$KEY=value, or ##$KEY=( dims ) and the value on the next
    line(s)), stripped of <> -- the first element of an array. A fast reader for the inventory: tools/ingest/jcampdx
    takes ~0.2 s per file; ar_02_inventory.py --check-parser compares the two on a sample. '' when absent."""
    try:
        with open(lp(path), "r", encoding="latin-1") as f:
            text = f.read()
    except OSError:
        return ["" for _ in keys]
    out = []
    for k in keys:
        i = text.find(f"##${k}=")
        if i < 0:
            out.append("")
            continue
        j = i + len(k) + 4
        end = len(text)
        for stop in ("\n##", "\n$$"):
            e = text.find(stop, j)
            if 0 <= e < end:
                end = e
        v = text[j:end].strip()
        if v.startswith("("):
            close = v.find(")")
            v = v[close + 1:].strip() if close >= 0 else ""
        if v.startswith("<"):
            e = v.find(">")
            v = v[1:e] if e >= 0 else v[1:]
        else:
            v = v.split()[0] if v.split() else ""
        out.append(v.strip())
    return out


def nonimage_marker(exam_dir):
    """ingest/paravision_regen.is_nonimage_exam's rule, with the fast reader: method Method + acqp PULPROG."""
    sig = " ".join(x for x in (jcamp_get(os.path.join(exam_dir, "method"), "Method")[0],
                                jcamp_get(os.path.join(exam_dir, "acqp"), "PULPROG")[0]) if x).lower()
    return next((m for m in ("STEAM", "PRESS", "WOBBLE") if m.lower() in sig), "")


def members(study):
    """The extraction member list of one study (member, kind, size, mtime, sha256, action)."""
    return rows(os.path.join(XMAN, study + ".csv"))


def dcm_prod_name(idx, base):
    """Production's file name for a scanner DICOM pdata/<idx>/dicom/<base> (mri_11_archive_check.py's rule)."""
    import re
    m = re.match(r"^MRIm(?P<n>\d+)\.dcm$", base, re.I)
    return f"recon{idx}_frame{m.group('n').zfill(2)}.dcm" if m else f"recon{idx}_{base}"


def dicom_set_digest(pairs):
    """SHA-256 over the sorted '<production name> <sha256>' lines (stream M's digest, one value per exam)."""
    return hashlib.sha256("\n".join(sorted(f"{n} {h}" for n, h in pairs)).encode()).hexdigest()
