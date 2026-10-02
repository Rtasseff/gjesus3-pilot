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

Run:  python tools/test_drives_ingest_plan.py
"""
import os
import sys

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


def main():
    test_resave_key()
    test_person_fields()
    test_zwsi_initials()
    test_canonical_order()
    test_archive_keys()
    test_check_3c_exemption()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)})")
        return 1
    print("ALL PASS (drives ingest plan rules)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
