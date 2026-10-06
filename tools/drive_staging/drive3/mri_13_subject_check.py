"""Stream M: every subject id the batches will write, looked up in the facility DB now (SELECT only, read-only).

    python mri_13_subject_check.py

A dry run of ingest_raw.py returns before the subject enrichment, so it proves nothing about subject ids. This calls
the same lookup the ingest calls (tools/animal_db.lookup(alias, animal), no cache) for every distinct (alias, animal)
of the case tables, and requires: found; the composed id is <animal>-AE-biomaGUNE-<alias> (never -None: 0118 has a
NULL alias in the DB, so the caller's alias must be used); a species; and a procedure logged within 3 days of each of
the animal's scan dates, or the A1 verdict CLAIM-KEPT for that study. Writes out\\subject_check.csv / .txt.
"""
import collections
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mri_common as C  # noqa: E402

sys.path.insert(0, os.path.join(C.WT, "tools"))
import animal_db  # noqa: E402

BATCHES = ["M01", "M02", "M03", "M04", "M05", "M06", "M07"]


def main():
    plan = {p["original_name"]: p for p in C.rows(os.path.join(C.OUT, "plan_exams.csv"))}
    want = collections.defaultdict(set)
    verdicts = collections.defaultdict(set)
    for b in BATCHES:
        for c in C.rows(os.path.join(C.CFG_DIR, f"cases_{b}.csv")):
            k = (c["drv_alias"], int(c["drv_animal"]))
            want[k].add(c["drv_acq_datetime"][:10])
            verdicts[k].add(plan[c["original_name"]]["verdict"])
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
        ok = (res.reason is None and sid == f"{animal}-AE-biomaGUNE-{alias}" and "None" not in sid and s.get("species")
              and (all(not n.endswith(":none") for n in near) or verdicts[(alias, animal)] <= {"CLAIM-KEPT"}
                   or "CLAIM-KEPT" in verdicts[(alias, animal)]))
        rec = {"alias": alias, "animal": animal, "found": res.reason is None, "reason": res.reason or "",
               "subject_id": sid, "species": s.get("species", ""), "strain": s.get("strain", ""), "sex": s.get("sex", ""),
               "dob": s.get("date_of_birth", ""), "scan_dates_and_procedures": "; ".join(near),
               "a1_verdicts": ";".join(sorted(verdicts[(alias, animal)])), "first_scan": min(dates), "ok": ok}
        out.append(rec)
        if not ok:
            bad.append(rec)
    C.write_csv(C.out("subject_check.csv"), out)
    L = [f"distinct (alias, animal): {len(out)}; found {sum(r['found'] for r in out)}; ok {sum(1 for r in out if r['ok'])}",
         f"by alias: {dict(collections.Counter(r['alias'] for r in out))}",
         f"species: {dict(collections.Counter((r['alias'], r['species']) for r in out))}",
         f"ids ending -None: {sum(1 for r in out if r['subject_id'].endswith('None'))}",
         f"born after its first scan: {[(r['alias'], r['animal']) for r in out if r['dob'] and str(r['dob'])[:10] > r['first_scan']]}",
         f"not ok: {[(r['alias'], r['animal'], r['reason'], r['scan_dates_and_procedures'], r['a1_verdicts']) for r in bad][:20]}"]
    open(C.out("subject_check.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
