"""Stream N, step 4: what the discovery fallback fix changes, measured on the whole S:\\gnuclear snapshot.

Read-only. Loads the `main` version of tools/ni_gnuclear_discover.py (git show) beside this
branch's version and runs analyse() of both over every file of the snapshot manifest (2,485 files),
grouped into acquisitions exactly as ingest/ni_flat.discover groups them (canonical = shallowest
path, then lexicographic), against the facility DB's protocol-code set (one SELECT).

Then, as discover() decides: an acquisition is SKIPPED when (ts14, modality) is already registered
(the registry snapshot taken by n02), HELD BACK when it has no project, else listed.

Reports:
  - regression: every acquisition whose main-version project was non-empty, or that stays held back,
    gives an IDENTICAL analyse() row under the fix (all fields);
  - the release: acquisitions held back under main that get a project under the fix, split into
    the 100 of stream N and the others; each other one is checked in the facility DB (SELECT):
    is (project, animal) found, and does it log a procedure within 3 days of the scan.

Writes out\\fix_effect_acqs.csv and out\\fix_released_others.csv.
"""
import collections
import csv
import datetime as dt
import glob
import importlib.util
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True
WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))      # the repository root (tools/drive_staging/drive3/<this>)
TOOLS = os.path.join(WT, "tools")
OUT = r"D:\projects\gjesus3\drive3_streams\petct\out"
SCR = r"D:\projects\gjesus3\drive3_streams\petct\scripts\_main_copy"
INPUTS = sorted(glob.glob(os.path.join(OUT, "_inputs", "2*")))[-1]
sys.path.insert(0, TOOLS)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    os.makedirs(SCR, exist_ok=True)
    src = subprocess.run(["git", "-C", WT, "show", "main:tools/ni_gnuclear_discover.py"],
                         capture_output=True, check=True).stdout
    old_path = os.path.join(SCR, "ni_gnuclear_discover_main.py")
    with open(old_path, "wb") as f:
        f.write(src)
    old = load("nd_main", old_path)
    new = load("nd_branch", os.path.join(TOOLS, "ni_gnuclear_discover.py"))
    import animal_db
    conn = animal_db.get_connection()
    try:
        valid = new.valid_protocol_codes(conn)
        old._VALID_CODES = valid

        snap = [json.loads(l) for l in open(os.path.join(INPUTS, "_manifest.jsonl"), encoding="utf-8")]
        reg = list(csv.DictReader(open(os.path.join(INPUTS, "registry_raw.csv"), encoding="utf-8-sig", newline="")))
        registered = set()
        for r in reg:
            inst = (r.get("instrument") or "").strip().upper()
            if inst in ("PET", "CT", "SPECT", "OI"):
                d = "".join(c for c in r.get("acquisition_datetime", "") if c.isdigit())[:14]
                if len(d) == 14:
                    registered.add((d, inst))
        ours100 = {r["acq_key"] for r in csv.DictReader(open(os.path.join(OUT, "acq_inventory.csv"), encoding="utf-8"))
                   if r["coverage"].startswith("only in the S")}

        by_key = collections.defaultdict(list)
        n_regress_files = 0
        for j in snap:
            rel = j["rel"]
            a_old = old.analyse(rel, 0, valid)
            a_new = new.analyse(rel, 0, valid)
            if a_old is None or a_new is None:
                assert a_old is None and a_new is None, rel
                continue
            by_key[a_new["acq_key"]].append((rel, a_old, a_new))
        rows, regress = [], []
        for key in sorted(by_key):
            ents = sorted(by_key[key], key=lambda e: (e[0].count("/"), e[0]))
            rel, a_old, a_new = ents[0]
            reg_hit = (key[:14], a_new["modality"]) in registered
            # discover()'s own order: no project -> held back FIRST, then (ts14, modality) registered -> skipped
            st_old = "held-back" if not a_old["project"] else ("skipped-registered" if reg_hit else "listed")
            st_new = "held-back" if not a_new["project"] else ("skipped-registered" if reg_hit else "listed")
            # regression: per file, every field equal unless this file's project changed none -> code
            for r_, o_, n_ in ents:
                changed = {k for k in o_ if o_[k] != n_[k]}
                allowed = {"project", "flags", "facility_keys"} if (not o_["project"] and n_["project"]) else set()
                if changed - allowed:
                    regress.append((r_, sorted(changed - allowed)))
                if not o_["project"] and n_["project"]:
                    if not n_["flags"].startswith(o_["flags"]) or "project-recovered:none->" not in n_["flags"]:
                        regress.append((r_, ["flags not old+recovered"]))
            rows.append({"acq_key": key, "canonical_rel": rel, "n_files": len(ents),
                         "researcher": a_new["researcher"], "series": a_new["series"],
                         "subject_folder": a_new["subject_folder"], "animals": a_new["animals"],
                         "project_main": a_old["project"], "project_fix": a_new["project"],
                         "flags_fix": a_new["flags"], "status_main": st_old, "status_fix": st_new,
                         "stream_n_100": "Y" if key in ours100 else ""})
        released = [r for r in rows if r["status_main"] == "held-back" and r["status_fix"] == "listed"]
        released_but_registered = [r for r in rows if r["status_main"] == "held-back"
                                   and r["status_fix"] == "skipped-registered"]
        rel_ours = [r for r in released if r["stream_n_100"]]
        rel_other = [r for r in released if not r["stream_n_100"]]

        # DB check of every released (project, animal) pair
        cache = {}
        for r in released:
            ts = dt.datetime.strptime(r["acq_key"][:14], "%Y%m%d%H%M%S").date()
            verdicts = []
            for a in [x for x in r["animals"].split(",") if x]:
                num = int("".join(c for c in a if c.isdigit()) or "0")
                k = (r["project_fix"], num)
                if k not in cache:
                    res = animal_db.lookup(k[0], k[1], conn=conn, use_cache=False)
                    if res.status == "unreachable":
                        raise SystemExit("facility DB unreachable")
                    cache[k] = res
                res = cache[k]
                if res.status != "found":
                    verdicts.append(f"{num}:not-in-{k[0]}")
                    continue
                near = []
                for pr in (res.subject or {}).get("procedures", []):
                    try:
                        d = dt.date.fromisoformat(str(pr.get("date", ""))[:10])
                    except ValueError:
                        continue
                    if abs((d - ts).days) <= 3:
                        near.append(f"{pr.get('type')}@{d}")
                verdicts.append(f"{num}:found" + (f"({'; '.join(near)})" if near else "(nothing logged within 3 d)"))
            r["db_check"] = " | ".join(verdicts) if verdicts else "no animal parsed"
    finally:
        conn.close()

    with open(os.path.join(OUT, "fix_effect_acqs.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) + ["db_check"], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(OUT, "fix_released_others.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) + ["db_check"], extrasaction="ignore")
        w.writeheader()
        w.writerows(rel_other)

    print(f"inputs: {INPUTS}")
    print(f"snapshot files {len(snap)}; acquisitions {len(rows)}")
    print("status main:", collections.Counter(r["status_main"] for r in rows))
    print("status fix :", collections.Counter(r["status_fix"] for r in rows))
    print(f"regressions (a field changed that may not): {len(regress)}")
    for x in regress[:20]:
        print("   ", x)
    print(f"\nreleased by the fix: {len(released)} = stream N's {len(rel_ours)} + {len(rel_other)} others")
    print(f"  stream N 100 released: {len(rel_ours)} of {len(ours100)};"
          f" not released: {sorted(ours100 - {r['acq_key'] for r in rel_ours})}")
    print("  stream N by recovered project:", collections.Counter(r["project_fix"] for r in rel_ours))
    print("  others by researcher x recovered project:")
    for k, v in sorted(collections.Counter((r["researcher"], r["project_fix"]) for r in rel_other).items()):
        print(f"     {v:4d}  {k}")
    print("  others: DB verdict per acquisition:")
    def verdict(r):
        d = r["db_check"]
        if d == "no animal parsed":
            return "no animal parsed (needs a subject mapping)"
        if "not-in-" in d:
            return "an animal NOT in the recovered protocol"
        if "nothing logged" in d:
            return "animal in protocol, nothing logged within 3 d"
        return "confirmed (animal in protocol + procedure within 3 d)"
    for k, v in collections.Counter(verdict(r) for r in rel_other).most_common():
        print(f"     {v:4d}  {k}")
    print("\nheld back under main but (ts14, modality) already registered (another reconstruction of a"
          f" registered scan): released by the fix into 'skipped': {len(released_but_registered)}")
    for k, v in sorted(collections.Counter((r["researcher"], r["project_fix"]) for r in released_but_registered).items()):
        print(f"     {v:4d}  {k}")
    still = [r for r in rows if r["status_fix"] == "held-back"]
    print(f"\nstill held back under the fix: {len(still)} (was {sum(1 for r in rows if r['status_main']=='held-back')})")


if __name__ == "__main__":
    main()
