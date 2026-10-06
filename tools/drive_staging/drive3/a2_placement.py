#!/usr/bin/env python3
"""a2_placement.py -- HANDOFF §6 items 4 and 5: the non-raw placement plan for drive 3 (M. Jesus).

READ-ONLY PLAN. Nothing is copied. It reads a2\\files.csv, a2\\claims\\, the live registries and, for
the destination rule, each target tree's _PATHMAP.csv / _INDEX.csv on the NAS (frozen names). It writes
only to D:\\projects\\gjesus3\\drive3_analysis\\a2\\placement\\.

WHAT IT DECIDES, per A2 file (non-raw; A1 owns the raw imaging, a2_common.classify):
  deferred-biomaGUNE-MJ   the researcher's own folder: inventory only now (HANDOFF §4, "biomaGUNE MJ
                          comes last"); still used as a twin for the dedup facts
  exclude-zero-byte       counted, not placed (drives 1+2 rule)
  in-raw                  the exact bytes are an acquisition file in /raw/
  already-placed          the exact bytes are already in the SAME project (drives 1+2 placement)
  placed-elsewhere        the exact bytes are placed in ANOTHER project by drives 1+2; drive 3's claim
                          names this one (listed for Ryan; not placed by default)
  already-in-holding      no project, and the bytes are already in the drives-1+2 holding folder
  covered-by-twin         no project, but the same bytes are placed through another drive-3 copy that
                          has one (that copy carries the evidence; this one is only an extra copy)
  duplicate-copy          has a project, but the dedup rule (--dedup) places another copy of the bytes
  place                   into <project>\\working\\historical_drives\\MJesus-MFB\\<study folder>\\...
  place-after-reopen      the project is AE-biomaGUNE-1121, closed; Ryan ruled it reopened (2026-09-30)
  closed-project          the project is closed and no reopen is ruled (Ryan's call)
  holding                 no project: staging\\historical_drives_unassigned\\MJesus-MFB\\<full path>
  holding-nmr             TopSpin (HR-MAS) NMR: holding, as Ryan ruled for NMR on 2026-10-02

TWO SCENARIOS, side by side:
  engine        the claims engine's per-file verdicts as they are (Ryan's rule of 2026-09-29);
  recommended   engine + the READINGS below, each evidence-based and listed for Ryan's approval
                (nothing in the engine is changed; a reading only fills a project the engine left blank).

READINGS (applied only in the recommended scenario):
  R1  `Pili y Mili\\Proyecto 0522  PAH` failed the engine's claim-level cross-check (CL-1344) because
      of its IFs and histologies subfolder; every file there WITHOUT contrary evidence of its own is read
      as 0522 (a file whose animal is not 0522's, or predates that animal's birth, stays C).
  R2  `1010-3 MTCOI and TOM20` is the (A) correction 1010 -> 1019 inside `Machos viejos-1019-3`; the
      engine counted the identical outer 1019 as a disagreement. Read as 1019.
  R3  a YYMM folder token (2302, 2305, 2306, 2311) that the engine itself reports "reads as a date close
      to its files' dates" shadows a valid outer claim; read the outer claim.
  R4  folders with no code, decided by evidence (a2 report §5):
        R4a PET\\FDG-ratonesfumadores -> AE-biomaGUNE-1122 (production registers all 69 of its PET/CT
            acquisitions to PROJ-0057);
        R4b Otros\\Segmentaciones ITK SNAP\\Segmentacion 2DG RATAS -> the 0118 rats (study folder names
            identical to MRI\\Proyecto 0118 (Ratas hipoxia) studies); R4b-weak: same day/series, the
            study itself is not on the drive;
        R4c MRI\\Comparasion expiration vs inspiraiton\\Rata MCT -> the 0118 rats, same test (R4c-weak).

DEDUP (--dedup), for copies of identical bytes bound for the same project (or the holding folder):
  all      place every copy (the drives 1+2 precedent: structure over bytes);
  study    (default) one study folder per content, every copy inside that folder kept: no twin study
           folders, each kept folder complete; the canonical copy is the one under the OUTERMOST study
           folder, then the shared group folders before `biomaGUNE MJ`, then the shallower path;
  project  one copy per project.

    python tools/drive_staging/drive3/a2_placement.py [--dedup all|study|project]
"""
import argparse
import collections
import json
import os
import re

import a2_common as C
import nonraw_placement as NP  # noqa: E402  (promote_root / PARENT_GROUP_PROJECTS: the shared root rule)

H = C.H
OUT = os.path.join(C.OUT, "placement")
HYPOXIA = "MRI\\Proyecto 0118 (Ratas hipoxia)\\"
MONO = "Pili y Mili\\Proyecto 0118 Monocrotalina\\"
P0118_HIP = "Proyecto-0118-rats-hipoxia"       # ruled 2026-09-30, new
P0118_MONO = "Proyecto-0118-Monocrotalina"     # ruled 2026-09-30, new (option R)
P0118 = "AE-biomaGUNE-0118"                    # PROJ-0060, exists, described as Monocrotalina (option E)
RULED_REOPEN = {"AE-biomaGUNE-1121"}
STUDY_RE = re.compile(r"\d{8}_\d{6}_[^\\]+?_\d+_\d+")
DATE_TOKEN_EVIDENCE = "reads as a date close to its files' dates"
NO_CODE_ROOTS = {
    "R4a": ("PET\\FDG-ratonesfumadores", "AE-biomaGUNE-1122"),
    "R4b": ("Otros\\Segmentaciones ITK SNAP\\Segmentacion 2DG RATAS", P0118_HIP),
    "R4c": ("MRI\\Comparasion expiration vs inspiraiton\\Rata MCT", P0118_HIP),
}


def engine_project(f):
    """The engine's per-file project (Ryan's rule). (B): 0521 is Project-0521, and 0720 folds into it
    (Ryan 2026-10-02); any other (B) is not approved -> no project."""
    v, p = f["verdict"], f["proposed_project"]
    if v in ("CONFIRMED", "A") and p:
        return p
    if v == "B":
        return "Project-0521" if p in ("Project-0521", "Project-0720") else ""
    if v == "C" and re.search(r"(?i)antiguo proyecto 0720", f["relpath"]):
        return "Project-0521"
    return ""


def build_claim_roots(claims, projects):
    """normalised claim-root segments -> {projects} (a root can carry two codes: `Proyecto 1019 + 1121`).
    A SHADOWED claim counts for AE-biomaGUNE-<token> when that token is Confirmed elsewhere on the drive."""
    confirmed = {c["token"] for c in claims if c["verdict"] in ("CONFIRMED", "A")}
    roots = collections.defaultdict(set)
    fn_roots = set()
    shadow_used = 0
    for c in claims:
        v, p = c["verdict"], c["proposed_project"]
        proj = ""
        if v in ("CONFIRMED", "A") and p:
            proj = p
        elif v == "B" and p in ("Project-0521", "Project-0720"):
            proj = "Project-0521"
        elif v == "SHADOWED" and c["token"] in confirmed and f"AE-biomaGUNE-{c['token']}" in projects:
            proj = f"AE-biomaGUNE-{c['token']}"
            shadow_used += 1
        if proj:
            key = H.claim_root_segments(c["claim_root"])
            roots[key].add(proj)
            if c["source"] in ("filename", "archive-member-filename"):
                fn_roots.add(key)
    return roots, fn_roots, shadow_used


def root_for(relpath, project, roots, fn_roots, use_shadow=True, shadow_keys=frozenset()):
    """The study folder: the OUTERMOST claim root of the file's project on its path (historical_paths
    rule), with Ryan's "group under the parent" for the PARENT_GROUP_PROJECTS (nonraw_placement)."""
    segs = H.logical_segments(relpath)
    names = [H.norm(n) for n, _k in segs]
    kinds = [k for _n, k in segs]
    for i in range(len(names) - 1):
        key = tuple(names[: i + 1])
        if project in roots.get(key, ()) and (use_shadow or key not in shadow_keys):
            if project in NP.PARENT_GROUP_PROJECTS:
                i = NP.promote_root(names, kinds, i, key in fn_roots, code=project[-4:])
            return tuple(names[: i + 1])
    return None


def contradicted_0522(f, cache, is_data):
    """R1: does this file's OWN evidence contradict 0522 (the engine's per-file test)?"""
    tok = f["animal_token"]
    if not tok:
        return False
    m = re.search(r"(\d+)", tok)
    v = cache.get(f"0522|{int(m.group(1))}")
    if not v:
        return False
    if v["status"] != "found":
        return True
    d = f["mtime"][:10]
    return bool(d and v.get("dob") and is_data(f["relpath"].split("\\")[-1]) and d < v["dob"][:10])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dedup", choices=["all", "study", "project"], default="study",
                    help="copies of the same bytes for one project: all / one study folder per content / one copy per project")
    args = ap.parse_args()
    C.stdout_utf8()
    os.makedirs(OUT, exist_ok=True)
    log = []

    def say(m=""):
        log.append(m)
        print(m, flush=True)

    projects = C.load_projects()
    files = list(C.it(os.path.join(C.OUT, "files.csv")))
    fclaims = {r["relpath"]: r for r in C.it(os.path.join(C.OUT, "claims", "file_claims.csv"))}
    for f in files:
        f["animal_token"] = fclaims.get(f["relpath"], {}).get("animal_token", "")
    claims = list(C.it(os.path.join(C.OUT, "claims", "claims.csv")))
    cl_by_id = {c["claim_id"]: c for c in claims}
    with open(os.path.join(C.OUT, "claims", "db_cache.json"), encoding="utf-8") as fh:
        cache = json.load(fh)
    import project_claims as PC  # is_data: the engine's own "raw imaging / acquisition file" test
    roots, fn_roots, shadow_used = build_claim_roots(claims, projects)
    shadow_keys = {H.claim_root_segments(c["claim_root"]) for c in claims if c["verdict"] == "SHADOWED"}
    say(f"claim roots: {len(roots)} (of which {shadow_used} SHADOWED outer folders counted for their own code)")
    by_sha = collections.defaultdict(list)
    for f in files:
        by_sha[f["sha256"]].append(f)
    studies_0118 = set()
    for f in files:
        if f["relpath"].startswith(HYPOXIA):
            studies_0118.update(m.group(0) for m in STUDY_RE.finditer(f["relpath"]))
    a2 = [f for f in files if f["owner"] == "A2"]
    say(f"A2 files: {len(a2):,} ({C.gb(sum(int(f['size']) for f in a2))} GB)")

    # ---- targets: engine and recommended ----------------------------------------------------------
    for f in a2:
        ep = engine_project(f)
        reading, rp = "", ""
        if not ep:
            if f["claim_id"] == "CL-1344":
                if not contradicted_0522(f, cache, PC.is_data):
                    reading, rp = "R1", "AE-biomaGUNE-0522"
            elif f["claim_id"] == "CL-0772":
                reading, rp = "R2", "AE-biomaGUNE-1019"
            else:
                m = re.match(r"nested claims disagree: nearest (\d{4}) \(C\) vs outer (\d{4}); nearest is unresolved", f["conflict"])
                c = cl_by_id.get(f["claim_id"])
                if m and c and DATE_TOKEN_EVIDENCE in c["evidence"] and f"AE-biomaGUNE-{m.group(2)}" in projects:
                    reading, rp = "R3", f"AE-biomaGUNE-{m.group(2)}"
            for rid, (prefix, proj) in NO_CODE_ROOTS.items():
                if not reading and f["relpath"].startswith(prefix + "\\"):
                    if rid == "R4a":
                        reading, rp = rid, proj
                    else:
                        st = [m.group(0) for m in STUDY_RE.finditer(f["relpath"])]
                        strong = any(s in studies_0118 for s in st)
                        reading, rp = (rid if strong else rid + "-weak"), proj
        f["engine_project"] = ep
        f["reading"] = reading
        f["rec_project"] = ep or rp
        # the 0118 split (ruled 2026-09-30): by source subtree
        for key in ("engine_project", "rec_project"):
            if f[key] == P0118:
                f[key] = P0118_MONO if f["relpath"].startswith(MONO) else P0118_HIP

    # ---- decisions --------------------------------------------------------------------------------
    def status_of(p):
        if p in (P0118_HIP, P0118_MONO):
            return "new (ruled 2026-09-30)"
        row = projects.get(p)
        return (row["status"] if row else "NOT IN REGISTRY")

    def folder_of(p):
        row = projects.get(p)
        return C.project_folder_name(row) if row else p   # a new project: folder == name (05 §2a)

    def first_decision(f, proj):
        if f["top"] == "biomaGUNE MJ":
            return "deferred-biomaGUNE-MJ"
        if int(f["size"]) == 0:
            return "exclude-zero-byte"
        if f["in_raw"]:
            return "in-raw"
        if f["cls"] == "nmr-topspin":
            return "holding-nmr" if not f["holding12"] else "already-in-holding"
        placed = set(f["placed12"].split(";")) - {""}
        if proj:
            if folder_of(proj) in placed or (proj in (P0118_HIP, P0118_MONO) and "AE-biomaGUNE-0118" in placed):
                return "already-placed"
            if placed:
                return "placed-elsewhere"
            st = status_of(proj)
            if st == "closed":
                return "place-after-reopen" if proj in RULED_REOPEN else "closed-project"
            return "place"
        if placed:
            return "already-placed"
        if f["holding12"]:
            return "already-in-holding"
        return "unattributed"

    PLACED = ("place", "place-after-reopen", "closed-project")

    def order_for(scen):
        def order(x):
            """Canonical copy: the one under the OUTERMOST study folder (a project folder beats a file-name
            claim's own folder), then the shared group folders before the researcher's own, then the
            shallower path, then the name."""
            rk = x.get(f"root_{scen}", "")
            depth = len(rk.split("|")) if rk and rk != "-" else 99
            return (depth, C.TOP_ORDER.index(x["top"]) if x["top"] in C.TOP_ORDER else 9,
                    x["relpath"].count("\\"), x["relpath"].lower())
        return order

    def plan_scenario(scen):
        pkey = "engine_project" if scen == "engine" else "rec_project"
        for f in a2:
            f[f"dec_{scen}"] = first_decision(f, f[pkey])
        # content level: an unattributed copy whose bytes are placed through a copy that has a project
        placed_shas = set()
        for f in a2:
            if f[f"dec_{scen}"] in PLACED + ("already-placed",):
                placed_shas.add(f["sha256"])
        for f in a2:
            if f[f"dec_{scen}"] == "unattributed":
                f[f"dec_{scen}"] = "covered-by-twin" if f["sha256"] in placed_shas else "holding"
        # the study folder of every copy to be placed
        for f in a2:
            f[f"root_{scen}"] = ""
            if f[f"dec_{scen}"] not in PLACED:
                continue
            rp = f[pkey]
            rproj = P0118 if rp in (P0118_HIP, P0118_MONO) and not (scen == "rec" and f["reading"]) else rp
            if scen == "rec" and f["reading"].startswith("R4"):
                rid = f["reading"].split("-")[0]
                f["root_rec"] = "|".join(H.norm(s) for s in NO_CODE_ROOTS[rid][0].split("\\"))
                continue
            r = root_for(f["relpath"], rproj, roots, fn_roots)
            f[f"root_{scen}"] = "|".join(r) if r else "-"
            if scen == "rec":
                r0 = root_for(f["relpath"], rproj, roots, fn_roots, use_shadow=False, shadow_keys=shadow_keys)
                f["root_noshadow"] = "|".join(r0) if r0 else "-"
        # copies of identical bytes bound for one project (or the holding folder):
        #   all      every copy (drives 1+2 precedent: structure over bytes)
        #   study    one study folder per content, every copy inside it kept (no cross-folder twins)
        #   project  one copy per project
        order = order_for(scen)
        g_proj = collections.defaultdict(list)
        for f in a2:
            if f[f"dec_{scen}"] in PLACED + ("holding",):
                g_proj[(f[pkey] or "(holding)", f["sha256"])].append(f)
        for fs in g_proj.values():
            fs.sort(key=order)
            best_root = fs[0][f"root_{scen}"]
            for i, x in enumerate(fs):
                x[f"keep_project_{scen}"] = i == 0
                x[f"keep_study_{scen}"] = x[f"root_{scen}"] == best_root
                x[f"canonical_{scen}"] = fs[0]["relpath"] if i else ""
        res = {}
        for opt in ("all", "study", "project"):
            n = b = 0
            for f in a2:
                if f[f"dec_{scen}"] not in PLACED + ("holding",):
                    continue
                if opt == "all" or f[f"keep_{opt}_{scen}"]:
                    n += 1
                    b += int(f["size"])
            res[opt] = (n, b)
        for f in a2:
            if f[f"dec_{scen}"] in PLACED + ("holding",) and args.dedup != "all" \
                    and not f[f"keep_{args.dedup}_{scen}"]:
                f[f"dec_{scen}"] = "duplicate-copy"
        return res

    say(f"\nDEDUP OPTIONS (copies of identical bytes that one project, or the holding folder, would receive); chosen: {args.dedup}")
    for scen in ("engine", "rec"):
        res = plan_scenario(scen)
        for opt, (n, b) in res.items():
            say(f"  {scen:7s} {opt:8s} {n:7,d} files {C.gb(b):>8s} GB")

    # ---- destinations (recommended scenario) ------------------------------------------------------------
    trees = collections.defaultdict(list)
    for f in a2:
        d = f["dec_rec"]
        if d in ("place", "place-after-reopen", "closed-project"):
            trees["\\".join(["projects", folder_of(f["rec_project"]), "working", "historical_drives"])].append(f)
        elif d in ("holding", "holding-nmr"):
            trees[NP.HOLDING_BASE].append(f)
    say("\nDESTINATIONS (historical_paths.Planner, tag MJesus-MFB, budget 240)")
    lens, nshort, failed = [], 0, []
    scatter = {}
    short_rows, study_rows = [], []
    for base, fs in sorted(trees.items()):
        p = H.Planner(base)
        p.load_pathmap(os.path.join(C.NAS, base, H.PATHMAP_NAME))
        p.load_index(os.path.join(C.NAS, base, "manifest.csv" if base == NP.HOLDING_BASE else H.INDEX_NAME))
        items = []
        for i, f in enumerate(fs):
            rk = f.get("root_rec", "")
            root = tuple(rk.split("|")) if rk and rk != "-" else None
            items.append(H.Item(id=str(i), drive=C.DRIVE, relpath=f["relpath"], root=root,
                                extra={"size": f["size"], "sha256": f["sha256"], "claim_id": f["claim_id"]}))
        try:
            dests = p.plan(items)
        except H.BudgetError as e:
            failed.append(f"{base}: {e}")
            continue
        tops = collections.defaultdict(lambda: [0, 0])
        for it_, f in zip(items, fs):
            f["dest"] = dests[it_.id]
            f["shortened"] = "Y" if it_.extra.get("shortened") else "N"
            lens.append(H.unc_len(f["dest"]))
            nshort += f["shortened"] == "Y"
            rel = f["dest"][len(base) + 1:]
            sf = rel.split("\\")[1] if rel.count("\\") >= 2 else rel
            tops[sf][0] += 1
            tops[sf][1] += int(f["size"])
        scatter[base] = len(tops)
        d3_nodes = [k for k in p.nodes if k.startswith(C.DRIVE + ":")]
        short_rows.append({"tree": base, "files": len(fs), "folders": len(d3_nodes),
                           "folders_shortened": sum(1 for k in p.short if k.startswith(C.DRIVE + ":")),
                           "file_names_shortened": len(p.file_short),
                           "longest": max(H.unc_len(f["dest"]) for f in fs)})
        for sf, (n, b) in sorted(tops.items(), key=lambda kv: -kv[1][1]):
            study_rows.append({"tree": base, "study_folder": sf, "files": n, "gb": C.gb(b)})
    C.wcsv(os.path.join(OUT, "path_stats.csv"), ["tree", "files", "folders", "folders_shortened",
                                                 "file_names_shortened", "longest"], short_rows)
    C.wcsv(os.path.join(OUT, "study_folders.csv"), ["tree", "study_folder", "files", "gb"], study_rows, bom=True)
    say(f"  folders (drive 3): {sum(r['folders'] for r in short_rows):,}; shortened: "
        f"{sum(r['folders_shortened'] for r in short_rows):,}; file names shortened: "
        f"{sum(r['file_names_shortened'] for r in short_rows):,}")
    say(f"  destinations: {len(lens):,}; longest {max(lens) if lens else 0}; over 240: "
        f"{sum(1 for x in lens if x > 240)}; shortened (a folder or the name on the way): {nshort:,}")
    for fl in failed:
        say(f"  !! {fl}")
    # scattering with / without the SHADOWED outer folders
    sc_noshadow = collections.defaultdict(set)
    for f in a2:
        if f["dec_rec"] in ("place", "place-after-reopen", "closed-project") and f.get("root_noshadow"):
            sc_noshadow[f["rec_project"]].add(f["root_noshadow"])
    sc_shadow = collections.defaultdict(set)
    for f in a2:
        if f["dec_rec"] in ("place", "place-after-reopen", "closed-project"):
            sc_shadow[f["rec_project"]].add(f.get("root_rec", ""))
    say("\nSTUDY FOLDERS per project tree (MJesus-MFB\\<study folder>): with the SHADOWED outer folders "
        "(recommended) vs as drives 1+2 ran (no shadowed roots)")
    for p in sorted(sc_shadow, key=lambda p: -len(sc_shadow[p])):
        say(f"  {p:28s} {len(sc_shadow[p]):4d}   (without: {len(sc_noshadow.get(p, ())):4d})")

    # ---- write ---------------------------------------------------------------------------------------
    fields = ["relpath", "top", "size", "sha256", "cls", "seg", "verdict", "claim_id", "engine_project",
              "dec_engine", "reading", "rec_project", "dec_rec", "root_rec", "dest", "shortened",
              "canonical_rec", "dup_n", "dup_tops", "in_raw", "placed12", "holding12", "conflict"]
    for f in a2:
        f.setdefault("dest", "")
        f.setdefault("shortened", "")
        f.setdefault("root_rec", "")
        f.setdefault("canonical_rec", "")
    C.wcsv(os.path.join(OUT, "placement_plan.csv"), fields, a2)

    def table(key, scen):
        agg = collections.defaultdict(lambda: [0, 0])
        for f in a2:
            k = key(f, scen)
            agg[k][0] += 1
            agg[k][1] += int(f["size"])
        return agg

    say("\nBY DECISION                      engine scenario            recommended scenario")
    e = table(lambda f, s: f[f"dec_{s}"], "engine")
    r = table(lambda f, s: f[f"dec_{s}"], "rec")
    for k in sorted(set(e) | set(r)):
        say(f"  {k:24s} {e[k][0]:8,d} {C.gb(e[k][1]):>8s} GB   {r[k][0]:8,d} {C.gb(r[k][1]):>8s} GB")
    say("\nREADINGS (recommended scenario only)")
    rd = collections.defaultdict(lambda: [0, 0, collections.Counter()])
    for f in a2:
        if f["reading"]:
            rd[f["reading"]][0] += 1
            rd[f["reading"]][1] += int(f["size"])
            rd[f["reading"]][2][f["dec_rec"]] += 1
    for k in sorted(rd):
        say(f"  {k:9s} {rd[k][0]:6,d} files {C.gb(rd[k][1]):>7s} GB  -> {dict(rd[k][2])}")
    prow = []
    agg = collections.defaultdict(lambda: collections.Counter())
    aggb = collections.defaultdict(lambda: collections.Counter())
    for f in a2:
        for scen in ("engine", "rec"):
            p = f["engine_project" if scen == "engine" else "rec_project"] or "(no project)"
            agg[(p, scen)][f[f"dec_{scen}"]] += 1
            aggb[(p, scen)][f[f"dec_{scen}"]] += int(f["size"])
    for (p, scen) in sorted(agg):
        row = {"project": p, "scenario": scen, "status": status_of(p) if not p.startswith("(") else ""}
        for d in ("place", "place-after-reopen", "closed-project", "already-placed", "placed-elsewhere",
                  "duplicate-copy", "in-raw", "deferred-biomaGUNE-MJ", "covered-by-twin", "holding",
                  "holding-nmr", "already-in-holding", "exclude-zero-byte"):
            row[f"{d}_files"] = agg[(p, scen)][d]
            row[f"{d}_gb"] = C.gb(aggb[(p, scen)][d])
        prow.append(row)
    C.wcsv(os.path.join(OUT, "per_project.csv"), list(prow[0].keys()), prow)
    say("\nPER PROJECT, recommended scenario: to place now (files, GB) | already placed | deferred (biomaGUNE MJ)")
    for row in prow:
        if row["scenario"] != "rec":
            continue
        n = row["place_files"] + row["place-after-reopen_files"] + row["closed-project_files"]
        g = float(row["place_gb"]) + float(row["place-after-reopen_gb"]) + float(row["closed-project_gb"])
        say(f"  {row['project']:28s} {row['status']:22s} {n:6,d} {g:8.2f} | {row['already-placed_files']:6,d} "
            f"| {row['deferred-biomaGUNE-MJ_files']:6,d}")
    cls = table(lambda f, s: (f["cls"], f[f"dec_{s}"]), "rec")
    C.wcsv(os.path.join(OUT, "per_class.csv"), ["cls", "decision", "files", "gb"],
           [{"cls": k[0], "decision": k[1], "files": v[0], "gb": C.gb(v[1])} for k, v in sorted(cls.items())])
    with open(os.path.join(OUT, "plan.log"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log) + "\n")


if __name__ == "__main__":
    main()
