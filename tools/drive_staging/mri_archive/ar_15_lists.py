"""Stream AR: the hand-over lists (plan only; nothing is copied or appended here).

    python ar_15_lists.py [<nas_root>]          # with a root (e.g. the rehearsal), the ACQ-IDs each row was given

  out\\for_placement.csv      every exam NOT registered (spectroscopy, no reconstruction, never acquired, a failed
                             conversion, the incomplete exam of a short archive) and every 2dseq-only reconstruction
                             of a registered exam: the tarball and member prefix it is in, its files and bytes (k-space
                             included, from the extraction member list), and where a placement batch would put it (the
                             study's project, else the holding folder). Never-acquired exams (no data) are listed apart.
  out\\for_claim_workbook.csv one row per MRI session (study folder) registered with operator pending-claim: what
                             tools/claim_workbooks.py claims-append should add after the write (its session key).
  out\\for_assign_workbook.csv one row per study registered with NO project, with the claim and the DB evidence: for
                             the assign workbook (Q4; claim_workbooks.py assign-append covers drive 3 only today).
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ar_common as C  # noqa: E402


def main():
    nas = sys.argv[1] if len(sys.argv) > 1 else None
    plan = C.rows(os.path.join(C.OUT, "plan_exams.csv"))
    studies = {s["study"]: s for s in C.rows(os.path.join(C.OUT, "plan_studies.csv"))}
    nra = os.path.join(C.OUT, "not_registered_after_convert.csv")
    after = {x["original_name"]: x["reason"] for x in C.rows(nra)} if os.path.exists(nra) else {}
    acq = collections.defaultdict(list)
    if nas:
        for r in C.live_registry(nas):
            if "configs/mri_archive/" in r["ingest_config"].replace("\\", "/"):
                acq[r["original_name"].split("/")[0]].append(r["acq_id"])
    mem_cache = {}

    def mem(study):
        if study not in mem_cache:
            mem_cache.clear()
            mem_cache[study] = C.members(study)
        return mem_cache[study]

    place = []
    for x in plan:
        s = studies[x["study"]]
        if s["extracted"] != "Y":
            continue
        reason = x["reason"] if x["disposition"] == "not-registered" else after.get(x["original_name"], "")
        recons = x["recons_without_dicom"] if (not reason and x["disposition"] == "register") else ""
        if not reason and not recons:
            continue
        pre = [f"{x['study']}/{x['exam']}/"] if reason else [f"{x['study']}/{x['exam']}/pdata/{i}/" for i in recons.split(";")]
        ms = [m for m in mem(x["study"]) if m["kind"] == "file" and any(m["member"].startswith(p) for p in pre)]
        place.append({"study": x["study"], "exam": x["exam"], "what": "exam" if reason else f"reconstructions {recons} (2dseq only)",
                      "reason": reason or "reconstruction without DICOM beside registered DICOM (as stream M 3.2)",
                      "to": (s["project_name"] or "holding") if ms else "(nothing: no data)",
                      "files": len(ms), "bytes": sum(int(m["size"]) for m in ms),
                      "kspace_bytes": sum(int(m["size"]) for m in ms if C.is_kspace(m["member"].split("/")[-1])),
                      "tarball": s["archive"], "member_prefix": ";".join(pre)})
    C.write_csv(C.out("for_placement.csv"), place)

    cases = {}
    for b in sorted({x["batch"] for x in plan}):
        p = os.path.join(C.CFG_DIR, f"cases_{b}.csv")
        if os.path.exists(p):
            for c in C.rows(p):
                cases[c["original_name"]] = {**c, "batch": b}
    by = collections.defaultdict(list)
    for on, c in cases.items():
        by[on.split("/")[0]].append(c)
    claim, assign = [], []
    for st, cs in sorted(by.items()):
        s = studies[st]
        d = sorted(c["drv_acq_datetime"][:10] for c in cs)
        ids = sorted(acq.get(st, []))
        claim.append({"session_key": st, "batch": cs[0]["batch"], "project": s["project_name"], "sample": s["sample_id"],
                      "acquisitions": len(cs), "first_day": d[0], "last_day": d[-1],
                      "acq_ids": f"{ids[0]} .. {ids[-1]}" if ids else ""})
        if not s["project_name"]:
            assign.append({"study": st, "batch": cs[0]["batch"], "tier": s["tier"], "acquisitions": len(cs),
                           "first_day": d[0], "claim_in_name": s["claim"], "db_verdict": s["db_verdict"],
                           "why_no_project": s["why"], "db_evidence": s["db_evidence"],
                           "acq_ids": f"{ids[0]} .. {ids[-1]}" if ids else ""})
    C.write_csv(C.out("for_claim_workbook.csv"), claim)
    C.write_csv(C.out("for_assign_workbook.csv"), assign)
    pc = collections.Counter(p["to"] for p in place)
    print(f"for placement: {len(place)} rows ({sum(1 for p in place if p['what'] == 'exam')} exams, "
          f"{sum(1 for p in place if p['what'] != 'exam')} reconstruction sets); {sum(p['files'] for p in place)} files, "
          f"{sum(p['bytes'] for p in place) / 1e9:.2f} GB (k-space {sum(p['kspace_bytes'] for p in place) / 1e9:.2f} GB); "
          f"to {dict(pc)}")
    print(f"for the claim workbook: {len(claim)} sessions, {sum(c['acquisitions'] for c in claim)} acquisitions")
    print(f"for the assign workbook: {len(assign)} studies, {sum(a['acquisitions'] for a in assign)} acquisitions "
          f"{dict(collections.Counter(a['batch'] for a in assign))}")


if __name__ == "__main__":
    main()
