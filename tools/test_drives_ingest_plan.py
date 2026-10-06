#!/usr/bin/env python3
"""test_drives_ingest_plan.py -- the per-file rules of the historical-drives .czi ingest
(tools/drive_staging/ingest_plan.py), pinned so a re-run of the plan cannot drift from what Ryan
decided on 2026-09-29.

  1. The operators' top folders give the OPERATOR, not the researcher (AINHIZE / Marta under
     `Cell observer` on D1 and `CELL OBSERVER 2` on D2), case-insensitively, recorded as written;
     an inner person folder stays the researcher; elsewhere the operator is blank.
  2. ZWSI operator initials come from the AxioScan filename slot `MFB_<initials>_<project>_...`.
  3. The canonical copy: a claimed project first, then a loose non-backup copy, then a researcher,
     the shorter path, D1, lexicographic; and a loose copy beats an archive member.
  4. Every archive gets a distinct extraction folder.
  5. (2026-10-06, the third drive) The profiles: the default is the frozen drives 1+2 ingest, unchanged;
     drive3_2026-10 rebinds every drive-specific constant and back.
  6. Drive 3's canonical copy prefers a copy outside `biomaGUNE MJ` (Ryan's "last"); it has no operator
     top folders.
  7. Drive 3's same-acquisition rule (same_acquisition_actions): every pixel-check outcome maps to keep,
     keep-flag, drop, non-raw, hold or undecided exactly as tasks/drive3_czi_gate.md says.
  8. The local mirror copy keeps a file only when its bytes hash to the manifest's SHA-256.

Run:  python tools/test_drives_ingest_plan.py
"""
import hashlib
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "drive_staging"))
import ingest_plan as P  # noqa: E402
import ingest_check as C  # noqa: E402

FAILS = []


def check(cond, msg):
    print(f"  {'ok:  ' if cond else 'FAIL:'} {msg}")
    if not cond:
        FAILS.append(msg)


def parts(p):
    return p.split("\\")


def test_person_fields():
    print("test_person_fields")
    f = P.person_fields
    check(f("D1", parts(r"Cell observer\AINHIZE\1123\ID 7-20\x.czi"), "AINHIZE") == ("", "AINHIZE"),
          "AINHIZE top folder, no inner person -> researcher blank, operator AINHIZE")
    check(f("D1", parts(r"Cell observer\AINHIZE\LAURA\1321\x.czi"), "LAURA") == ("LAURA", "AINHIZE"),
          "AINHIZE > LAURA -> researcher LAURA (as written), operator AINHIZE")
    check(f("D2", parts(r"CELL OBSERVER 2\Marta\Irene\Irene_0522_Metfor\x.czi"), "Irene") == ("Irene", "Marta"),
          "D2 Marta > Irene -> researcher Irene, operator Marta")
    check(f("D1", parts(r"Cell observer\marta\x.czi"), "Marta") == ("", "marta"),
          "matched case-insensitively, operator recorded as written")
    check(f("D1", parts(r"Cell observer\Laura\x.czi"), "Laura") == ("Laura", ""),
          "a non-operator person folder: researcher kept, operator blank")
    check(f("D2", parts(r"2025-10-02 - Toshiba EXT (Backup)\Proyectos_Laboratorio_Laura\x.czi"), "Laura") == ("Laura", ""),
          "elsewhere the operator is blank")
    check(f("D1", parts(r"Former students\AINHIZE\x.czi"), "AINHIZE") == ("AINHIZE", ""),
          "only the four named top folders are operator folders")
    check(f("D1", parts(r"Cell observer\Marta\Infartos Ruben_PR.zip"), "Marta") == ("", "Marta"),
          "an archive under an operator folder (members inherit the archive's path)")


def test_zwsi_initials():
    print("test_zwsi_initials")
    m = P.MFB_RE.match("MFB_AUA_1123_ID205Lu_TM_10x_ROI lobulo 1.czi")
    check(bool(m) and m.group(1) == "AUA" and f"{m.group(2)}_{m.group(3)}" == "1123_ID205Lu",
          "MFB_AUA_1123_ID205Lu_... -> operator AUA, sample 1123_ID205Lu")
    check(P.MFB_RE.match("2026_01_12__10_33__0024_30H.czi") is None, "an auto-named AxioScan file has no initials")


def copy(**kw):
    c = {"kind": "loose", "in_backup": False, "project": "", "researcher": "", "path": "a\\x.czi", "drive": "D1"}
    c.update(kw)
    return c


def test_canonical_order():
    print("test_canonical_order")
    pick = lambda cs: min(cs, key=P.canon_key)  # noqa: E731
    a = copy(path="short.czi")
    b = copy(project="AE-biomaGUNE-1123", path="a\\much\\longer\\path\\x.czi", in_backup=True)
    check(pick([a, b]) is b, "rule 1: a copy whose claim gives a project wins, even from the backup")
    a = copy(in_backup=True, path="b.czi")
    b = copy(path="a\\very\\long\\x.czi")
    check(pick([a, b]) is b, "rule 2: outside the backup beats inside it")
    a = copy(kind="member", path="z.zip\\x.czi")
    b = copy(in_backup=True, path="2025-10-02 - Toshiba EXT (Backup)\\deep\\deeper\\x.czi")
    check(pick([a, b]) is b, "refinement: a loose backup copy beats an archive member (no extraction)")
    check(min([a, b], key=lambda c: P.canon_key(c, strict=True)) is a,
          "the rule as written would have picked the shorter member path (reported, never used)")
    a = copy(path="a\\x.czi")
    b = copy(researcher="LAURA", path="a\\longer\\x.czi")
    check(pick([a, b]) is b, "rule 3: a non-blank researcher beats a shorter path")
    a = copy(path="a\\b\\x.czi", drive="D1")
    b = copy(path="a\\x.czi", drive="D2")
    check(pick([a, b]) is b, "rule 4: the shorter path beats D1")
    a = copy(path="a\\x.czi", drive="D2")
    b = copy(path="b\\x.czi", drive="D1")
    check(pick([a, b]) is b, "rule 5: D1 before D2 at equal length")


def test_archive_keys():
    print("test_archive_keys")
    k1 = P.archive_key("D1", r"Drive zuri 170823.zip")
    k2 = P.archive_key("D2", r"Drive zuri 170823.zip")
    k3 = P.archive_key("D1", r"x\Drive zuri 170823.zip")
    check(len({k1, k2, k3}) == 3, "same archive name on another drive / folder -> distinct folders")


def test_resave_key():
    print("test_resave_key")
    k = P.resave_key
    a = k("CELL", "2023-07-26T09:12:33.1234567Z", "drive1_FRIO-X6/a/B/4h_HepG2_20X_6.czi")
    check(a == k("CELL", "2023-07-26T09:12:33Z", r"UPTAKE\4h_hepg2_20x_6.CZI"),
          "same acquisition: timestamp to the second, filename case- and folder-blind")
    check(a != k("LSM9", "2023-07-26T09:12:33Z", "4h_HepG2_20X_6.czi"), "another instrument is another acquisition")
    check(a != k("CELL", "2023-07-26T09:12:34Z", "4h_HepG2_20X_6.czi"), "another second is another acquisition")
    check(P.GROUP_NOTE.format(m=1, s="") == "shares its acquisition timestamp with 1 other file in this "
          "ingest (likely a ZEN scene split, stitched copy or extract)", "the R4 notes clause")


def test_check_3c_exemption():
    print("test_check_3c_exemption")
    g = "CELL|2023-06-23T10:00:00.1234567Z"
    exp = {  # the frozen plan: an export planned in B05 and a planned sibling of it
        "d/Kidney-HE.czi": {"acq_group": g},
        "d/Other-group.czi": {"acq_group": "CELL|2023-06-02T09:00:00Z"},
        "d/No-group.czi": {"acq_group": ""},
    }
    e = {"acq_group": g}
    ex, hits = C.split_3c_hits(e, [{"acq_id": "ACQ-1", "original_name": "d/Kidney-HE.czi"}], exp)
    check(len(ex) == 1 and not hits, "production row = a planned row, same acq_group -> exempt, no hit")
    ex, hits = C.split_3c_hits(e, [{"acq_id": "ACQ-2", "original_name": "d/NOT-IN-THE-PLAN.czi"}], exp)
    check(not ex and len(hits) == 1, "production row not in the plan (pre-existing / operator ingest) -> still a hit")
    ex, hits = C.split_3c_hits(e, [{"acq_id": "ACQ-3", "original_name": "d/Other-group.czi"}], exp)
    check(not ex and len(hits) == 1, "planned row of another acq_group -> still a hit")
    ex, hits = C.split_3c_hits({"acq_group": ""}, [{"acq_id": "ACQ-4", "original_name": "d/No-group.czi"}], exp)
    check(not ex and len(hits) == 1, "checked file in no R4 group -> never exempt")
    ex, hits = C.split_3c_hits(e, [{"acq_id": "ACQ-1", "original_name": "d/Kidney-HE.czi"},
                                   {"acq_id": "ACQ-2", "original_name": "d/NOT-IN-THE-PLAN.czi"}], exp)
    check(len(ex) == 1 and len(hits) == 1, "mixed: the exempt one is listed, the other still fails")


def test_check_3c_decided_exemption():
    print("test_check_3c_decided_exemption")
    e = {"acq_group": "CELL|2023-05-30T09:24:00"}
    prod = [{"acq_id": "ACQ-20230530-CELL-011", "original_name": "drive1_FRIO-X6/x/a-1.czi"}]
    ex, hits = C.split_3c_hits(e, prod, {}, decided=frozenset({"ACQ-20230530-CELL-011"}))
    check(len(ex) == 1 and not hits, "drive 3: a production row of the file's decided pixel-check group is exempt")
    ex, hits = C.split_3c_hits(e, prod, {}, decided=frozenset({"ACQ-20230530-CELL-099"}))
    check(not ex and len(hits) == 1, "a production row the pixel check never saw is still a hit")


def test_profiles():
    print("test_profiles")
    try:
        check(P.PROFILE_NAME == "drives_2026-09", "the default profile is the drives 1+2 ingest")
        check(P.CONFIG_DIR_REL == "tools/configs/drives_2026-09" and P.CONFIG_PREFIX == "drives_",
              "drives 1+2 configs: tools/configs/drives_2026-09/drives_Bxx.yaml")
        check(P.config_file("B05") == "tools/configs/drives_2026-09/drives_B05.yaml",
              "config_file = the registry's ingest_config form (frozen rows point at it)")
        check(list(P.DRIVES) == ["D1", "D2"] and P.DRIVES["D2"][1] == "drive2_MFB-Disco-2", "drives 1+2 labels")
        check(P.NEW_PROJECT == "AE-biomaGUNE-0118" and P.BATCH_CAP == 400 * 10**9 and P.BATCH_PREFIX == "B",
              "drives 1+2: one new project, 400 GB batches B01..")
        check(P.BACKUP_TOP == "2025-10-02 - Toshiba EXT (Backup)", "drives 1+2: the Toshiba backup is deprioritised")
        check(P.RESAVE_DECISIONS.get("dc8e8fe75a7356ee8ad229d3b329ed5ebff72dfcaca6bf7555f1bea0dd2bc497")
              == "hold-production-truncated", "drives 1+2 keep their hand-recorded re-save decisions")
        P.use_profile("drive3_2026-10")
        check(list(P.DRIVES) == ["D3"] and P.DRIVES["D3"][1] == "drive3_MJesus-MFB", "drive 3: one drive, its label")
        check(P.config_file("C01") == "tools/configs/drives3_2026-10/drives3_C01.yaml",
              "drive 3 configs: tools/configs/drives3_2026-10/drives3_Cxx.yaml")
        check(P.NEW_PROJECT is None and not P.OPERATOR_TOPS and P.INSTRUMENTS == {"CELL": "CELL"},
              "drive 3: no project created, no operator folders, Cell Observer only")
        check(P.STAGING.lower().startswith("j:\\_staging_drive3_mj") and P.LOCAL.lower().startswith("d:\\"),
              "drive 3: staged on J: (read), mirrored to D:")
        check(P.BATCH_CAP == 250 * 10**9 and P.SAME_ACQ_MODE == "decide" and not P.RESAVE_DECISIONS,
              "drive 3: 250 GB batches; same-acquisition groups decided by the pixel check")
        check(os.path.basename(P.CONFIG_DIR) == "drives3_2026-10", "CONFIG_DIR follows the profile")
    finally:
        P.use_profile(P.DEFAULT_PROFILE)
    check(P.PROFILE_NAME == "drives_2026-09" and list(P.DRIVES) == ["D1", "D2"], "use_profile restores the default")


def test_drive3_canonical_and_people():
    print("test_drive3_canonical_and_people")
    try:
        P.use_profile("drive3_2026-10")
        mk = lambda path, **kw: copy(path=path, drive="D3", in_backup=P.in_deprioritised(path), **kw)  # noqa: E731
        a = mk("biomaGUNE MJ\\a\\x.czi")
        b = mk("Microscopio\\CELL OBS MARTA\\much\\longer\\folder\\x.czi")
        check(min([a, b], key=P.canon_key) is b, "outside `biomaGUNE MJ` beats inside it, even when longer")
        a = mk("biomaGUNE MJ\\a\\x.czi", project="AE-biomaGUNE-0424")
        check(min([a, b], key=P.canon_key) is a, "a claimed project still comes first")
        a = mk("Microscopio\\a\\x.czi")
        check(min([a, b], key=P.canon_key) is a, "then the shorter path")
        check(P.person_fields("D3", r"Microscopio\CELL OBS MARTA\x.czi".split("\\"), "") == ("", ""),
              "drive 3 has no operator folders: `CELL OBS MARTA` gives no operator (names in longer folder names "
              "are flagged, not assigned)")
        rel = ("Microscopio\\Microscopio- MJesus Sanchez 2023\\Machos vs Hembras\\Controles Male (Nmx and SuHx)\\"
               "4- Controles Male (Nmx and SuHx)- ki67 and SMA\\230125 M\u00e1s muestras\\ID138-ki67SMA-230125-20x-5.czi")
        n = P.farm_path_len({"original_name": "drive3_MJesus-MFB/" + rel.replace("\\", "/")})
        check(n == 256 and n <= P.MAX_FARM_PATH < 260, f"the deepest drive-3 farm path ({n}) fits MAX_PATH")
    finally:
        P.use_profile(P.DEFAULT_PROFILE)


def d(member, cls, name, parent="", complete="Y", role="plan"):
    return {"member": member, "class": cls, "name": name, "parent": parent, "complete": complete, "role": role}


def decide(plan, prod, rows):
    """Run same_acquisition_actions with decisions stamped for exactly this membership."""
    sig = P.group_signature([r["sha256"] for r in plan] + [p["acq_id"] for p in prod])
    dec = {r["member"]: dict(r, group_signature=sig) for r in rows}
    return P.same_acquisition_actions(plan, prod, dec)


def prow(sha, path, project=""):
    c = {"kind": "loose", "in_backup": False, "project": project, "researcher": "", "path": path, "drive": "D3"}
    return {"sha256": sha, "original_name": "drive3_MJesus-MFB/" + path.replace("\\", "/"), "project": project, "_c": c}


def test_same_acquisition_actions():
    print("test_same_acquisition_actions")
    try:
        P.use_profile("drive3_2026-10")
        K, F, D, N, H, U = (P.ACTION_KEEP, P.ACTION_FLAG, P.ACTION_DROP, P.ACTION_NONRAW, P.ACTION_HOLD,
                            P.ACTION_UNDECIDED)
        a = prow("a" * 64, "Microscopio\\Female Diets\\0619\\x.czi", project="AE-biomaGUNE-0619")
        b = prow("b" * 64, "Microscopio\\Machos vs Hembras\\x.czi")
        # not decided / stale
        out = P.same_acquisition_actions([a, b], [], {})
        check(all(v[0] == U for v in out.values()), "no pixel decision -> undecided")
        stale = {a["sha256"]: dict(d(a["sha256"], "original", "x.czi"), group_signature="0" * 16),
                 b["sha256"]: dict(d(b["sha256"], "identical re-save", "x.czi", a["sha256"]), group_signature="0" * 16)}
        check(all(v[0] == U for v in P.same_acquisition_actions([a, b], [], stale).values()),
              "a decision made for another membership (stale signature) -> undecided")
        # same name, pixel-identical: the canonical rule keeps one (the claimed project), drops the other
        out = decide([a, b], [], [d(b["sha256"], "original", "x.czi"),
                                  d(a["sha256"], "identical re-save", "x.czi", b["sha256"])])
        check(out[a["sha256"]][0] == K and out[b["sha256"]] [0] == D and out[b["sha256"]][1] == a["sha256"],
              "same-name identical pair: the canonical (claimed) one kept, the other a dropped re-save (gate R2)")
        # same name, the twins differ only by a scale-bar annotation layer: the CLEAN one is the raw record (Ryan
        # 2026-10-01), even when the canonical rule would pick the annotated (claimed) copy; the annotated one is a
        # scale-bar copy for the project folder; whichever the pixel check called the root
        for root_is_clean in (True, False):
            if root_is_clean:
                rows_ = [dict(d(b["sha256"], "original", "x.czi"), has_scalebar="False"),
                         dict(d(a["sha256"], "scale-bar copy", "x.czi", b["sha256"]), has_scalebar="True")]
            else:
                rows_ = [dict(d(a["sha256"], "original", "x.czi"), has_scalebar="True"),
                         dict(d(b["sha256"], "identical re-save", "x.czi", a["sha256"]), has_scalebar="False")]
            out = decide([a, b], [], rows_)
            check(out[b["sha256"]][0] == K and out[a["sha256"]][0] == N and out[a["sha256"]][1] == b["sha256"],
                  f"same-name twins differing by a scale bar: clean kept, annotated -> non-raw (root clean: {root_is_clean})")
        both = [dict(d(b["sha256"], "original", "x.czi"), has_scalebar="True"),
                dict(d(a["sha256"], "scale-bar copy", "x.czi", b["sha256"]), has_scalebar="True")]
        out = decide([a, b], [], both)
        check(out[a["sha256"]][0] == K and out[b["sha256"]][0] == D,
              "both twins annotated: the canonical one kept, the other a plain re-save (gate R2)")
        # same name: a complete file is kept before a truncated one, even against the canonical order
        out = decide([a, b], [], [d(b["sha256"], "original", "x.czi"),
                                  d(a["sha256"], "export: subset", "x.czi", b["sha256"], complete="N")])
        check(out[a["sha256"]][0] == D and out[b["sha256"]][0] == K,
              "a truncated same-name copy is dropped; the complete one is the acquisition")
        out = decide([a, b], [], [d(a["sha256"], "original", "x.czi"),
                                  d(b["sha256"], "identical re-save", "x.czi", a["sha256"], complete="N")])
        check(out[a["sha256"]][0] == K and out[b["sha256"]][0] == D, "identical but truncated twin: dropped")
        # renamed re-save, scale-bar copy, crop: non-raw, parent = the kept file
        c = prow("c" * 64, "Microscopio\\Female Diets\\0619\\x-copy.czi")
        s = prow("5" * 64, "Microscopio\\Female Diets\\0619\\x-scale.czi")
        k = prow("6" * 64, "Microscopio\\Female Diets\\0619\\ROI.czi")
        out = decide([a, c, s, k], [], [d(a["sha256"], "original", "x.czi"),
                                        d(c["sha256"], "identical re-save", "x-copy.czi", a["sha256"]),
                                        d(s["sha256"], "scale-bar copy", "x-scale.czi", a["sha256"]),
                                        d(k["sha256"], "export: crop", "ROI.czi", a["sha256"])])
        check(out[a["sha256"]][0] == K and all(out[x["sha256"]][0] == N and out[x["sha256"]][1] == a["sha256"]
                                               for x in (c, s, k)),
              "renamed re-save, scale-bar copy and crop -> non-raw, under the original")
        # a derivative of a same-name twin that is dropped points at the twin that is kept
        out = decide([a, b, k], [], [d(b["sha256"], "original", "x.czi"),
                                     d(a["sha256"], "identical re-save", "x.czi", b["sha256"]),
                                     d(k["sha256"], "export: crop", "ROI.czi", b["sha256"])])
        check(out[k["sha256"]] [0] == N and out[k["sha256"]][1] == a["sha256"],
              "a crop's parent is the kept member of its original's identical set")
        # distinct siblings, ambiguous
        out = decide([a, c], [], [d(a["sha256"], "distinct", "x.czi"), d(c["sha256"], "distinct", "x-copy.czi")])
        check(out[a["sha256"]][0] == K and out[c["sha256"]][0] == K, "two distinct scenes: both kept")
        out = decide([a, c], [], [d(a["sha256"], "ambiguous", "x.czi"), d(c["sha256"], "ambiguous", "x-copy.czi")])
        check(out[a["sha256"]][0] == F and out[c["sha256"]][0] == F, "ambiguous: kept and flagged")
        # production in the group
        P1 = {"acq_id": "ACQ-20230707-CELL-001", "original_name": "drive1_FRIO-X6/m/x.czi", "project_id": ""}
        out = decide([a], [P1], [d(P1["acq_id"], "original", "x.czi", role="production"),
                                 d(a["sha256"], "identical re-save", "x.czi", P1["acq_id"])])
        check(out[a["sha256"]][0] == D, "same name, pixel-identical to production: a dropped re-save (R1)")
        out = decide([a], [P1], [d(a["sha256"], "original", "x.czi"),
                                 d(P1["acq_id"], "export: subset", "x.czi", a["sha256"], complete="N", role="production")])
        check(out[a["sha256"]][0] == H, "production holds a TRUNCATED copy under the same name -> hold (repair)")
        out = decide([a], [P1], [d(a["sha256"], "original", "x.czi"),
                                 d(P1["acq_id"], "export: crop", "x.czi", a["sha256"], role="production")])
        check(out[a["sha256"]][0] == H and out[a["sha256"]][1] == P1["acq_id"],
              "production holds a 1-tile derivative under the same name -> hold, not a second ACQ-ID")
        out = decide([a], [P1], [d(a["sha256"], "distinct", "x.czi"), d(P1["acq_id"], "distinct", "x.czi", role="production")])
        check(out[a["sha256"]][0] == H, "same name and second as production, other pixels -> hold for the coordinator")
        inc = dict(d(P1["acq_id"], "distinct", "x.czi", complete="N", role="production"),
                   complete_note="1 of 1 level-0 tiles unreadable: downsampled: stored 310 x 235 px")
        out = decide([a], [P1], [d(a["sha256"], "distinct", "x.czi"), inc])
        check(out[a["sha256"]][0] == H and "INCOMPLETE" in out[a["sha256"]][2] and "downsampled" in out[a["sha256"]][2],
              "production holds only a downsampled preview under the same name -> hold, the note says so (repair)")
        P2 = dict(P1, original_name="drive1_FRIO-X6/m/x-1.czi")
        out = decide([a], [P2], [d(a["sha256"], "distinct", "x.czi"), d(P2["acq_id"], "distinct", "x-1.czi", role="production")])
        check(out[a["sha256"]][0] == K, "production holds another scene of the second (other name): kept")
        out = decide([a], [P2], [d(P2["acq_id"], "original", "x-1.czi", role="production"),
                                 d(a["sha256"], "export: crop", "x.czi", P2["acq_id"])])
        check(out[a["sha256"]][0] == N and out[a["sha256"]][1] == P2["acq_id"],
              "a crop of a production acquisition (other name) -> non-raw under it")
        out = decide([a], [P2], [d(a["sha256"], "original", "x.czi"),
                                 d(P2["acq_id"], "export: crop", "x-1.czi", a["sha256"], role="production")])
        check(out[a["sha256"]][0] == F, "production holds a crop of it under another name: kept, flagged")
        out = decide([a, b], [], [d(a["sha256"], "original", "x.czi"), d(b["sha256"], "export: crop", "x.czi", "nobody")])
        check(all(v[0] == U for v in out.values()), "a parent that is no root of the group -> undecided")
    finally:
        P.use_profile(P.DEFAULT_PROFILE)


def test_readings():
    print("test_readings")
    try:
        P.use_profile("drive3_2026-10")
        pre = "biomaGUNE MJ\\PAH aged_Proyecto 0424 & 1019 (female and male)\\PAH aged Female_Proyecto 0424"
        why = ("nested claims disagree: nearest 0424 (CONFIRMED) vs outer 1019; animal 7 is found in BOTH 0424 "
               "and 1019, and the DB dates do not separate them")

        def row(rel, verdict="C", conflict=why, project=""):
            return {"relpath": rel, "verdict": verdict, "conflict": conflict, "project": project, "drive": "D3",
                    "subject_id": "", "subject_alias": "", "subject_animal": "", "sample_type": "", "notes": "x"}
        r5 = {"reading": "R5", "status": "proposed", "kind": "both-protocols-near", "prefix": pre,
              "project": "AE-biomaGUNE-0424", "summary": "s", "evidence": "e", "decided": ""}
        rows = [row(pre + "\\Raw data\\a.czi")]
        applied, would = P.apply_readings(rows, [r5])
        check(not applied and would["R5"] == 1 and rows[0]["project"] == "" and rows[0]["verdict"] == "C",
              "a PROPOSED reading changes nothing (it is only counted)")
        r5a = dict(r5, status="accepted", decided="2026-10-07 coordinator")
        rows = [row(pre + "\\Raw data\\a.czi"),
                row(pre + "\\Raw data\\b.czi", conflict="file's animal ID7 is not in protocol 0424 -> C"),
                row(pre + "\\Raw data\\c.czi", verdict="CONFIRMED", project="AE-biomaGUNE-0424"),
                row("Microscopio\\elsewhere\\d.czi")]
        applied, would = P.apply_readings(rows, [r5a])
        a, b, c, d = rows
        check(a["project"] == "AE-biomaGUNE-0424" and a["verdict"] == "READING-R5" and
              a["subject_id"] == "7-AE-biomaGUNE-0424" and a["sample_type"] == "tissue",
              "ACCEPTED: the nearer claim, and animal N of that protocol as the subject")
        check(b["project"] == "" and b["verdict"] == "C",
              "a (C) file with another engine reason under the same folder is not filled")
        check(c["verdict"] == "CONFIRMED", "a Confirmed claim is never touched")
        check(d["project"] == "" and applied["R5"] == 1, "a file outside the reading's folder is not touched")
    finally:
        P.use_profile(P.DEFAULT_PROFILE)


def test_cut_even():
    print("test_cut_even")
    rows = [{"size": s} for s in (100, 90, 80, 70, 60, 50, 40, 30)]          # 520 in all
    ch = P.cut_even(rows, 250)
    sizes = [sum(r["size"] for r in c) for c in ch]
    check(len(ch) == 3 and all(x <= 250 for x in sizes) and sum(sizes) == 520,
          f"the fewest chunks under the cap ({sizes})")
    check(max(sizes) - min(sizes) <= 50, f"cuts land near the even target 173 ({sizes})")
    check([r for c in ch for r in c] == rows, "order kept, nothing lost or repeated")
    check(len(P.cut_even([{"size": 10}], 250)) == 1, "one small row: one chunk")
    ch = P.cut_even([{"size": 240}, {"size": 20}, {"size": 240}], 250)
    check(all(sum(r["size"] for r in c) <= 250 for c in ch), "a cut that undershoots is retried with more chunks")


def test_copy_verified():
    print("test_copy_verified")
    tmp = tempfile.mkdtemp(prefix="d3_copy_")
    try:
        src = os.path.join(tmp, "src", "x.czi")
        os.makedirs(os.path.dirname(src))
        data = os.urandom(300_000)
        with open(src, "wb") as f:
            f.write(data)
        sha = hashlib.sha256(data).hexdigest()
        dst = os.path.join(tmp, "mirror", "deep", "x.czi")
        ok, _ = P.copy_verified(src, dst, sha, len(data), mtime_ns=1_600_000_000 * 10**9)
        check(ok and open(dst, "rb").read() == data and int(os.path.getmtime(dst)) == 1_600_000_000,
              "the manifest's hash and size: kept, mtime from the manifest")
        dst2 = os.path.join(tmp, "mirror", "bad.czi")
        ok, why = P.copy_verified(src, dst2, "0" * 64, len(data))
        check(not ok and not os.path.exists(dst2) and not os.path.exists(dst2 + ".part"),
              "a hash that is not the manifest's: nothing kept, no .part left")
        check(open(src, "rb").read() == data, "the source is only read")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    test_resave_key()
    test_person_fields()
    test_zwsi_initials()
    test_canonical_order()
    test_archive_keys()
    test_check_3c_exemption()
    test_check_3c_decided_exemption()
    test_profiles()
    test_drive3_canonical_and_people()
    test_same_acquisition_actions()
    test_readings()
    test_cut_even()
    test_copy_verified()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)})")
        return 1
    print("ALL PASS (drives ingest plan rules)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
