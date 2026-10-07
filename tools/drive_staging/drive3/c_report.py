#!/usr/bin/env python3
"""c_report.py -- stream C (drive 3): every number in tasks/drive3_czi_gate.md, and its committed lists.

Reads the plan folder (ingest_plan.py --profile drive3_2026-10 plan; pixel_decisions.csv from
drive3/c_groups.py), part A1's microscopy table and part A2's per-file claims. Writes
<plan>\\report_tables.txt and, in the repo's tasks\\ folder:

  drive3_czi_nonraw_for_stream_p.csv    the derivatives found in the same-acquisition groups: stream P
                                         places them in the original's project folder (or holding)
  drive3_czi_pixel_classification.csv   every file the pixel check compared: class, parent, evidence, action
  drive3_czi_blank_project_preview.csv  every planned file with a blank project, and what its path claimed
  drive3_czi_held.csv                   files held back for the coordinator (a production row of the same
                                         name and second: repair or decide)
  drive3_czi_out_of_scope.csv           the drive's .czi / .lif that are not this stream's, with the reason

    python tools/drive_staging/drive3/c_report.py
Read-only except those outputs.
"""
import collections
import csv
import io
import json
import os
import re
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.dirname(HERE)
sys.path.insert(0, DS)
import ingest_plan as P  # noqa: E402

P.use_profile("drive3_2026-10")
TASKS = os.path.join(P.REPO, "tasks")
RATES = (31, 39)                      # MB/s, measured on drives 1+2 B01-B04 (source local, NAS write + read-back)
PER_FILE_S = (1.0, 2.0)               # per-acquisition registry / sidecar / link work over SMB (drives 1+2 estimate)


def rd(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def gbs(n):
    return f"{n / 1e9:,.1f}"


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(header))) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def main():
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    out = P.OUT
    exp = rd(os.path.join(out, "expected.csv"))
    exc = rd(os.path.join(out, "excluded.csv"))
    nonraw = rd(os.path.join(out, "nonraw_derived.csv"))
    held = rd(os.path.join(out, "production_repairs.csv"))
    oos = rd(os.path.join(out, "out_of_scope.csv"))
    batches = rd(os.path.join(out, "batches.csv"))
    summ = json.load(io.open(os.path.join(out, "plan_summary.json"), encoding="utf-8"))
    dec_path = os.path.join(out, "pixel_decisions.csv")
    dec = rd(dec_path) if os.path.isfile(dec_path) else []
    cand = rd(os.path.join(out, "pixel_candidates.csv"))
    a1 = rd(P.A1_FILES)
    L = []

    def say(m=""):
        L.append(m)

    # ---- scope -------------------------------------------------------------------------------------
    czi = [r for r in a1 if r["ext"] == ".czi"]
    cell = [r for r in czi if r["instrument"] == "CELL" and r["czi_class"] == "czi-raw"]
    d_cell = {r["sha256"]: r for r in cell}
    say("## scope")
    say(f"A1 rows: {len(a1):,} (.czi {len(czi):,}; .lif/.lifext {len(a1) - len(czi)}); Cell Observer czi-raw copies "
        f"{len(cell):,}, distinct {len(d_cell):,} ({gbs(sum(int(r['size']) for r in d_cell.values()))} GB)")
    oos_d = collections.defaultdict(dict)
    for r in oos:
        oos_d[r["reason"].split(":")[0]][r["sha256"]] = int(r["size"])
    for k, v in oos_d.items():
        say(f"  out of scope: {k}: {sum(1 for r in oos if r['reason'].split(':')[0] == k)} files, {len(v)} distinct, "
            f"{gbs(sum(v.values()))} GB")
    exr = collections.defaultdict(lambda: [0, 0])
    for x in exc:
        exr[x["reason"]][0] += 1
        exr[x["reason"]][1] += int(x["size"])
    for k, (n, b) in sorted(exr.items(), key=lambda kv: -kv[1][0]):
        say(f"  excluded {k}: {n} distinct, {gbs(b)} GB")
    tot = sum(int(e["size"]) for e in exp)
    say(f"PLAN: {len(exp):,} files, {gbs(tot)} GB, {len(batches)} batches")

    # ---- per project ----------------------------------------------------------------------------------
    say("")
    say("## per project")
    rows = []
    for p in sorted({e["project"] for e in exp}, key=lambda p: (p == "", p)):
        es = [e for e in exp if e["project"] == p]
        rows.append([p or "(blank)", es[0]["project_id"] if p else "", len(es), gbs(sum(int(e["size"]) for e in es)),
                     sum(1 for e in es if e["subject_id"]), len({e["subject_id"] for e in es if e["subject_id"]}),
                     ", ".join(f"{k} {v}" for k, v in collections.Counter(e["verdict"] for e in es).most_common())])
    L.extend(table(["project", "id", "files", "GB", "with subject", "animals", "verdicts"], rows))

    # ---- batches -------------------------------------------------------------------------------------
    say("")
    say("## batches")
    rows = []
    for b in batches:
        es = [e for e in exp if e["batch"] == b["batch"]]
        size = sum(int(e["size"]) for e in es)
        lo = size / (RATES[1] * 1e6) + len(es) * PER_FILE_S[0]
        hi = size / (RATES[0] * 1e6) + len(es) * PER_FILE_S[1]
        rows.append([b["batch"], b["bucket"], len(es), gbs(size), b["projects"], f"{lo / 3600:.1f}-{hi / 3600:.1f} h"])
    L.extend(table(["batch", "what", "files", "GB", "projects", "time at 31-39 MB/s"], rows))
    size = sum(int(e["size"]) for e in exp)
    say(f"total: {len(exp):,} files, {gbs(size)} GB, "
        f"{(size / (RATES[1] * 1e6) + len(exp) * PER_FILE_S[0]) / 3600:.1f}-"
        f"{(size / (RATES[0] * 1e6) + len(exp) * PER_FILE_S[1]) / 3600:.1f} h")

    # ---- claims ---------------------------------------------------------------------------------------
    say("")
    say("## claims (planned files)")
    fc = {}
    want = {e["relpath"] for e in exp} | {r["relpath"] for r in cell}
    with io.open(os.path.join(P.CODES, "file_claims.csv"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["relpath"] in want:
                fc[r["relpath"]] = r
    a1_by_rel = {r["relpath"]: r for r in a1}
    xt = collections.Counter()
    for e in exp:
        a1v = a1_by_rel[e["relpath"]]["claim_verdict"]
        a1v = {"CONFIRMED (animal in protocol)": "A1 animal in protocol", "no claim": "A1 no claim",
               "claim, protocol valid (no animal id to check)": "A1 protocol, no animal",
               "C (animal not in claimed protocol)": "A1 animal NOT in protocol"}.get(a1v, a1v)
        xt[(a1v, e["verdict"])] += 1
    L.extend(table(["A1 (by path)", "engine verdict (A2)", "files"], [[a, b, n] for (a, b), n in sorted(xt.items())]))
    # A1's own counts (over ITS population: the 5,258 distinct microscopy files it found not in production,
    # re-saves counted as in production), followed to where each file ends up here
    say("")
    say("A1's population (distinct, not in production by A1) -> where each file ends up, by A1's claim verdict:")
    first = {}
    for r in a1:
        first.setdefault(r["sha256"], r)
    a1pop = [r for r in first.values() if r["vs_production"] == "not in production"
             or r["vs_production"].startswith("same instrument+second")]
    by_sha_e = {e["sha256"]: e for e in exp}
    exc_s = {x["sha256"]: x for x in exc}
    oos_s = {r["sha256"] for r in oos}
    fate = collections.Counter()
    for r in a1pop:
        a1v = r["claim_verdict"]
        if r["sha256"] in by_sha_e:
            where = "planned, engine " + by_sha_e[r["sha256"]]["verdict"]
        elif r["sha256"] in exc_s:
            where = "excluded: " + exc_s[r["sha256"]]["reason"]
        elif r["sha256"] in oos_s:
            where = "out of scope"
        else:
            where = "?"
        fate[(a1v, where)] += 1
    L.extend(table(["A1 verdict", "here", "files"], [[a, b, n] for (a, b), n in sorted(fate.items())]))
    say(f"A1 population: {len(a1pop)}; A1 'no claim': {sum(1 for r in a1pop if r['claim_verdict'] == 'no claim')}; "
        f"A1 'animal not in claimed protocol': {sum(1 for r in a1pop if r['claim_verdict'].startswith('C '))}")
    why = collections.Counter()
    for e in exp:
        if e["verdict"] != "C":
            continue
        t = fc[e["relpath"]]["conflict"]
        t = re.sub(r"animal \d+", "animal N", t)
        t = re.sub(r"ID ?\d+", "IDn", t)
        t = re.sub(r"\(terminal procedure.*|\(procedure-date.*", "(the DB dates do not separate them)", t)
        folder = "\\".join(e["relpath"].split("\\")[:-1])
        why[(t[:120], folder)] += 1
    say("")
    say("(C) planned files by reason and folder:")
    L.extend(table(["engine reason", "folder", "files"], [[a, b, n] for (a, b), n in why.most_common()]))
    nc = collections.Counter("\\".join(e["relpath"].split("\\")[:3]) for e in exp if e["verdict"] == "NO-CLAIM")
    say("")
    say("no-claim planned files by folder (3 levels):")
    L.extend(table(["folder", "files"], [[k, n] for k, n in nc.most_common()]))

    # ---- people (flagged, not assigned) ---------------------------------------------------------------
    say("")
    say("## people")
    say(f"researcher non-blank: {sum(1 for e in exp if e['researcher'])}; operator non-blank: "
        f"{sum(1 for e in exp if e['operator'])}")
    for frag in ("Microscopio\\Microscopio- MJesus Sanchez 2023\\", "Microscopio\\CELL OBS MARTA\\"):
        es = [e for e in exp if e["relpath"].startswith(frag)]
        say(f"planned files under {frag}: {len(es)} ({gbs(sum(int(e['size']) for e in es))} GB)")

    # ---- pixel check ----------------------------------------------------------------------------------
    say("")
    say("## same-acquisition groups (pixel check)")
    groups = collections.defaultdict(list)
    for r in cand:
        groups[r["group"]].append(r)
    say(f"groups {len(groups)}; members {len(cand)} ({sum(1 for r in cand if r['role'] == 'plan')} planned, "
        f"{sum(1 for r in cand if r['role'] == 'production')} production); "
        f"{gbs(sum(int(r['size']) for r in cand))} GB")
    say("classes: " + ", ".join(f"{k} {v}" for k, v in collections.Counter(d["class"] for d in dec).most_common()))
    say("incomplete (truncated) members: " + str(sum(1 for d in dec if d["complete"] != "Y")))
    acts = collections.Counter()
    by_sha = {e["sha256"]: e for e in exp}
    exc_by = {x["sha256"]: x for x in exc}
    for r in cand:
        if r["role"] != "plan":
            continue
        e = by_sha.get(r["sha256"])
        if e is not None:
            acts[e["same_acq_action"]] += 1
        else:
            x = exc_by.get(r["sha256"])
            acts[f"excluded:{x['reason'] if x else '?'}"] += 1
    say("planned members' outcome: " + ", ".join(f"{k} {v}" for k, v in acts.most_common()))

    # ---- lists -------------------------------------------------------------------------------------------
    P.wcsv(os.path.join(TASKS, "drive3_czi_nonraw_for_stream_p.csv"), P.NONRAW_D3_COLS, nonraw)
    pc_cols = ["group", "member", "role", "name", "relpath_or_acq_id", "size", "class", "parent", "parent_name",
               "via", "evidence", "complete", "complete_note", "has_scalebar", "plan_action", "plan_note"]
    cand_by = {(r["group"], r["member"]): r for r in cand}
    pcr = []
    for d in dec:
        c = cand_by.get((d["group"], d["member"]), {})
        e = by_sha.get(d["member"])
        x = exc_by.get(d["member"]) if e is None else None
        pcr.append({**d, "relpath_or_acq_id": (c.get("original_name", "").split("/", 1)[-1] if d["role"] == "plan"
                                              else d["member"]),
                    "plan_action": (e["same_acq_action"] if e else (x["reason"] if x else
                                    ("production (read only)" if d["role"] == "production" else "?"))),
                    "plan_note": (e["same_acq_note"] if e else (x["detail"] if x else ""))})
    P.wcsv(os.path.join(TASKS, "drive3_czi_pixel_classification.csv"), pc_cols, pcr)
    bl_cols = ["batch", "relpath", "size", "acquisition_datetime", "verdict", "claimed", "engine_reason", "a1_claim"]
    blank = [{"batch": e["batch"], "relpath": e["relpath"], "size": e["size"],
              "acquisition_datetime": e["acquisition_datetime"], "verdict": e["verdict"], "claimed": e["claimed"],
              "engine_reason": fc[e["relpath"]]["conflict"], "a1_claim": a1_by_rel[e["relpath"]]["claim_verdict"]}
             for e in exp if not e["project"]]
    P.wcsv(os.path.join(TASKS, "drive3_czi_blank_project_preview.csv"), bl_cols, blank)
    P.wcsv(os.path.join(TASKS, "drive3_czi_held.csv"), P.REPAIR_COLS, held)
    P.wcsv(os.path.join(TASKS, "drive3_czi_out_of_scope.csv"),
           ["relpath", "size", "sha256", "ext", "instrument", "serials", "stand", "czi_class", "acq_dt", "reason",
            "in_production"], oos)
    say("")
    say(f"lists: nonraw {len(nonraw)}, pixel classification {len(pcr)}, blank-project preview {len(blank)}, "
        f"held {len(held)}, out of scope {len(oos)}")
    say("")
    say("plan_summary: " + json.dumps({k: summ[k] for k in ("expected", "expected_gb", "nonraw", "production_repairs",
                                                            "undecided_rows", "max_farm_path", "registry_rows",
                                                            "production_hashes_mtime") if k in summ}))
    txt = "\n".join(L) + "\n"
    with io.open(os.path.join(out, "report_tables.txt"), "w", encoding="utf-8") as f:
        f.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
