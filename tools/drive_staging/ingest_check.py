#!/usr/bin/env python3
"""ingest_check.py -- the dry-run review for the historical-drives .czi ingest (checks 1-7 of the
handoff), run against the ENGINE'S OWN resolution of every generated config.

For every batch config in tools/configs/drives_2026-09/ it calls ingest/config.expand_batch -- the
exact code path `ingest_raw.py --dry-run` runs before its early return, reading each .czi's own
metadata and the live registry for dedup -- and compares every resolved case, file by file, with
the independent expected table (ingest_plan.py plan). It never writes to the NAS.

    python tools/drive_staging/ingest_check.py [--batch B01 ...] [--nas J:\\gjesus3-data]

Output: <out>\\check_cases.csv (one row per case, engine value vs expected), check_report.json and a
printed PASS/FAIL per check. Exit 1 on any unexplained mismatch.

  1 reconciliation   every in-scope content in exactly one batch; engine cases == expected rows;
                     per-instrument counts/GB re-derived here from the catalog; nothing out of scope
  2 per file         instrument, project, researcher, operator, subject id, acquisition_datetime,
                     data_source, original_name (+ instrument_model, sample, link name): 0 mismatches
  3 production       no in-scope sha256 in the production index, and that index is not older than
                     the registry
  4 dates            no blank acquisition_datetime, no ACQ-ID date == today
  5 projects         exactly one project would be created (AE-biomaGUNE-0118); every other exists
  6 subjects         none on 0118 / (C) / no-claim rows; each present one re-resolves in the facility
                     DB, in its own protocol, to itself
  7 XMIC             338 rows, instrument_model "Axio Imager.Z2", the chosen data_source
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


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=P.OUT)
    ap.add_argument("--nas", default=P.NAS)
    ap.add_argument("--config-dir", default=P.CONFIG_DIR)
    ap.add_argument("--batch", action="append")
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")

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
        cfg_path = os.path.join(args.config_dir, f"drives_{b['batch']}.yaml")
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
    # independent re-derivation from the catalog (not from the plan's own code path)
    prod = {r["sha256"] for r in P.rcsv(os.path.join(P.CAT, "production_hashes.csv"))}
    gopt = collections.Counter()
    for x in P.rcsv(os.path.join(args.out, "excluded.csv")):
        if x["reason"] == "in-goptical-axioscan":
            gopt[x["sha256"]] += 1
    derived = collections.defaultdict(dict)
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
        if set(derived[inst]) != {e["sha256"] for e in pe}:
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
              ("instrument_model", "instrument_model"), ("sample_id", "sample_id"),
              ("sample_type", "sample_type"), ("link_name", "link_name")]
    mism = collections.Counter()
    for k, g in got.items():
        e = exp_in.get(k)
        if not e:
            continue
        for gf, ef in fields:
            if g[gf] != e[ef]:
                mism[gf] += 1
                c2.append(f"{k}: {gf} engine={g[gf]!r} expected={e[ef]!r}")
        # acquisition_datetime: the engine reads the .czi itself; the catalog read it independently
        if resolver.normalize_acquisition_datetime(e["acquisition_datetime"]) != g["acquisition_datetime"]:
            mism["acquisition_datetime"] += 1
            c2.append(f"{k}: acquisition_datetime engine={g['acquisition_datetime']!r} "
                      f"catalog={e['acquisition_datetime']!r}")
        if k != e["original_name"]:
            mism["original_name"] += 1
    checks["2 per-file"] = c2
    notes["2"].append({"mismatch_by_field": dict(mism), "cases_compared": len(got)})

    # ---- 3 production -------------------------------------------------------------------------------
    c3 = [f"in production: {e['original_name']}" for e in exp.values() if e["sha256"] in prod]
    reg = os.path.join(args.nas, "registries", "registry_raw.csv")
    ph = os.path.join(P.CAT, "production_hashes.csv")
    with open(reg, encoding="utf-8-sig", newline="") as f:
        n_reg = sum(1 for _ in csv.DictReader(f))
    n_ph_acq = len({r["acq_id"] for r in P.rcsv(ph)})
    if os.path.getmtime(reg) > os.path.getmtime(ph):
        c3.append(f"registry_raw.csv is newer than production_hashes.csv: re-run catalog.py production")
    notes["3"].append({"registry_rows_now": n_reg, "acquisitions_in_hash_index": n_ph_acq,
                       "registry_mtime": dt.datetime.fromtimestamp(os.path.getmtime(reg)).isoformat(timespec="seconds"),
                       "hash_index_mtime": dt.datetime.fromtimestamp(os.path.getmtime(ph)).isoformat(timespec="seconds")})
    checks["3 production"] = c3

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
    if set(created) - {P.NEW_PROJECT}:
        c5.append(f"would create unexpected projects: {sorted(set(created) - {P.NEW_PROJECT})}")
    auto_batches = {g["batch"] for g in rows if g["auto_create"]}
    for g in rows:
        if g["batch"] in auto_batches and g["project"] != P.NEW_PROJECT:
            c5.append(f"auto-create batch holds a non-0118 file: {g['original_name']}")
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
        if g["subject_id"] and (e["verdict"] != "CONFIRMED" or not g["project"]):
            c6.append(f"subject on a {e['verdict']} / blank-project row: {g['original_name']}")
        if g["project"] == P.NEW_PROJECT and g["subject_id"]:
            c6.append(f"subject on a 0118 row (HELD): {g['original_name']}")
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
    if not args.batch and len(xm) != 338:
        c7.append(f"XMIC rows {len(xm)} != 338")
    c7 += [f"XMIC model/source wrong: {g['original_name']}" for g in xm
           if g["instrument_model"] != P.XMIC_MODEL or g["data_source"] != P.XMIC_SOURCE]
    notes["7"].append({"xmic_rows": len(xm)})
    checks["7 XMIC"] = c7

    # ---- report ----------------------------------------------------------------------------------------
    P.wcsv(os.path.join(args.out, "check_cases.csv"), list(rows[0].keys()) if rows else ["original_name"], rows)
    rep = {"generated": dt.datetime.now().isoformat(timespec="seconds"), "batches": len(batches),
           "cases": len(rows), "engine": engine_log,
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
