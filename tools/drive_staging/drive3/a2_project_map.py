#!/usr/bin/env python3
"""a2_project_map.py -- HANDOFF §6 items 1 and 2: every code-bearing folder on drive 3 against today's
registry, and a proposed description for every matched project.

Inputs (read-only): a2\\claims\\claims.csv (a2_claims.py), a2\\files.csv (a2_files.py), the live
registry_projects.csv and the project folders on J:.

Outputs (a2\\):
  claims_today.csv   every claim the engine made (non-shadowed and shadowed), with today's project
                     (id, status, folder on the NAS)
  project_map.csv    the drive's project folders: the OUTERMOST folders whose own name carries a code (the
                     depth-2 `Proyecto XXXX ...` folders; deeper in Microscopio / Otros), with the per-file
                     outcome below each (which project each file's claim resolves to, or C / none)
  foreign_codes.csv  claims deeper down that name a DIFFERENT protocol from their project folder
  descriptions.csv   per matched project: the drive's wordings, today's description, the proposal

THE DESCRIPTION FORMAT (one rule for every row):
  "<primary wording>[ (also named <w2>; <w3>)]. <today's description, unchanged>"
  * primary wording = the project folder's own name, preferring `Pili y Mili\\Proyecto XXXX <words>` (the
    group's shared convention), then MRI, Otros, PET, Microscopio, biomaGUNE MJ;
  * only names that add words to the code count (`Proyecto 0619`, `0619` do not), and only names that
    name ONE protocol (`PAH diets_Proyecto 0619 & 0522` names two, so it describes neither alone);
  * no change is proposed where today's description already contains the primary wording.
"""
import collections
import os
import re

import a2_common as C

ORDER = ["Pili y Mili", "MRI", "Otros", "PET", "Microscopio", "biomaGUNE MJ"]
CODE_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")


def wording_ok(name, code):
    """A folder name that describes the project: carries the code once, names no other 4-digit code,
    and has words besides `Proyecto` and the code."""
    codes = set(CODE_RE.findall(name))
    if codes != {code}:
        return False
    rest = re.sub(r"(?i)proyecto|project|" + code, " ", name)
    return bool(re.search(r"[A-Za-zÀ-ɏ]{2,}", rest))


def main():
    C.stdout_utf8()
    projects = C.load_projects()
    by_id = {r["project_id"]: r for r in projects.values()}
    proj_dir = os.path.join(C.NAS, "projects")
    present = {d.lower() for d in os.listdir(proj_dir)}

    def today(pname):
        row = projects.get(pname)
        if not row:
            return {"project_id": "NEW" if pname else "", "status": "", "folder_exists": ""}
        return {"project_id": row["project_id"], "status": row["status"],
                "folder_exists": "Y" if C.project_folder_name(row).lower() in present else "N"}

    claims = list(C.it(os.path.join(C.OUT, "claims", "claims.csv")))
    out = []
    for c in claims:
        t = today(c["proposed_project"])
        out.append({"claim_id": c["claim_id"], "claim_root": c["claim_root"], "depth": c["claim_root"].count("\\") + 1,
                    "token": c["token"], "phrasing": c["phrasing"], "verdict": c["verdict"],
                    "proposed_project": c["proposed_project"], "project_id": t["project_id"],
                    "project_status": t["status"], "folder_exists": t["folder_exists"],
                    "n_files": c["n_files"], "bytes": c["bytes"], "date_min": c["date_min"], "date_max": c["date_max"],
                    "corrected_from": c["corrected_from"], "flags": c["flags"][:300], "evidence": c["evidence"][:600]})
    C.wcsv(C.out_path("claims_today.csv"), list(out[0].keys()), out)
    C.say(f"claims_today.csv: {len(out)} claims")

    files = list(C.it(os.path.join(C.OUT, "files.csv")))
    # ---- the drive's project folders --------------------------------------------------------------
    # = the OUTERMOST folder-level claim roots (a folder whose own name carries the code: keyword,
    # folder-exact/-head/-chunk phrasing; not a session/animal-level study name), at any depth. For
    # Pili y Mili / MRI / PET / biomaGUNE MJ these are the depth-2 `Proyecto XXXX ...` folders; in
    # Microscopio and Otros the codes sit deeper.
    cand = collections.defaultdict(set)
    for c in claims:
        if c["source"] != "folder" or c["phrasing"] == "animal-paired":
            continue
        if c["claim_root"].count("\\") < 1:
            continue
        cand[c["claim_root"]].add(c["token"])
    roots2 = {}
    for k in cand:
        parts = k.split("\\")
        if any("\\".join(parts[:i]) in cand for i in range(2, len(parts))):
            continue                                   # an ancestor folder already carries a code
        roots2[k] = cand[k]
    agg = collections.defaultdict(lambda: collections.Counter())
    aggb = collections.defaultdict(lambda: collections.Counter())
    tot = collections.Counter()
    totb = collections.Counter()
    a2n = collections.Counter()
    a2b = collections.Counter()

    def folder_of(relpath):
        parts = relpath.split("\\")
        for i in range(2, len(parts)):
            k = "\\".join(parts[:i])
            if k in roots2:
                return k
        return None

    for f in files:
        key = folder_of(f["relpath"])
        if key is None:
            continue
        out_k = f["proposed_project"] or f"<{f['verdict']}>"
        agg[key][out_k] += 1
        aggb[key][out_k] += int(f["size"])
        tot[key] += 1
        totb[key] += int(f["size"])
        if f["owner"] == "A2":
            a2n[key] += 1
            a2b[key] += int(f["size"])
    pm = []
    for key in sorted(roots2, key=lambda k: (ORDER.index(k.split("\\")[0]) if k.split("\\")[0] in ORDER else 9, k)):
        toks = sorted(roots2[key])
        # the folder's own verdict(s): the engine's claim AT this root
        own = [c for c in claims if c["claim_root"] == key and c["source"] == "folder"]
        verdicts = "; ".join(sorted({f"{c['token']}:{c['verdict']}" for c in own}))
        outcome = "; ".join(f"{k} {n} ({aggb[key][k] / 1e9:.2f} GB)" for k, n in agg[key].most_common())
        main_proj = ""
        for k, _n in sorted(aggb[key].items(), key=lambda kv: -kv[1]):
            if not k.startswith("<"):
                main_proj = k
                break
        t = today(main_proj)
        pm.append({"folder": key, "codes_in_name": " ".join(toks), "engine_verdict_at_folder": verdicts,
                   "files": tot[key], "bytes": totb[key], "gb": C.gb(totb[key]),
                   "a2_files": a2n[key], "a2_gb": C.gb(a2b[key]),
                   "main_project": main_proj, "project_id": t["project_id"], "project_status": t["status"],
                   "project_folder_exists": t["folder_exists"], "per_file_outcome": outcome})
    C.wcsv(C.out_path("project_map.csv"), list(pm[0].keys()), pm)
    C.say(f"project_map.csv: {len(pm)} outermost code-bearing folders")

    # ---- foreign codes below a project folder -----------------------------------------------------
    fc = collections.defaultdict(lambda: [0, 0, set()])
    for f in files:
        key = folder_of(f["relpath"])
        if key is None or not f["proposed_project"]:
            continue
        code = f["proposed_project"][-4:]
        if code in roots2[key]:
            continue
        g = fc[(key, f["proposed_project"])]
        g[0] += 1
        g[1] += int(f["size"])
        if len(g[2]) < 3:
            g[2].add("\\".join(f["relpath"][len(key) + 1:].split("\\")[:3]))
    frows = [{"project_folder": k[0], "codes_in_name": " ".join(sorted(roots2[k[0]])), "other_project": k[1],
              "project_id": today(k[1])["project_id"], "files": v[0], "gb": C.gb(v[1]),
              "examples": " | ".join(sorted(v[2]))} for k, v in sorted(fc.items())]
    C.wcsv(C.out_path("foreign_codes.csv"), ["project_folder", "codes_in_name", "other_project", "project_id",
                                             "files", "gb", "examples"], frows)
    C.say(f"foreign_codes.csv: {len(frows)} (folder, other project) pairs")

    # ---- descriptions ---------------------------------------------------------------------------------
    words = collections.defaultdict(list)   # project -> [(top order, folder name, where)]
    for key, toks in roots2.items():
        if key.count("\\") != 1:
            continue    # only the drive's project folders (top\X) name a project; deeper ones name experiments
        top, name = key.split("\\", 1)
        for tok in toks:
            pname = f"AE-biomaGUNE-{tok}"
            if pname not in projects:
                pname = next((p for p in projects if p.endswith(tok) and p.startswith("Project-")), pname)
            if wording_ok(name, tok):
                words[pname].append((ORDER.index(top) if top in ORDER else 9, name.strip(), key))
    matched = collections.Counter()
    for f in files:
        if f["proposed_project"]:
            matched[f["proposed_project"]] += 1
    drows = []
    for pname in sorted(set(matched) | set(words)):
        row = projects.get(pname)
        cur = row["description"] if row else ""
        ws = sorted(set(words.get(pname, [])))
        seen, uniq = set(), []
        for o, w, where in ws:
            k = re.sub(r"\s+", " ", w).lower()
            if k not in seen:
                seen.add(k)
                uniq.append((o, re.sub(r"\s+", " ", w), where))
        allw = "; ".join(f"{w} [{where}]" for _o, w, where in uniq)
        if not uniq:
            proposal, note = cur, "no change: no folder on the drive gives this project a descriptive name"
        elif pname == "AE-biomaGUNE-0118":
            proposal, note = cur, ("PENDING Ryan: the drive names 0118 twice ('Proyecto 0118 Monocrotalina', "
                                   "'Proyecto 0118 (Ratas hipoxia)'); ruled 2026-09-30 as two projects, while "
                                   "AE-biomaGUNE-0118 already exists described as Monocrotalina -- see the report's 0118 options")
        else:
            primary = uniq[0][1]
            others = [w for _o, w, _wh in uniq[1:]]
            core = re.sub(r"(?i)^\s*(proyecto|project)\s*", "", primary).strip().lower()
            if primary.lower() in cur.lower() or core in cur.lower():
                proposal, note = cur, "no change: today's description already carries the drive's wording"
            else:
                also = f" (also named {'; '.join(others)})" if others else ""
                proposal = f"{primary}{also}. {cur}".strip()
                note = "prepend the drive's wording; today's text kept unchanged after it"
        drows.append({"project": pname, "project_id": row["project_id"] if row else "NEW",
                      "status": row["status"] if row else "", "files_on_drive": matched[pname],
                      "drive_wordings": allw, "today_description": cur, "proposed_description": proposal,
                      "note": note})
    C.wcsv(C.out_path("descriptions.csv"), list(drows[0].keys()), drows, bom=True)
    C.say(f"descriptions.csv: {len(drows)} projects, {sum(1 for d in drows if d['note'].startswith('prepend'))} with a proposal")


if __name__ == "__main__":
    main()
