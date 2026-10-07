#!/usr/bin/env python3
"""ingest_check.py -- the dry-run review for a historical-drive .czi ingest, run against the ENGINE'S
OWN resolution of every generated config.

For every batch config of the profile (ingest_plan.PROFILES; default drives_2026-09, the drives 1+2
ingest; `--profile drive3_2026-10` for M. Jesus's drive) it calls ingest/config.expand_batch -- the exact
code path `ingest_raw.py --dry-run` runs before its early return, reading each .czi's own metadata and the
live registry for dedup -- and compares every resolved case, file by file, with the independent expected
table (ingest_plan.py plan). It never writes to the NAS.

    python tools/drive_staging/ingest_check.py [--profile P] [--batch B01 ...] [--nas J:\\gjesus3-data]

Output: <out>\\check_cases.csv (one row per case, engine value vs expected), check_report.json and a
printed PASS/FAIL per check. Exit 1 on any unexplained mismatch.

  1 reconciliation   every in-scope content in exactly one batch; engine cases == expected rows;
                     per-instrument counts/GB re-derived here from the catalog (drive 3: from part A1's
                     header table); nothing out of scope
  2 per file         instrument, project, researcher, operator, subject id, acquisition_datetime,
                     data_source, original_name (+ instrument_model, sample, link name): 0 mismatches
  3 production       no in-scope sha256 in the production index, and that index is not older than
                     the registry
  3b re-saves        no planned file is a re-save of a production acquisition (same instrument,
                     timestamp to the second and filename), and no two planned files are (gate R1/R2)
  3c derivatives     no planned file shares instrument + timestamp with a production acquisition (R3),
                     except a planned sibling an earlier batch of this run ingested (INFO-listed) and,
                     drive 3, a production row the pixel check compared it with (its decided group)
  3d decided         drive 3: every planned file that shares an instrument + second with another planned
                     file or a production row sits in a group the pixel check decided for exactly the
                     current membership, as keep or keep-flag
  3e structure       drive 3: every planned (farm) file's last subblock ends inside the file (no
                     truncated primary), and its farm path fits MAX_PATH
  4 dates            no blank acquisition_datetime, no ACQ-ID date == today
  5 projects         only the profile's one new project may be created (drive 3: none); every other exists
  6 subjects         none on (A)-held / (C) / no-claim rows; each present one re-resolves in the facility
                     DB, in its own protocol, to itself
  7 XMIC             drives 1+2: 338 rows, instrument_model "Axio Imager.Z2", the chosen data_source
  8 link names       drive 3: every planned link name is unique in its project and free in the project's
                     live raw_linked\\ (the engine's 2026-10-05 pre-check refuses a taken one at run time)
"""
import argparse
import collections
import contextlib
import csv
import datetime as dt
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, TOOLS)
import ingest_plan as P  # noqa: E402
from ingest import config, enrichment, linker, resolver  # noqa: E402
import animal_db  # noqa: E402


def split_3c_hits(e, prod_rows, exp, decided=frozenset()):
    """Split one planned file's production matches (same instrument + timestamp) for check 3c.

    Returns (exempt, hits). A match is EXEMPT -- an expected planned sibling, not a derivative --
    when the production row's original_name is itself a row of the frozen plan (so an earlier batch
    of THIS run ingested it) AND that row's planned acq_group equals the checked file's acq_group
    (gate rule R4: keep every member of a same-timestamp group). Drive 3 adds one more exemption: a
    production row that is a member of the file's decided pixel-check group (`decided`: the ACQ-IDs
    that group was decided with). Everything else stays a hit: a derivative of an acquisition that was
    in production before this run, or an operator ingest of a sibling. (Coordinator answer to the B08
    stop, 2026-10-01: ANSWER_B08_STOP.md.)
    """
    grp = e.get("acq_group", "")
    exempt, hits = [], []
    for r in prod_rows:
        planned = exp.get(r["original_name"])
        if r["acq_id"] in decided:
            exempt.append(r)
        elif grp and planned and planned.get("acq_group") == grp:
            exempt.append(r)
        else:
            hits.append(r)
    return exempt, hits


def split_3d_new_production(prows, dec_prod, sibs):
    """Check 3d: which production rows sharing a decided group's second are NEW since the pixel check.

    Returns (new, sibling). A production row is not new when the pixel check already knew it as a
    production member (`dec_prod`, its ACQ-IDs), and it is an expected SIBLING when its original_name is a
    planned member of the same group (`sibs`, the whole plan's members, every batch): an earlier batch of
    THIS run ingested it, and the pixel check decided it as a planned member. Everything else is new: an
    operator ingest, or a row from outside the plan. (The 3d twin of check 3c's exemption; the coordinator,
    2026-10-07, after C03 stopped on ten such C02 siblings.)
    """
    planned_names = {s["original_name"] for s in sibs}
    new, sibling = [], []
    for p in prows:
        if p["acq_id"] in dec_prod:
            continue
        (sibling if p["original_name"] in planned_names else new).append(p)
    return new, sibling


def czi_last_subblock_inside(path):
    """(inside?, last end, size): does the .czi's last subblock (any pyramid level) end inside the file?"""
    import czifile
    lp = P.longpath(path)
    size = os.path.getsize(lp)
    with czifile.CziFile(lp) as czi:
        last = max(czi.subblock_directory, key=lambda e: e.file_position)
        seg = last.read_segment_data(czi)
        end = seg.data_offset + seg.data_size
    return end <= size, end, size


def main():
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--profile", default=P.DEFAULT_PROFILE)
    known, _ = pre.parse_known_args()
    P.use_profile(known.profile)
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--profile", default=P.DEFAULT_PROFILE, choices=sorted(P.PROFILES))
    ap.add_argument("--out", default=P.OUT)
    ap.add_argument("--nas", default=P.NAS)
    ap.add_argument("--config-dir", default=P.CONFIG_DIR)
    ap.add_argument("--batch", action="append")
    ap.add_argument("--no-structure", action="store_true", help="drive 3: skip check 3e's file reads")
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    decide = P.SAME_ACQ_MODE == "decide"

    exp = {e["original_name"]: e for e in P.load_expected(args.out)}
    batches = list(P.rcsv(os.path.join(args.config_dir, "batches.csv")))
    if args.batch:
        batches = [b for b in batches if b["batch"] in set(args.batch)]
    checks = collections.OrderedDict()
    notes = collections.defaultdict(list)
    today = dt.date.today().strftime("%Y%m%d")
    projects_csv = os.path.join(args.nas, "registries", "registry_projects.csv")

    # ---- run the engine over every batch ------------------------------------------------------
    rows, cases_by_batch, engine_log = [], {}, {}
    t0 = time.time()
    for b in batches:
        cfg_path = os.path.join(args.config_dir, f"{P.CONFIG_PREFIX}{b['batch']}.yaml")
        cfg = config.load_config(cfg_path)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cases = config.expand_batch(cfg, nas_root=args.nas)
        log = buf.getvalue()
        engine_log[b["batch"]] = {
            "skips": sum(1 for ln in log.splitlines() if "SKIP" in ln),
            "warns": sum(1 for ln in log.splitlines() if "WARN" in ln),
            "extraction_failures": sum(1 for ln in log.splitlines() if "embedded extraction failed" in ln),
        }
        if engine_log[b["batch"]]["skips"] or engine_log[b["batch"]]["extraction_failures"]:
            notes["engine"].append(f"{b['batch']}: " + "; ".join(
                ln for ln in log.splitlines() if "SKIP" in ln or "failed" in ln)[:2000])
        cases_by_batch[b["batch"]] = cases
        auto_create = bool((cfg.get("ingest") or {}).get("auto_create_projects"))
        for c in cases:
            d = c.get("discovered") or {}
            # subject exactly as the engine's enrichment would form it (Step 8.4)
            pairs = []
            if (c.get("sample_type") or "").lower() in ("organism", "tissue") and c.get("subject_from_db"):
                pairs = enrichment._subject_pairs(c, d, lambda *a, **k: None)
            subj = ";".join(animal_db.compose_subject_id(code, alias) for alias, code in pairs)
            proj_id, canon, _folder = linker.resolve_project(projects_csv, c.get("project_name", "")) \
                if c.get("project_name") else ("", "", "")
            link = resolver.resolve_link_filename(c.get("link_filename"), c, "ACQ-X",
                                                  (c.get("acquisition_datetime") or "")[:10].replace("-", ""))
            rows.append({
                "batch": b["batch"], "original_name": c["original_name"], "auto_create": auto_create,
                "instrument": c.get("instrument", ""), "project": c.get("project_name", ""),
                "project_resolves_to": proj_id or "", "researcher": c.get("researcher", ""),
                "operator": c.get("operator", ""), "subject_id": subj,
                "acquisition_datetime": c.get("acquisition_datetime", ""),
                "data_source": c.get("data_source", ""), "instrument_model": c.get("instrument_model", ""),
                "sample_id": c.get("sample_id", ""), "sample_type": c.get("sample_type", ""),
                "link_name": link or "", "sha256": d.get("drv_sha256", ""),
                "czi_microscope_name": d.get("czi_microscope_name", ""),
                "acq_group": d.get("drv_acq_group", ""), "notes": c.get("notes", ""),
                "source_path": c.get("source_path", ""),
            })
        print(f"{b['batch']}: {len(cases)} cases, log {engine_log[b['batch']]} "
              f"({time.time() - t0:.0f}s)", flush=True)

    got = {r["original_name"]: r for r in rows}
    want_batches = {b["batch"] for b in batches}
    exp_in = {k: e for k, e in exp.items() if e["batch"] in want_batches}

    # ---- 1 reconciliation --------------------------------------------------------------------------
    c1 = []
    dup_case = [k for k, n in collections.Counter(r["original_name"] for r in rows).items() if n > 1]
    shas = collections.Counter(e["sha256"] for e in exp.values())
    c1 += [f"sha256 in >1 expected row: {s}" for s, n in shas.items() if n > 1]
    c1 += [f"engine case twice: {k}" for k in dup_case]
    c1 += [f"expected but not produced by the engine: {k}" for k in exp_in if k not in got]
    c1 += [f"engine case not in the plan: {k}" for k in got if k not in exp_in]
    c1 += [f"case in batch {got[k]['batch']} but planned for {exp_in[k]['batch']}: {k}"
           for k in got if k in exp_in and got[k]["batch"] != exp_in[k]["batch"]]
    c1 += [f"{k}: engine sha {got[k]['sha256'][:12]} != plan {exp_in[k]['sha256'][:12]}"
           for k in got if k in exp_in and got[k]["sha256"] != exp_in[k]["sha256"]]
    # independent re-derivation from the source tables (not from the plan's own code path)
    prod = {r["sha256"] for r in P.rcsv(os.path.join(P.CAT, "production_hashes.csv"))}
    gopt = collections.Counter()   # planned exclusions other than production (re-saves, derivatives, ...)
    for x in P.rcsv(os.path.join(args.out, "excluded.csv")):
        if x["reason"] != "in-production":
            gopt[x["sha256"]] += 1
    derived = collections.defaultdict(dict)
    if decide:
        for r in P.rcsv(P.A1_FILES):
            if r["ext"].lower() == ".czi" and r["czi_class"] == "czi-raw" and r["instrument"] in P.INSTRUMENTS:
                if r["sha256"] not in prod and r["sha256"] not in gopt:
                    derived[P.INSTRUMENTS[r["instrument"]]][r["sha256"]] = int(r["size"])
    else:
        for r in P.rcsv(os.path.join(P.CAT, "files.csv")):
            if r["ext"].lower() == ".czi" and r["class"] == "czi-raw" and r["instrument"] in P.INSTRUMENTS:
                if r["sha256"] not in prod and r["sha256"] not in gopt:
                    derived[P.INSTRUMENTS[r["instrument"]]][r["sha256"]] = int(r["size"])
        for r in P.rcsv(os.path.join(P.CAT, "archive_members.csv")):
            if r["ext"].lower() == ".czi" and r["class"] == "czi-raw" and r["instrument"] in P.INSTRUMENTS:
                if r["sha256"] not in prod and r["sha256"] not in gopt:
                    derived[P.INSTRUMENTS[r["instrument"]]][r["sha256"]] = int(r["size"])
    recon = {}
    for inst in sorted(set(derived) | {e["instrument"] for e in exp.values()}):
        pe = [e for e in exp.values() if e["instrument"] == inst]
        recon[inst] = {"catalog_distinct_new": len(derived[inst]),
                       "catalog_gb": P.gb(sum(derived[inst].values())),
                       "plan": len(pe), "plan_gb": P.gb(sum(int(e["size"]) for e in pe)),
                       "of_which_archive_only": sum(1 for e in pe if e["kind"] == "member")}
        if args.batch:
            # per-batch (pre-flight of one production batch): earlier batches are IN production now,
            # so only require that this batch's files are still new in-scope content
            pin = {e["sha256"] for e in exp_in.values() if e["instrument"] == inst}
            if pin - set(derived[inst]):
                c1.append(f"{inst}: {len(pin - set(derived[inst]))} planned file(s) of this batch are no "
                          f"longer new in-scope content (now in production?)")
        elif set(derived[inst]) != {e["sha256"] for e in pe}:
            c1.append(f"{inst}: catalog-derived set != plan set "
                      f"({len(set(derived[inst]) - {e['sha256'] for e in pe})} missing, "
                      f"{len({e['sha256'] for e in pe} - set(derived[inst]))} extra)")
    for e in exp.values():
        if not e["original_name"].lower().endswith(".czi"):
            c1.append(f"not a .czi: {e['original_name']}")
    checks["1 reconciliation"] = c1
    notes["1"].append(recon)

    # ---- 2 per file ---------------------------------------------------------------------------------
    c2 = []
    fields = [("instrument", "instrument"), ("project", "project"), ("researcher", "researcher"),
              ("operator", "operator"), ("subject_id", "subject_id"), ("data_source", "data_source"),
              ("sample_id", "sample_id"), ("sample_type", "sample_type"), ("link_name", "link_name")]
    mism = collections.Counter()
    for k, g in got.items():
        e = exp_in.get(k)
        if not e:
            continue
        for gf, ef in fields:
            if g[gf] != e[ef]:
                mism[gf] += 1
                c2.append(f"{k}: {gf} engine={g[gf]!r} expected={e[ef]!r}")
        # instrument_model: the catalog's stand name where it has one (archive members: no stand in
        # the catalog -> the engine's own reading must at least be non-blank)
        if e["instrument_model"] and g["instrument_model"] != e["instrument_model"]:
            mism["instrument_model"] += 1
            c2.append(f"{k}: instrument_model engine={g['instrument_model']!r} expected={e['instrument_model']!r}")
        if not g["instrument_model"]:
            mism["instrument_model"] += 1
            c2.append(f"{k}: instrument_model blank")
        # acquisition_datetime: the engine reads the .czi itself; the catalog read it independently
        if resolver.normalize_acquisition_datetime(e["acquisition_datetime"]) != g["acquisition_datetime"]:
            mism["acquisition_datetime"] += 1
            c2.append(f"{k}: acquisition_datetime engine={g['acquisition_datetime']!r} "
                      f"catalog={e['acquisition_datetime']!r}")
        if k != e["original_name"]:
            mism["original_name"] += 1
        if g["acq_group"] != e["acq_group"] or g["notes"] != e["notes"]:
            mism["acq_group/notes"] += 1
            c2.append(f"{k}: acq_group/notes differ from the plan")
    checks["2 per-file"] = c2
    notes["2"].append({"mismatch_by_field": dict(mism), "cases_compared": len(got)})

    # ---- 3 production -------------------------------------------------------------------------------
    c3 = [f"in production: {e['original_name']}" for e in exp_in.values() if e["sha256"] in prod]
    reg = os.path.join(args.nas, "registries", "registry_raw.csv")
    ph = os.path.join(P.CAT, "production_hashes.csv")
    with open(reg, encoding="utf-8-sig", newline="") as f:
        n_reg = sum(1 for _ in csv.DictReader(f))
    n_ph_acq = len({r["acq_id"] for r in P.rcsv(ph)})
    if os.path.getmtime(reg) > os.path.getmtime(ph):
        c3.append(f"registry_raw.csv is newer than production_hashes.csv: re-run catalog.py production"
                  + (f" --out {P.CAT}" if decide else ""))
    notes["3"].append({"registry_rows_now": n_reg, "acquisitions_in_hash_index": n_ph_acq,
                       "registry_mtime": dt.datetime.fromtimestamp(os.path.getmtime(reg)).isoformat(timespec="seconds"),
                       "hash_index_mtime": dt.datetime.fromtimestamp(os.path.getmtime(ph)).isoformat(timespec="seconds")})
    checks["3 production"] = c3

    # ---- 3b / 3c the same ACQUISITION under different bytes (gate 2026-09-30, R1-R3) -----------
    by_key, by_ts = P.production_index(args.nas)
    decided = collections.defaultdict(dict)       # drive 3: group -> {member: decision row}
    if decide:
        dpath = os.path.join(args.out, "pixel_decisions.csv")
        if os.path.isfile(dpath):
            for d in P.rcsv(dpath):
                decided[d["group"]][d["member"]] = d
    c3b, c3c, exempt_3c = [], [], []
    seen_key = collections.defaultdict(list)
    for e in exp_in.values():
        k = P.resave_key(e["instrument"], e["acquisition_datetime"], e["original_name"])
        if k in by_key:
            c3b.append(f"re-save of production {by_key[k][0]['acq_id']}: {e['original_name']}")
        seen_key[k].append(e["original_name"])
        t = (e["instrument"], e["acquisition_datetime"][:19])
        if t in by_ts:
            dec_ids = frozenset(m for m, d in decided.get(P.group_id(*t), {}).items() if d["role"] == "production")
            exempt, hits = split_3c_hits(e, by_ts[t], exp, decided=dec_ids)
            for r in exempt:
                exempt_3c.append((e["original_name"], r["acq_id"], e["acq_group"]))
            if hits:
                c3c.append(f"shares instrument+timestamp with production {[r['acq_id'] for r in hits]}: "
                           f"{e['original_name']}")
    c3b += [f"re-saves within the plan: {v}" for v in seen_key.values() if len(v) > 1]
    checks["3b re-saves"] = c3b
    checks["3c derivatives"] = c3c
    for name, acq, grp in exempt_3c:
        print(f"INFO 3c exempt (planned sibling ingested earlier in this run, or a production member of the "
              f"file's decided pixel-check group): {name} -> {acq}, group {grp}")
    print(f"INFO 3c exemptions: {len({n for n, _, _ in exempt_3c})} files "
          f"({len(exempt_3c)} file-to-production matches)", flush=True)
    groups = {e["acq_group"] for e in exp_in.values() if e.get("acq_group")}
    notes["3b"].append({"planned_rows": len(exp_in), "same_timestamp_groups_flagged": len(groups),
                        "files_in_them": sum(1 for e in exp_in.values() if e.get("acq_group"))})

    # ---- 3d / 3e drive 3: every same-acquisition group decided; no truncated file; paths fit --------
    if decide:
        c3d, c3e = [], []
        exempt_3d = []
        plan_by_group = collections.defaultdict(list)
        for e in exp.values():                       # the WHOLE plan: siblings may sit in other batches
            plan_by_group[P.group_id(e["instrument"], e["acquisition_datetime"])].append(e)
        for e in exp_in.values():
            gid = P.group_id(e["instrument"], e["acquisition_datetime"])
            sibs = plan_by_group[gid]
            prows = by_ts.get((e["instrument"], e["acquisition_datetime"][:19]), [])
            if e.get("same_acq_action") == P.ACTION_UNDECIDED:
                c3d.append(f"undecided: {e['original_name']}")
                continue
            if len(sibs) + len(prows) < 2:
                continue
            dec = decided.get(gid, {})
            if e["sha256"] not in dec:
                c3d.append(f"in a same-second group with no pixel decision: {e['original_name']}")
                continue
            # the membership now: the decided group's planned members (kept or not) + production now
            dec_prod = {m for m, d in dec.items() if d["role"] == "production"}
            new_prod, sib_prod = split_3d_new_production(prows, dec_prod, sibs)
            for p in sib_prod:
                exempt_3d.append((e["original_name"], p["acq_id"], gid))
            if new_prod:
                c3d.append(f"production rows added since the pixel check share its second: "
                           f"{sorted(p['acq_id'] for p in new_prod)}: {e['original_name']}")
            if e.get("same_acq_action") not in (P.ACTION_KEEP, P.ACTION_FLAG):
                c3d.append(f"planned with action {e.get('same_acq_action')!r}: {e['original_name']}")
            if dec[e["sha256"]].get("complete") != "Y":
                notes["3d"].append(f"kept although incomplete (flagged): {e['original_name']}")
        checks["3d decided"] = c3d
        for name, acq, grp in exempt_3d:
            print(f"INFO 3d exempt (a planned sibling an earlier batch of this run ingested): {name} -> {acq}, group {grp}")
        print(f"INFO 3d exemptions: {len(exempt_3d)} file-to-production matches", flush=True)
        notes["3d"].append({"groups_decided": len(decided),
                            "planned_rows_in_groups": sum(1 for e in exp_in.values() if e.get("same_acq_group"))})
        n_struct = 0
        for k, g in got.items():
            e = exp_in.get(k)
            if not e:
                continue
            if len(g["source_path"]) > P.MAX_FARM_PATH:
                c3e.append(f"farm path {len(g['source_path'])} > {P.MAX_FARM_PATH}: {g['source_path']}")
            if not args.no_structure:
                try:
                    inside, end, size = czi_last_subblock_inside(g["source_path"])
                    n_struct += 1
                    if not inside:
                        c3e.append(f"last subblock ends at {end} past the file's {size} bytes (truncated): {k}")
                except Exception as ex:     # an unreadable file is a failure, never skipped
                    c3e.append(f"cannot read its subblock directory ({type(ex).__name__}: {ex}): {k}")
        checks["3e structure"] = c3e
        notes["3e"].append({"files_structure_checked": n_struct,
                            "max_source_path": max((len(g["source_path"]) for g in rows), default=0)})

    # ---- 4 dates ------------------------------------------------------------------------------------
    c4 = []
    for g in rows:
        adt = g["acquisition_datetime"]
        if len(adt) < 10:
            c4.append(f"blank acquisition_datetime: {g['original_name']}")
        elif adt[:10].replace("-", "") == today:
            c4.append(f"ACQ-ID would be dated today: {g['original_name']}")
    years = collections.Counter(g["acquisition_datetime"][:4] for g in rows)
    notes["4"].append({"years": dict(sorted(years.items()))})
    checks["4 dates"] = c4

    # ---- 5 projects ---------------------------------------------------------------------------------
    c5 = []
    created = collections.Counter()
    existing = collections.Counter()
    for g in rows:
        if not g["project"]:
            continue
        if g["project_resolves_to"]:
            existing[(g["project"], g["project_resolves_to"])] += 1
        else:
            created[g["project"]] += 1
            if not g["auto_create"]:
                c5.append(f"{g['original_name']}: project {g['project']} does not exist and its batch "
                          f"does not auto-create (would register with NO project)")
    allowed = {P.NEW_PROJECT} - {None}
    if set(created) - allowed:
        c5.append(f"would create unexpected projects: {sorted(set(created) - allowed)}")
    auto_batches = {g["batch"] for g in rows if g["auto_create"]}
    for g in rows:
        if g["batch"] in auto_batches and g["project"] != P.NEW_PROJECT:
            c5.append(f"auto-create batch holds a non-{P.NEW_PROJECT} file: {g['original_name']}")
    if decide:
        status = {r["project_id"]: r["status"] for r in P.rcsv(projects_csv)}
        for (pname, pid), n in existing.items():
            if status.get(pid) != "active":
                c5.append(f"target project {pname} ({pid}) is {status.get(pid)!r}, not active ({n} files)")
    notes["5"].append({"created": dict(created),
                       "existing": {f"{p} = {i}": n for (p, i), n in sorted(existing.items())}})
    checks["5 projects"] = c5

    # ---- 6 subjects ----------------------------------------------------------------------------------
    c6 = []
    conn = animal_db.get_connection()
    seen = {}
    for g in rows:
        e = exp_in.get(g["original_name"])
        if not e:
            continue
        # a subject only where the claim is Confirmed, or an ACCEPTED reading filled it (drive 3: readings.csv)
        if g["subject_id"] and (not (e["verdict"] == "CONFIRMED" or e["verdict"].startswith("READING-"))
                                or not g["project"]):
            c6.append(f"subject on a {e['verdict']} / blank-project row: {g['original_name']}")
        if P.NEW_PROJECT and g["project"] == P.NEW_PROJECT and g["subject_id"]:
            c6.append(f"subject on a {P.NEW_PROJECT} row (HELD): {g['original_name']}")
        if g["subject_id"]:
            alias = g["subject_id"].split("-AE-biomaGUNE-")[-1]
            if g["project"][-4:] != alias:
                c6.append(f"subject {g['subject_id']} not in its own project {g['project']}")
            if g["subject_id"] not in seen:
                code = int(g["subject_id"].split("-")[0])
                res = animal_db.lookup(alias, code, conn=conn, use_cache=False)
                if res.status == "unreachable":
                    raise SystemExit(f"animal DB unreachable: {res.detail}")
                seen[g["subject_id"]] = res.subject.get("facility_animal_id") if res.status == "found" else None
            if seen[g["subject_id"]] != g["subject_id"]:
                c6.append(f"subject {g['subject_id']} does not re-resolve (got {seen[g['subject_id']]})")
    notes["6"].append({"rows_with_subject": sum(1 for g in rows if g["subject_id"]),
                       "distinct_subjects": len(seen)})
    checks["6 subjects"] = c6

    # ---- 7 XMIC ------------------------------------------------------------------------------------------
    xm = [g for g in rows if g["instrument"] == "XMIC"]
    c7 = []
    want_xmic = P.PROFILE.get("xmic_expected")
    if want_xmic is not None and not args.batch and len(xm) != want_xmic:
        c7.append(f"XMIC rows {len(xm)} != {want_xmic}")
    if want_xmic is None and xm:
        c7.append(f"{len(xm)} XMIC rows in a profile that plans none")
    c7 += [f"XMIC model/source wrong: {g['original_name']}" for g in xm
           if g["instrument_model"] != P.XMIC_MODEL or g["data_source"] != P.XMIC_SOURCE]
    notes["7"].append({"xmic_rows": len(xm)})
    checks["7 XMIC"] = c7

    # ---- 8 link names (drive 3) ---------------------------------------------------------------------------
    if decide:
        c8 = []
        projects = P.load_projects(args.nas)
        live = {}
        per_project = collections.defaultdict(collections.Counter)
        for e in exp.values():
            if e["project"]:
                per_project[e["project"].lower()][e["link_name"].lower()] += 1
        for p, cnt in per_project.items():
            c8 += [f"link name {n!r} planned {k} times in {p}" for n, k in cnt.items() if k > 1]
        for g in rows:
            e = exp_in.get(g["original_name"])
            if not e or not e["project"]:
                continue
            key = e["project"].lower()
            if key not in live:
                pr = projects.get(key)
                live[key] = P.existing_links(args.nas, pr["folder"]) if pr else set()
            if g["link_name"].lower() in live[key]:
                c8.append(f"link name taken in {e['project']}\\raw_linked: {g['link_name']} ({g['original_name']})")
        checks["8 link names"] = c8
        notes["8"].append({"projects": len(per_project), "planned_links": sum(sum(c.values()) for c in per_project.values())})

    # ---- report ----------------------------------------------------------------------------------------
    P.wcsv(os.path.join(args.out, "check_cases.csv"), list(rows[0].keys()) if rows else ["original_name"], rows)
    rep = {"generated": dt.datetime.now().isoformat(timespec="seconds"), "profile": P.PROFILE_NAME,
           "batches": len(batches), "cases": len(rows), "engine": engine_log,
           "checks": {k: {"pass": not v, "failures": len(v), "first": v[:20]} for k, v in checks.items()},
           "notes": notes}
    with open(os.path.join(args.out, "check_report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1, ensure_ascii=False, default=str)
    print()
    for k, v in checks.items():
        print(f"{'PASS' if not v else 'FAIL'}  {k}  ({len(v)} failures)")
        for x in v[:10]:
            print(f"      {x}")
    print(json.dumps(notes, indent=1, ensure_ascii=False, default=str)[:6000])
    sys.exit(0 if all(not v for v in checks.values()) else 1)


if __name__ == "__main__":
    main()
