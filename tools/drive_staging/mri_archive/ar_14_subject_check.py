"""Stream AR: every subject id the batches will write, looked up in the facility DB now (SELECT only, read-only).

    python ar_14_subject_check.py

Stream M's mri_13_subject_check.py for this stream. A dry run returns before the subject enrichment, so it proves
nothing about subject ids. This calls the lookup the ingest calls (tools/animal_db.lookup(alias, animal), no cache) for
every distinct (alias, animal) of the case tables with an alias, and requires: found; the id is exactly
<animal>-AE-biomaGUNE-<alias> (never -None: 0118, 1116, 0219, 0618, 0619 hold a NULL alias in the DB, and animal_db
composes from the caller's alias); a species; born before the first scan; and a procedure logged within 3 days of
each scan day, or the study's verdict CLAIM-KEPT. Writes out\\subject_check.csv / .txt.
"""
import collections
import datetime
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ar_common as C  # noqa: E402

sys.path.insert(0, os.path.join(C.WT, "tools"))
import animal_db  # noqa: E402


def main():
    studies = {s["study"]: s for s in C.rows(os.path.join(C.OUT, "plan_studies.csv"))}
    want = collections.defaultdict(set)
    verdicts = collections.defaultdict(set)
    for p in sorted(glob.glob(os.path.join(C.CFG_DIR, "cases_AR*.csv"))):
        for c in C.rows(p):
            if not c["drv_alias"]:
                continue
            k = (c["drv_alias"], int(c["drv_animal"]))
            want[k].add(c["drv_acq_datetime"][:10])
            verdicts[k].add(studies[c["original_name"].split("/")[0]]["db_verdict"])
    conn = animal_db.get_connection()
    out, bad = [], []
    for (alias, animal), dates in sorted(want.items()):
        res = animal_db.lookup(alias, animal, conn=conn, use_cache=False)
        s = res.subject or {}
        sid = s.get("facility_animal_id", "")
        procs = s.get("procedures") or []
        near = []
        for d in sorted(dates):
            d0 = datetime.date.fromisoformat(d)
            hits = [p for p in procs if p.get("date") and abs((datetime.date.fromisoformat(p["date"][:10]) - d0).days) <= 3]
            near.append(f"{d}:{'+'.join(sorted({h['type'] for h in hits})) or 'none'}")
        born_ok = not (s.get("date_of_birth") and str(s["date_of_birth"])[:10] > min(dates))
        ok = (res.reason is None and sid == f"{animal}-AE-biomaGUNE-{alias}" and "None" not in sid and s.get("species")
              and born_ok and (all(not n.endswith(":none") for n in near) or "CLAIM-KEPT" in verdicts[(alias, animal)]))
        rec = {"alias": alias, "animal": animal, "found": res.reason is None, "reason": res.reason or "",
               "subject_id": sid, "species": s.get("species", ""), "strain": s.get("strain", ""), "sex": s.get("sex", ""),
               "dob": s.get("date_of_birth", ""), "scan_dates_and_procedures": "; ".join(near),
               "verdicts": ";".join(sorted(verdicts[(alias, animal)])), "first_scan": min(dates), "ok": ok}
        out.append(rec)
        if not ok:
            bad.append(rec)
    conn.close()
    C.write_csv(C.out("subject_check.csv"), out)
    L = [f"distinct (alias, animal): {len(out)}; found {sum(r['found'] for r in out)}; ok {sum(1 for r in out if r['ok'])}",
         f"by alias: {dict(collections.Counter(r['alias'] for r in out))}",
         f"species: {dict(collections.Counter((r['alias'], r['species']) for r in out))}",
         f"ids ending -None: {sum(1 for r in out if r['subject_id'].endswith('None'))}",
         f"born after its first scan: {[(r['alias'], r['animal']) for r in out if r['dob'] and str(r['dob'])[:10] > r['first_scan']]}",
         f"scan days with no procedure within 3 days (kept: CLAIM-KEPT): "
         f"{sum(1 for r in out for n in r['scan_dates_and_procedures'].split('; ') if n.endswith(':none'))}",
         f"not ok: {[(r['alias'], r['animal'], r['reason'], r['scan_dates_and_procedures'], r['verdicts']) for r in bad][:20]}"]
    open(C.out("subject_check.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
