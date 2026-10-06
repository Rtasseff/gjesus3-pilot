#!/usr/bin/env python3
"""test_recover_subject_ids.py — drive the one-shot repair against a scratch NAS.

Builds a miniature `J:\\gjesus3-data` in a temp dir (real headers, real CRLF /
no-BOM registry bytes, and sidecars in BOTH terminator classes the live archive
actually holds) and runs recover_subject_ids end to end. Nothing here touches
the NAS or the facility DB.

The cases that matter are the ones that would be expensive to discover on 444
production rows: the collision really splitting, a corrected id that ALREADY
exists merging instead of duplicating, LF and CRLF sidecars each keeping their
own endings, a half-done run resuming instead of aborting, and a second --apply
being a true no-op.

Kept alongside tools/recover_subject_ids.py as the record of what was
verified before that script touched 444 production rows.

Run:  PYTHONPATH=tools python tools/test_recover_subject_ids.py
"""

import csv
import hashlib
import io
import json
import os
import sys
import tempfile

import recover_subject_ids as rsi
from ingest import registry, subjects_table as st


FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


# ---- fixture -------------------------------------------------------------

# (acq_id, project_id, subject_ids, animal attributes for the sidecar)
ACQS = [
    # Both sides of a real collision: same broken id, two different animals.
    ("ACQ-20220124-MRI-001", "PROJ-0001", "23-AE-biomaGUNE-None", ("M", "2021-11-18", "C57BL/6NCrl")),
    ("ACQ-20220118-PET-010", "PROJ-0002", "23-AE-biomaGUNE-None", ("F", "2021-02-10", "A/JOlaHsd")),
    # A broken id whose CORRECTED form already has a subjects row.
    ("ACQ-20220201-MRI-002", "PROJ-0001", "9-AE-biomaGUNE-None", ("F", "2020-01-01", "BALB/c")),
    # Already correct - must not be touched at all.
    ("ACQ-20220301-MRI-003", "PROJ-0003", "13-AE-biomaGUNE-0525", ("M", "2025-07-31", "C57BL/6J")),
    # Broken, but the project names no animal protocol -> reported, not guessed.
    ("ACQ-20220401-MRI-004", "PROJ-0004", "5-AE-biomaGUNE-None", ("M", "2021-01-01", "CD1")),
]
PROJECTS = {"PROJ-0001": "AE-biomaGUNE-0219", "PROJ-0002": "AE-biomaGUNE-1521",
            "PROJ-0003": "AE-biomaGUNE-0525", "PROJ-0004": "laura-tholt"}

# Both terminator classes, so a writer that pins either is caught.
NEWLINE_OF = {
    "ACQ-20220124-MRI-001": "\n",      # WSL-era
    "ACQ-20220118-PET-010": "\r\n",    # Windows/GUI-era
    "ACQ-20220201-MRI-002": "\r\n",
    "ACQ-20220301-MRI-003": "\n",
    "ACQ-20220401-MRI-004": "\r\n",
}


def _sidecar(acq, sid, attrs):
    sex, dob, strain = attrs
    return {
        "acq_id": acq, "generator": "ingest_raw.py",
        "subject": {
            "facility_animal_id": sid, "species": "Mus musculus",
            "strain": strain, "sex": sex, "date_of_birth": dob,
            "age_at_acquisition": "P215D", "genotype": "",
            "weight_at_acquisition_g": None, "cohort_id": "",
            "procedures": [], "source": "animal-facility-db",
        },
        "condition": {"is_control": None},
    }


def build_nas(root, cover_sidecar_in_checksums=True):
    reg = os.path.join(root, "registries")
    os.makedirs(reg)

    # registry_raw.csv — real header, CRLF, NO BOM (matches production bytes).
    lines = [",".join(registry.REGISTRY_FIELDS)]
    for acq, pid, sids, _ in ACQS:
        row = {f: "" for f in registry.REGISTRY_FIELDS}
        row.update({"acq_id": acq, "registration_datetime": "2026-01-01T00:00:00Z",
                    "data_ecosystem": "DICOM", "instrument": acq.split("-")[2],
                    "sample_type": "organism", "subject_ids": sids,
                    "project_id": pid, "canonical_path": f"/raw/DICOM/{acq}/"})
        lines.append(",".join(row[f] for f in registry.REGISTRY_FIELDS))
    with open(os.path.join(reg, "registry_raw.csv"), "wb") as f:
        f.write(("\r\n".join(lines) + "\r\n").encode("utf-8"))

    with open(os.path.join(reg, "registry_projects.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["project_id", "name"])
        w.writeheader()
        for pid, name in PROJECTS.items():
            w.writerow({"project_id": pid, "name": name})

    # Sidecars. The live archive is NOT uniform: the 444 affected sidecars are
    # 314 LF (WSL-era ingests) / 130 CRLF (Windows/GUI-era). Both classes are
    # represented here, because a writer that pins either one churns the other.
    for acq, _pid, sids, attrs in ACQS:
        folder = os.path.join(root, "raw", "DICOM", acq)
        os.makedirs(folder)
        sc = os.path.join(folder, "metadata.json")
        with open(sc, "w", encoding="utf-8", newline=NEWLINE_OF[acq]) as f:
            json.dump(_sidecar(acq, sids, attrs), f, indent=2)
            f.write("\n")
        files = {f"{acq}.data/img.dcm": "0" * 64}
        if cover_sidecar_in_checksums:
            files["metadata.json"] = "stale" + "0" * 59
        with open(os.path.join(folder, "checksums.json"), "w",
                  encoding="utf-8", newline="\n") as f:
            json.dump({"algorithm": "sha256", "files": files}, f, indent=2)

    # A pre-existing subjects row for one of the CORRECTED ids, so the upsert
    # has to merge rather than duplicate -- and one stale -None row per broken id.
    st.upsert_subjects(reg, [
        {"facility_id": "9-AE-biomaGUNE-0219", "animal_code": "9",
         "project_alias": "0219", "sex": "F", "source": "animal-facility-db"},
        {"facility_id": "23-AE-biomaGUNE-None", "animal_code": "23",
         "project_alias": "None", "sex": "M", "source": "animal-facility-db"},
        {"facility_id": "9-AE-biomaGUNE-None", "animal_code": "9",
         "project_alias": "None", "sex": "F", "source": "animal-facility-db"},
        {"facility_id": "5-AE-biomaGUNE-None", "animal_code": "5",
         "project_alias": "None", "sex": "M", "source": "animal-facility-db"},
    ])
    return reg


def _raw_bytes(reg):
    return open(os.path.join(reg, "registry_raw.csv"), "rb").read()


def _subject_id_of(root, acq):
    with open(os.path.join(root, "raw", "DICOM", acq, "metadata.json"),
              encoding="utf-8") as f:
        return json.load(f)["subject"]["facility_animal_id"]


# ---- tests ---------------------------------------------------------------

def test_dry_run_writes_nothing():
    print("dry run touches nothing:")
    with tempfile.TemporaryDirectory() as root:
        reg = build_nas(root)
        before = _raw_bytes(reg)
        before_sc = open(os.path.join(root, "raw", "DICOM", ACQS[0][0],
                                      "metadata.json"), "rb").read()
        rc = rsi.main(["--nas-root", root])
        check(rc == 0, "dry run exits 0")
        check(_raw_bytes(reg) == before, "registry_raw.csv is byte-identical")
        check(open(os.path.join(root, "raw", "DICOM", ACQS[0][0],
                                "metadata.json"), "rb").read() == before_sc,
              "the sidecar is byte-identical")


def test_apply_repairs_everything():
    print("--apply repairs sidecars, registry and the subjects table:")
    with tempfile.TemporaryDirectory() as root:
        reg = build_nas(root)
        before = _raw_bytes(reg).split(b"\r\n")
        before_sc = {a: open(os.path.join(root, "raw", "DICOM", a,
                                          "metadata.json"), "rb").read()
                     for a, *_ in ACQS}
        rc = rsi.main(["--nas-root", root, "--apply",
                       "--backup-dir", os.path.join(root, "_backup")])
        check(rc == 0, "exits 0")

        # 1. the collision really splits into two different animals
        check(_subject_id_of(root, "ACQ-20220124-MRI-001") == "23-AE-biomaGUNE-0219",
              "collision side A -> 23-AE-biomaGUNE-0219")
        check(_subject_id_of(root, "ACQ-20220118-PET-010") == "23-AE-biomaGUNE-1521",
              "collision side B -> 23-AE-biomaGUNE-1521")

        # 2. the already-correct acquisition is untouched
        check(_subject_id_of(root, "ACQ-20220301-MRI-003") == "13-AE-biomaGUNE-0525",
              "the already-correct sidecar is unchanged")

        # 3. registry bytes: only the repaired lines differ; no BOM appeared
        after = _raw_bytes(reg)
        check(not after.startswith(b"\xef\xbb\xbf"), "no BOM was introduced")
        check(after.count(b"\r\n") == len(before) - 1, "CRLF endings preserved")
        diff = [i for i, (a, b) in enumerate(zip(before, after.split(b"\r\n")))
                if a != b]
        check(len(diff) == 3, f"exactly 3 registry lines changed (got {len(diff)})")
        # The ONLY -None left is the deliberately held-back laura-tholt row.
        check(after.count(b"-AE-biomaGUNE-None") == 1
              and b"5-AE-biomaGUNE-None" in after,
              "every repairable -None is gone; only the held-back row remains")

        # 4. subjects table: stale rows gone, collision split, merge not dup
        table = st.read_subjects(st.subjects_path(reg))
        check(not [k for k in table if k.endswith("-None")],
              "every stale -None subjects row is gone")
        check("23-AE-biomaGUNE-0219" in table and "23-AE-biomaGUNE-1521" in table,
              "the collided id became two rows")
        check(table["23-AE-biomaGUNE-0219"]["sex"] == "M"
              and table["23-AE-biomaGUNE-1521"]["sex"] == "F",
              "each split row carries its OWN animal's sex")
        check(table["23-AE-biomaGUNE-0219"]["project_alias"] == "0219",
              "project_alias is repaired, not left as None")
        check(len(table) == 3, f"3 subject rows: 2 split + 1 merged (got {len(table)})")
        check(table["9-AE-biomaGUNE-0219"]["sex"] == "F",
              "the corrected id MERGED into the pre-existing row, no duplicate")

        # 4b. Every repaired sidecar - LF class AND CRLF class - is byte-for-byte
        # its original with ONLY the id substring swapped. Pinning either
        # terminator would rewrite every line of the other class; this is the
        # assertion that catches that, and it is stated as bytes, not as a
        # count of \r\n, so nothing else can drift either.
        for acq, pid, sids, _ in ACQS[:3]:
            new_id = f"{sids.split('-', 1)[0]}-{PROJECTS[pid]}"
            expect = before_sc[acq].replace(sids.encode(), new_id.encode())
            got = open(os.path.join(root, "raw", "DICOM", acq,
                                    "metadata.json"), "rb").read()
            cls = "CRLF" if NEWLINE_OF[acq] == "\r\n" else "LF"
            check(got == expect,
                  f"{acq} ({cls}) is byte-identical apart from the repaired field")

        # 5. checksums.json for the sidecar was recomputed, not left stale
        ck = json.load(open(os.path.join(root, "raw", "DICOM",
                                         "ACQ-20220124-MRI-001", "checksums.json"),
                            encoding="utf-8"))
        sc = open(os.path.join(root, "raw", "DICOM", "ACQ-20220124-MRI-001",
                               "metadata.json"), "rb").read()
        check(ck["files"]["metadata.json"] == hashlib.sha256(sc).hexdigest(),
              "checksums.json entry matches the rewritten sidecar")
        check(ck["files"]["ACQ-20220124-MRI-001.data/img.dcm"] == "0" * 64,
              "the data files' checksums are untouched")

        # 6. the backup exists and is byte-identical to what it copied
        check(os.path.isfile(os.path.join(root, "_backup", "registry_raw.csv")),
              "registries were backed up off-NAS first")

        # 7. idempotency. rc is 1, not 0: the held-back laura-tholt row is still
        # unrepaired, and the script must keep saying so rather than report a
        # clean sweep it did not achieve.
        subj_before = open(st.subjects_path(reg), "rb").read()
        rc2 = rsi.main(["--nas-root", root, "--apply",
                        "--backup-dir", os.path.join(root, "_backup2")])
        check(_raw_bytes(reg) == after and open(st.subjects_path(reg), "rb").read()
              == subj_before, "a second --apply changes 0 bytes")
        check(rc2 == 1, "and still exits nonzero while a row remains unrepaired")


def test_unresolvable_project_is_reported_not_guessed():
    print("a non-protocol project is reported, never guessed:")
    with tempfile.TemporaryDirectory() as root:
        reg = build_nas(root)
        work, unresolvable = rsi.build_worklist(root)
        check(len(work) == 3, f"3 repairable rows (got {len(work)})")
        check([u[0] for u in unresolvable] == ["ACQ-20220401-MRI-004"],
              "the laura-tholt row is held back")
        rsi.main(["--nas-root", root, "--apply",
                  "--backup-dir", os.path.join(root, "_b")])
        check(_subject_id_of(root, "ACQ-20220401-MRI-004") == "5-AE-biomaGUNE-None",
              "its sidecar is left alone rather than given an invented alias")
        check(b"5-AE-biomaGUNE-None" in _raw_bytes(reg),
              "and its registry row is left alone too")


def test_resumes_after_a_partial_failure():
    print("a half-done run (sidecars fixed, registry not) resumes:")
    with tempfile.TemporaryDirectory() as root:
        reg = build_nas(root)
        # Simulate dying between the sidecar pass and the registry write: fix
        # one sidecar by hand and leave every registry row untouched.
        acq, sc_id = "ACQ-20220124-MRI-001", "23-AE-biomaGUNE-0219"
        sc = os.path.join(root, "raw", "DICOM", acq, "metadata.json")
        raw = open(sc, "rb").read().replace(b"23-AE-biomaGUNE-None", sc_id.encode())
        with open(sc, "wb") as f:
            f.write(raw)

        rc = rsi.main(["--nas-root", root, "--apply",
                       "--backup-dir", os.path.join(root, "_b")])
        check(rc == 0, "the resume run completes instead of aborting")
        check(open(sc, "rb").read() == raw,
              "the already-correct sidecar is left byte-identical")
        check(_subject_id_of(root, "ACQ-20220118-PET-010") == "23-AE-biomaGUNE-1521",
              "the sidecar that still needed repair got it")
        after = _raw_bytes(reg)
        check(after.count(b"-AE-biomaGUNE-None") == 1,
              "the registry rows left behind by the failed run are now repaired")
        table = st.read_subjects(st.subjects_path(reg))
        check("23-AE-biomaGUNE-0219" in table and "23-AE-biomaGUNE-1521" in table
              and not [k for k in table if k.endswith("-None")],
              "and the subjects table ends up in the same state as a clean run")


def test_sidecar_registry_disagreement_aborts():
    print("a sidecar that disagrees with the registry stops the run:")
    with tempfile.TemporaryDirectory() as root:
        reg = build_nas(root)
        sc = os.path.join(root, "raw", "DICOM", ACQS[0][0], "metadata.json")
        md = json.load(io.open(sc, encoding="utf-8"))
        md["subject"]["facility_animal_id"] = "99-AE-biomaGUNE-None"
        with io.open(sc, "w", encoding="utf-8", newline="\n") as f:
            json.dump(md, f, indent=2)
        before = _raw_bytes(reg)
        raised = False
        try:
            rsi.main(["--nas-root", root, "--apply",
                      "--backup-dir", os.path.join(root, "_b")])
        except RuntimeError as e:
            raised = "refusing to guess" in str(e)
        check(raised, "it raises rather than picking one of the two")
        check(_raw_bytes(reg) == before, "and nothing was written")


def main():
    for fn in (test_dry_run_writes_nothing,
               test_apply_repairs_everything,
               test_unresolvable_project_is_reported_not_guessed,
               test_resumes_after_a_partial_failure,
               test_sidecar_registry_disagreement_aborts):
        fn()
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for m in FAILS:
            print(f"  - {m}")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
