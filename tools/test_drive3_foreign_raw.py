#!/usr/bin/env python3
"""test_drive3_foreign_raw.py -- the M. Jesus drive's raw from outside instruments (tasks/drive3_foreign_raw_gate.md):
the Biodonostia Axioscan as XMIC (profile drive3x_2026-10) and the fourth placement batch (Leica, the processed .czi).

  1. The profile: XMIC from the reference entry, the model and source written literally, its own configs, a
     smaller pilot; drives 1+2 and stream C keep theirs.
  2. A1's rows are re-fingerprinted against the CURRENT reference only in this profile; a row A1 named stays named.
  3. x_groups.classify_members: identical stored tiles -> one original (the earliest ZEN save) and its re-saves; a
     truncated copy -> a subset of the complete one; no tile shared -> distinct; partly shared -> ambiguous.
  4. The measured triple: a tie broken by the claim, a moved origin, an interrupted copy dropped (rule 1b).
  5. The label readings: proposed ones change nothing; L1 fills a blank row; L2 replaces a Confirmed folder claim the
     label contradicts; a label without a protocol is never used; a Confirmed claim is never filled by L1.
  6. The placement lists: the Leica files go to their claim's active project, the processed .czi with no claim to
     the holding folder ("no claim", mappable); the Axioscan files are never placed; a derivative needs its parent's
     XMIC ACQ-ID.
  7. The 1121 tree's README gains the Leica note; every other tree keeps its text.

Run:  python tools/test_drive3_foreign_raw.py
"""
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "drive_staging"))
sys.path.insert(0, os.path.join(HERE, "drive_staging", "drive3"))
import ingest_plan as P  # noqa: E402
import historical_paths as H  # noqa: E402
import x_groups as X  # noqa: E402
import x_placement as XP  # noqa: E402

FAILS = []


def check(cond, msg):
    print(f"  {'ok:  ' if cond else 'FAIL:'} {msg}")
    if not cond:
        FAILS.append(msg)


def test_profile():
    print("test_profile")
    try:
        check(P.XMIC_MODEL == "Axio Imager.Z2" and P.XMIC_SOURCE == "collaborator:Charite"
              and P.PILOT == P.PILOT_DEFAULT, "drives 1+2 (the default): the Charite model and source, the full pilot")
        P.use_profile("drive3x_2026-10")
        check(P.INSTRUMENTS == {"EXTERNAL:Axioscan7-Biodonostia": "XMIC"}, "XMIC from the reference entry only")
        check(P.XMIC_MODEL == "Axioscan 7" and P.XMIC_SOURCE == "collaborator:Biodonostia",
              "the model the file carries, and the origin in data_source's vocabulary")
        check(P.config_file("X01") == "tools/configs/drives3x_2026-10/drives3x_X01.yaml" and P.NEW_PROJECT is None,
              "its own configs (X01..), no project created")
        check(P.PILOT["per_project"] == 1 and P.PILOT["deepest"] == 1, "a smaller pilot (an Axioscan file is 0.3-3 GB)")
        check(P.STAGING.lower().startswith("j:\\_staging_drive3_mj") and "xmic" in P.LOCAL.lower()
              and "xmic" in P.OUT.lower(), "the staged copy is read; its own mirror and plan on D:")
        check(not P.PEOPLE_BY_FOLDER and not P.OPERATOR_TOPS, "no person from a folder (none names one)")
        P.use_profile("drive3_2026-10")
        check(P.INSTRUMENTS == {"CELL": "CELL"} and P.PILOT == P.PILOT_DEFAULT and not P.PROFILE.get("refingerprint"),
              "stream C's profile is unchanged")
    finally:
        P.use_profile(P.DEFAULT_PROFILE)
    check(P.XMIC_MODEL == "Axio Imager.Z2", "use_profile restores the default's XMIC model")


def a1row(serials, keys, stand, inst="unknown"):
    return {"relpath": "Microscopio\\x.czi", "serials": serials, "stand_keys": keys, "stand": stand,
            "instrument": inst}


def test_refingerprint():
    print("test_refingerprint")
    try:
        P.use_profile("drive3x_2026-10")
        r = a1row("4661000340", "Pollux;UprightFixedStage", "Axioscan 7")
        check(P.a1_instrument(r) == "EXTERNAL:Axioscan7-Biodonostia", "A1's `unknown` Axioscan -> the new entry")
        check(P.a1_instrument(a1row("", "Inverted", "Axio Observer.Z1 / 7", "CELL")) == "CELL",
              "a row A1 named stays named")
        check(P.a1_instrument(a1row("4661000999", "Pollux", "Axioscan 7")) == "unknown", "an unknown serial stays unknown")
        try:
            P.a1_instrument(a1row("4661000718", "Pollux", "Axioscan 7", "CELL"))
            check(False, "a reference that re-names an A1 instrument stops the plan")
        except SystemExit:
            check(True, "a reference that re-names an A1 instrument stops the plan")
        P.use_profile("drive3_2026-10")
        check(P.a1_instrument(a1row("4661000340", "Pollux;UprightFixedStage", "Axioscan 7")) == "unknown",
              "stream C's profile reads A1 as it is (its plan is frozen)")
    finally:
        P.use_profile(P.DEFAULT_PROFILE)


def mem(mid, name, tiles, created, missing=0, inside=True, scalebar=False, top="Microscopio"):
    return {"member": mid, "name": name, "original_name": f"drive3_MJesus-MFB/{top}/f/{name}",
            "creation": dt.datetime.fromisoformat(created) if created else None, "scalebar": scalebar,
            "tiles": tiles, "missing": missing, "inside": inside}


def tiles(n, dy=0, dx=0, pay="h"):
    """n tiles in the key form x_groups.read_tiles writes: scene|M|start (C,Y,X,S)|shape."""
    return {f"0|{i}|0,{100 + dy},{2056 * i + dx},0|1,2464,2056,3": f"{pay}{i}" for i in range(n)}


def decide_with(ms, projects=None):
    """Run ingest_plan.same_acquisition_actions on x_groups' facts, as plan_drive3 does."""
    projects = projects or {}
    cl = X.classify_members(ms)
    sig = P.group_signature([m["member"] for m in ms])
    dec = {m["member"]: {"member": m["member"], "class": cl[m["member"]][0], "parent": cl[m["member"]][1],
                         "name": m["name"], "complete": cl[m["member"]][3], "group_signature": sig,
                         "has_scalebar": str(m["scalebar"])} for m in ms}
    rows = [{"sha256": m["member"], "original_name": m["original_name"], "project": projects.get(m["member"], ""),
             "_c": {"kind": "loose", "in_backup": "/biomaGUNE MJ/" in m["original_name"],
                    "project": projects.get(m["member"], ""), "researcher": "",
                    "path": m["original_name"].split("/", 1)[1].replace("/", "\\"), "drive": "D3"}} for m in ms]
    return cl, P.same_acquisition_actions(rows, [], dec)


def test_classify():
    print("test_classify")
    T = tiles(4)
    scan = mem("a" * 64, "2024_10_24__4469-1.czi", T, "2024-10-25T07:45:25+00:00")
    resave = mem("b" * 64, "2024_10_24__4469-1.czi", dict(T), "2024-10-28T11:33:53+00:00", top="biomaGUNE MJ")
    out = X.classify_members([resave, scan])
    check(out[scan["member"]][0] == "original" and out[resave["member"]][:2] == ("identical re-save", scan["member"]),
          "same tiles: the earliest ZEN save is the original, the later one its re-save")
    renamed = mem("c" * 64, "ID2_0424_H+L 1.czi", dict(T), "2025-02-20T10:00:00+00:00")
    out = X.classify_members([renamed, scan])
    check(out[renamed["member"]][0] == "identical re-save" and out[renamed["member"]][1] == scan["member"],
          "a renamed copy with the same tiles: an identical re-save of the earlier save")
    moved = mem("d" * 64, "ID1_0424_H+L.czi", tiles(4, dy=-37681, dx=577322), "2024-10-25T07:45:25+00:00")
    out = X.classify_members([scan, moved])
    check({out[scan["member"]][0], out[moved["member"]][0]} == {"original", "identical re-save"}
          and "origin moved" in (out[scan["member"]][2] + out[moved["member"]][2]),
          "the same tiles with every position shifted by one offset (a re-save that moved the origin): identical")
    sb = mem("e" * 64, "x.czi", dict(T), "2025-03-01T00:00:00+00:00", scalebar=True)
    check(X.classify_members([scan, sb])[sb["member"]][0] == "scale-bar copy", "same tiles + a ScaleBar layer: scale-bar copy")
    trunc = mem("f" * 64, "2024_10_24__4469-1.czi", dict(list(T.items())[:3]), "2024-10-25T07:45:25+00:00",
                missing=1, inside=False)
    out = X.classify_members([trunc, scan, renamed])
    check(out[trunc["member"]][0] == "export: subset" and out[trunc["member"]][1] == scan["member"]
          and out[trunc["member"]][3] == "N", "a truncated copy whose readable tiles are all in a complete one: a subset")
    other = mem("1" * 64, "y.czi", tiles(2, pay="z"), "2024-10-25T07:45:25+00:00")
    out = X.classify_members([scan, other])
    check(out[other["member"]][0] == "distinct" and out[scan["member"]][0] == "distinct",
          "no stored tile shared: both distinct (two slides or scenes in one second; both kept)")
    mixed = mem("2" * 64, "z.czi", dict(list(T.items())[:2], **{"0|8|0,0,0,0|1,2464,2056,3": "q"}),
                "2024-10-25T07:45:25+00:00")
    out = X.classify_members([scan, mixed])
    check(out[mixed["member"]][0] == "ambiguous" and out[scan["member"]][0] == "ambiguous",
          "tiles partly shared: the group is ambiguous (kept and flagged)")
    # what ingest_plan does with these facts
    _, acts = decide_with([scan, resave, trunc])
    check(acts[scan["member"]][0] == P.ACTION_KEEP and acts[resave["member"]][0] == P.ACTION_DROP
          and acts[trunc["member"]][0] == P.ACTION_DROP,
          "ingest_plan: the scan kept, its same-name re-save and its truncated copy dropped")


def test_triple():
    """The group of 2025-02-14T12:13:49, as measured: `ID1_0424_H+L.czi` and the escaner's `2025_02_14__5234.czi`
    (saved by ZEN at the same moment, the same tiles at moved positions), and `HE\\2025_02_14__5234.czi`, an
    interrupted copy of the escaner's file (czifile cannot open it; its subblocks are all the escaner file's)."""
    print("test_triple")
    t0 = "2025-02-19T12:40:58.937053+01:00"
    id1 = dict(mem("a" * 64, "ID1_0424_H+L.czi", tiles(5), t0), original_name="drive3_MJesus-MFB/Microscopio/HE/ID1_0424_H+L.czi")
    esc = dict(mem("b" * 64, "2025_02_14__5234.czi", tiles(5, dy=37681, dx=-577322), t0),
               original_name="drive3_MJesus-MFB/Microscopio/biodonostia/escaner/H&E/2025_02_14__5234.czi")
    cut = dict(mem("c" * 64, "2025_02_14__5234.czi", {}, t0, missing=1, inside=False), prefix_of="b" * 64,
               missing_note="interrupted copy: 3 of 5 subblocks, each byte-identical to 2025_02_14__5234.czi's")
    cl, acts = decide_with([id1, esc, cut], projects={"a" * 64: "AE-biomaGUNE-0424"})
    check(cl[id1["member"]][0] == "original" and "canonical rule" in cl[id1["member"]][2],
          "a tie on the ZEN save time: the claimed copy is the original (stream C's canonical rule)")
    check(cl[cut["member"]][:2] == ("export: subset", id1["member"]) and cl[cut["member"]][3] == "N",
          "the interrupted copy: a subset of the set's original, incomplete")
    check(acts[id1["member"]][0] == P.ACTION_KEEP and acts[esc["member"]][0] == P.ACTION_NONRAW
          and acts[cut["member"]][0] == P.ACTION_DROP,
          "ID1 kept; the escaner copy (another name) to the project folder; the interrupted copy dropped, as it "
          "has the name of a complete identical copy (rule 1b, 2026-10-08)")
    cut2 = dict(cut, name="other.czi", member="d" * 64)
    _, acts = decide_with([id1, esc, cut2], projects={"a" * 64: "AE-biomaGUNE-0424"})
    check(acts[cut2["member"]][0] == P.ACTION_NONRAW,
          "a truncated copy under a name no complete copy has: non-raw, as before (stream C's rule unchanged)")


def lrow(sha, verdict, project="", animal=""):
    return {"sha256": sha, "verdict": verdict, "project": project, "drive": "D3", "relpath": "M\\x.czi",
            "subject_id": f"{animal}-{project}" if animal else "", "subject_alias": "", "subject_animal": "",
            "sample_type": "", "notes": "x", "conflict": ""}


def test_label_readings():
    print("test_label_readings")
    try:
        P.use_profile("drive3x_2026-10")
        labels = {"1" * 64: {"sha256": "1" * 64, "label": "ID15 H / 0522 H&E / 3mo", "protocol": "0522", "animal": "15",
                             "reading": "L1"},
                  "2" * 64: {"sha256": "2" * 64, "label": "ID43 HL / H&E / 1422", "protocol": "1422", "animal": "43",
                             "reading": "L2"},
                  "3" * 64: {"sha256": "3" * 64, "label": "202 II / HE / NMX", "protocol": "", "animal": "",
                             "reading": ""},
                  "4" * 64: {"sha256": "4" * 64, "label": "ID1 H+L / H&E / 0424", "protocol": "0424", "animal": "1",
                             "reading": "L1"}}
        rd = [{"reading": "L1", "status": "proposed", "kind": "label", "prefix": "", "project": "", "summary": "",
               "evidence": "", "decided": ""},
              {"reading": "L2", "status": "proposed", "kind": "label-overrule", "prefix": "", "project": "",
               "summary": "", "evidence": "", "decided": ""}]

        def rows():
            return [lrow("1" * 64, "NO-CLAIM"), lrow("2" * 64, "CONFIRMED", "AE-biomaGUNE-0522"),
                    lrow("3" * 64, "NO-CLAIM"), lrow("4" * 64, "CONFIRMED", "AE-biomaGUNE-0424", "1")]
        es = rows()
        applied, would = P.apply_readings(es, rd, labels)
        check(not applied and would == {"L1": 1, "L2": 1} and [e["project"] for e in es] ==
              ["", "AE-biomaGUNE-0522", "", "AE-biomaGUNE-0424"], "PROPOSED readings change nothing (only counted)")
        acc = [dict(r, status="accepted", decided="2026-10-09 coordinator") for r in rd]
        es = rows()
        applied, _ = P.apply_readings(es, acc, labels)
        a, b, c, d = es
        check(a["project"] == "AE-biomaGUNE-0522" and a["subject_id"] == "15-AE-biomaGUNE-0522"
              and a["verdict"] == "READING-L1" and a["sample_type"] == "tissue" and "ID15 H / 0522" in a["notes"],
              "L1 accepted: the blank row takes the label's protocol and animal; the note quotes the label")
        check(b["project"] == "AE-biomaGUNE-1422" and b["subject_id"] == "43-AE-biomaGUNE-1422"
              and b["verdict"] == "READING-L2" and "CONFIRMED AE-biomaGUNE-0522, replaced" in b["notes"],
              "L2 accepted: the Confirmed folder claim the label contradicts is replaced, and the note says so")
        check(c["project"] == "" and c["verdict"] == "NO-CLAIM", "a label that names no protocol is never used")
        check(d["verdict"] == "CONFIRMED" and applied == {"L1": 1, "L2": 1}, "L1 never touches a Confirmed claim")
        es = [lrow("1" * 64, "CONFIRMED", "AE-biomaGUNE-0522", "15")]
        check(P.apply_readings(es, acc, {"1" * 64: dict(labels["1" * 64], reading="L2")})[0] == {},
              "L2 leaves a Confirmed claim the label agrees with")
    finally:
        P.use_profile(P.DEFAULT_PROFILE)


def test_placement_lists():
    print("test_placement_lists")
    oos = [{"relpath": "Pili y Mili\\Proyecto 1121 London\\E\\a.lif", "sha256": "a" * 64, "size": "10", "ext": ".lif",
            "serials": "8100000207", "czi_class": "lif"},
           {"relpath": "Microscopio\\M\\m204lung.czi", "sha256": "b" * 64, "size": "5", "ext": ".czi", "serials": "",
            "czi_class": "czi-processed"},
           {"relpath": "Microscopio\\biodonostia\\x.czi", "sha256": "c" * 64, "size": "7", "ext": ".czi",
            "serials": "4661000340", "czi_class": "czi-raw"}]
    a2 = {"Pili y Mili\\Proyecto 1121 London\\E\\a.lif": {"sha256": "a" * 64, "size": "10", "cls": "raw-microscopy",
                                                         "verdict": "CONFIRMED", "proposed_project": "AE-biomaGUNE-1121",
                                                         "claim_id": "CL-2441"},
          "Microscopio\\M\\m204lung.czi": {"sha256": "b" * 64, "size": "5", "cls": "raw-microscopy", "verdict": "NO-CLAIM",
                                           "proposed_project": "", "claim_id": ""}}
    rows, probs = XP.leica_and_processed(oos, a2, {"AE-biomaGUNE-1121": {"status": "active"}})
    by = {r["relpath"]: r for r in rows}
    check(not probs and len(rows) == 2, "the Axioscan file is never placed (it is registered as XMIC)")
    lif = by["Pili y Mili\\Proyecto 1121 London\\E\\a.lif"]
    check(lif["project"] == "AE-biomaGUNE-1121" and lif["kind"] == "other" and "Leica TCS SP8" in lif["reason"]
          and lif["claim_id"] == "CL-2441", "a Leica file: its claim's active project, with the reason")
    czi = by["Microscopio\\M\\m204lung.czi"]
    check(czi["project"] == "" and czi["reason"] == "no claim" and czi["class"] == "czi-processed",
          "the processed .czi with no claim: the holding folder, reason exactly `no claim` (mappable later)")
    rows, probs = XP.leica_and_processed(oos, a2, {"AE-biomaGUNE-1121": {"status": "closed"}})
    check(probs and not any(r["relpath"].endswith(".lif") for r in rows), "a closed claim project stops the Leica row")
    nonraw = [{"relpath": "HE\\ID2.czi", "sha256": "d" * 64, "class": "identical re-save",
               "parent_original_name": "drive3_MJesus-MFB/escaner/5235.czi", "destination_project": "AE-biomaGUNE-0424"}]
    reg = [{"acq_id": "ACQ-20250214-XMIC-002", "original_name": "drive3_MJesus-MFB/escaner/5235.czi",
            "ingest_config": "tools/configs/drives3x_2026-10/drives3x_X02.yaml"}]
    rows, probs = XP.nonraw_rows(nonraw, reg, "tools/configs/drives3x_2026-10/drives3x_")
    check(not probs and rows[0]["parent_acq_ids"] == "ACQ-20250214-XMIC-002" and rows[0]["kind"] == "derivative"
          and rows[0]["project"] == "AE-biomaGUNE-0424", "a derivative is handed over under its parent's XMIC ACQ-ID")
    rows, probs = XP.nonraw_rows(nonraw, [], "tools/configs/drives3x_2026-10/drives3x_")
    check(probs and not rows, "before the XMIC ingest there is no parent: refused")


def test_readme_note():
    print("test_readme_note")
    b = lambda p: f"projects\\{p}\\working\\historical_drives"  # noqa: E731
    r = H.project_readme(b("AE-biomaGUNE-1121"))
    check(r.startswith(H.PROJECT_README) and "Leica TCS SP8" in r and "not register" in r,
          "1121: the shared text, then the Leica note")
    check(H.project_readme(b("AE-biomaGUNE-1019")) == H.PROJECT_README and "Leica" not in H.project_readme(b("AE-biomaGUNE-0522")),
          "every other tree keeps its own text")
    check(all(len(x) <= 79 for x in H.PROJECT_README_NOTES["AE-biomaGUNE-1121"].splitlines()), "lines fit 79 characters")


def main():
    test_profile()
    test_refingerprint()
    test_classify()
    test_triple()
    test_label_readings()
    test_placement_lists()
    test_readme_note()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)})")
        return 1
    print("ALL PASS (drive 3 foreign raw: XMIC profile, x_groups, label readings, placement lists)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
