#!/usr/bin/env python3
"""test_project_dates.py -- a project's dates are its acquisition dates, and stay so (issue #10).

`registry_projects.start_date` / `last_activity` mean the project's first / newest ACQUISITION
date (06_REGISTRIES §4, 2026-07-14). Covered, against throwaway folders (never the NAS):

  projects_registry (unit)
    * acquisition_date: ISO dates kept, blank / NA / impossible dates -> ""
    * widened: only outward; blank current values replaced; unusable dates widen nothing
    * acquisition_date_ranges: min/max per project, multi-project cells, undated rows counted

  ingest_raw (end to end on a scratch NAS)
    * an existing project dated 2026-05 receives a 2024 acquisition: start_date moves back,
      last_activity unchanged; a later one moves last_activity forward; an acquisition with no
      date (NA, the today() placeholder) changes nothing
    * the widening write happens under the registry lock
    * a failure in the widening WARNs and the ingest still succeeds
    * an auto-created project is dated by the acquisition, not today, and its _project.yaml is UTF-8

  manager.raw_import
    * an acquisition that GAINS the project widens it; a shared one (registered elsewhere) does not

  recompute_project_dates.py
    * the recompute matches reopen_project's former inline logic on a fixture
    * dry run writes nothing; --apply refuses an existing backup dir and a missing one;
      --apply writes only the date columns, with a byte-verified backup; --project-id scopes

  fix_project_yaml_encoding.py
    * a cp1252 file is detected and converted (backup byte-identical to the original);
      a UTF-8 file is left alone; dry run writes nothing; --apply refuses an existing backup dir

  _project.yaml writers
    * create_project writes UTF-8 with LF; project_layout.update_project_yaml edits a legacy
      cp1252 file instead of crashing (and writes it back as UTF-8)

Run:  python tools/test_project_dates.py
"""
import contextlib
import csv
import io
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ingest import locking, project_layout, projects_registry, provenance, registry  # noqa: E402

FAILED = []


def check(cond, msg):
    print(f"  {'ok' if cond else 'FAIL'}:   {msg}")
    if not cond:
        FAILED.append(msg)


def write(path, data=b"x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return path


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def run_quiet(fn, *a, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out = fn(*a, **kw)
    return out, buf.getvalue()


def build_nas(root, projects=(("PROJ-0001", "alpha", "2026-05-01", "2026-05-20"),)):
    reg = os.path.join(root, "registries")
    os.makedirs(reg)
    os.makedirs(os.path.join(root, "raw"), exist_ok=True)
    with open(os.path.join(reg, "registry_raw.csv"), "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(registry.REGISTRY_FIELDS)
    with open(os.path.join(reg, "registry_projects.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(projects_registry.PROJECT_REGISTRY_FIELDS)
        for pid, name, start, last in projects:
            w.writerow([pid, name, "", "RT", start, "active", last, f"/projects/{name}/", ""])
    for _pid, name, _s, _l in projects:
        d = os.path.join(root, "projects", name)
        os.makedirs(os.path.join(d, "raw_linked"))
        provenance.write_empty(os.path.join(d, "provenance.csv"))


def project_row(nas, pid):
    rows = projects_registry.read_projects(projects_registry.projects_registry_path(nas))
    return projects_registry.find_project(rows, pid) or {}


def dates(nas, pid):
    r = project_row(nas, pid)
    return r.get("start_date"), r.get("last_activity")


def batch_cfg(staging, acq_dt, link, project="alpha", auto_create=False, acp=None):
    cfg = {
        "ingest": {"delete_source_after_ingest": False, "auto_create_projects": auto_create},
        "auto_discover": {"staging_dir": staging, "pattern": "*.tif"},
        "registry": {
            "instrument": "ZWSI", "data_ecosystem": "MICROSCOPY", "instrument_model": "NA",
            "modalities_in_study": "NA", "researcher": "RT", "data_source": "internal",
            "sample_id": "S1", "sample_type": "NA", "acquisition_datetime": acq_dt,
            "project_name": project, "notes": "NA",
        },
        "operator": "RT",
        "link_filename": link,
    }
    if acp:
        cfg["auto_create_project"] = acp
    return cfg


# ======================================================================== unit

def test_unit():
    print("projects_registry: acquisition_date / widened / ranges")
    ad = projects_registry.acquisition_date
    check(ad("2024-03-03T10:11:12") == "2024-03-03", "ISO datetime -> date")
    check(ad("2024-03-03") == "2024-03-03", "ISO date kept")
    check(all(ad(v) == "" for v in ("", None, "NA", "2024", "2024-13-01", "2024-02-30", "1900-01-01")),
          "blank / NA / bare year / impossible / placeholder dates -> ''")

    w = projects_registry.widened
    check(w("2026-05-01", "2026-05-20", ["2024-01-01"]) == ("2024-01-01", "2026-05-20"),
          "an earlier date moves start_date only")
    check(w("2026-05-01", "2026-05-20", ["2026-08-01"]) == ("2026-05-01", "2026-08-01"),
          "a later date moves last_activity only")
    check(w("2026-05-01", "2026-05-20", ["2026-05-10"]) == ("2026-05-01", "2026-05-20"),
          "a date inside the range moves nothing (never inward)")
    check(w("2026-05-01", "2026-05-20", ["", "NA"]) == ("2026-05-01", "2026-05-20"),
          "blank / NA dates widen nothing")
    check(w("", "garbage", ["2025-02-02"]) == ("2025-02-02", "2025-02-02"),
          "blank or unusable current values are replaced")

    rows = [
        {"project_id": "PROJ-0001", "acquisition_datetime": "2024-01-05T09:00"},
        {"project_id": "PROJ-0001;PROJ-0002", "acquisition_datetime": "2025-06-01"},
        {"project_id": "PROJ-0001", "acquisition_datetime": ""},
        {"project_id": "PROJ-0002", "acquisition_datetime": "2023-03-03"},
        {"project_id": "PROJ-0003", "acquisition_datetime": "NA"},
    ]
    r = projects_registry.acquisition_date_ranges(rows)
    check(r["PROJ-0001"] == ("2024-01-05", "2025-06-01", 3, 1), f"PROJ-0001 range (got {r['PROJ-0001']})")
    check(r["PROJ-0002"] == ("2023-03-03", "2025-06-01", 2, 0), "a multi-project cell counts for each")
    check(r["PROJ-0003"] == ("", "", 1, 1), "a project with only undated rows has no range")
    check(projects_registry.recompute_dates(rows, "PROJ-9999") == ("", "", 0, 0), "unknown project")


# ====================================================================== ingest

def test_ingest_widening():
    import ingest_raw

    print("ingest_raw: Step 11b widens an existing project's dates")
    with tempfile.TemporaryDirectory() as nas:
        build_nas(nas)
        reg_dir = os.path.join(nas, "registries")

        # record whether the lock is held whenever widen_dates writes
        real_widen = projects_registry.widen_dates
        seen_lock = []

        def spy(path, pid, ds):
            seen_lock.append(os.path.exists(os.path.join(reg_dir, locking.LOCK_FILENAME)))
            return real_widen(path, pid, ds)
        projects_registry.widen_dates = spy
        try:
            st = os.path.join(nas, "_st1")
            write(os.path.join(st, "a.tif"), b"A2024")
            res, out = run_quiet(ingest_raw.run_batch, batch_cfg(st, "2024-03-03", "a.tif"), nas)
            check([ok for _a, ok in res] == [True], "2024 case ingested")
            check(dates(nas, "PROJ-0001") == ("2024-03-03", "2026-05-20"),
                  f"start_date moved back to 2024-03-03, last_activity unchanged (got {dates(nas, 'PROJ-0001')})")
            check("dates widened" in out, "the log says the dates were widened")
            check(seen_lock == [True], f"widen_dates ran under the registry lock (got {seen_lock})")

            st = os.path.join(nas, "_st2")
            write(os.path.join(st, "b.tif"), b"B2026")
            run_quiet(ingest_raw.run_batch, batch_cfg(st, "2026-08-01T10:00:00", "b.tif"), nas)
            check(dates(nas, "PROJ-0001") == ("2024-03-03", "2026-08-01"),
                  f"a later acquisition moves last_activity forward (got {dates(nas, 'PROJ-0001')})")

            st = os.path.join(nas, "_st3")
            write(os.path.join(st, "c.tif"), b"C2025")
            before = read_bytes(projects_registry.projects_registry_path(nas))
            n_calls = len(seen_lock)
            run_quiet(ingest_raw.run_batch, batch_cfg(st, "2025-01-01", "c.tif"), nas)
            check(read_bytes(projects_registry.projects_registry_path(nas)) == before,
                  "a date inside the range leaves registry_projects.csv byte-identical")
            check(len(seen_lock) == n_calls, "...and does not even take the lock (unlocked pre-check)")

            st = os.path.join(nas, "_st4")
            write(os.path.join(st, "d.tif"), b"D-NA")
            res, out = run_quiet(ingest_raw.run_batch, batch_cfg(st, "NA", "d.tif"), nas)
            check(read_bytes(projects_registry.projects_registry_path(nas)) == before,
                  "an acquisition with no date (today() placeholder) changes nothing")
        finally:
            projects_registry.widen_dates = real_widen

        print("ingest_raw: a failure in the widening is non-fatal")
        projects_registry.widen_dates = lambda *a, **k: (_ for _ in ()).throw(OSError("simulated"))
        try:
            st = os.path.join(nas, "_st5")
            write(os.path.join(st, "e.tif"), b"E2020")
            res, out = run_quiet(ingest_raw.run_batch, batch_cfg(st, "2020-02-02", "e.tif"), nas)
        finally:
            projects_registry.widen_dates = real_widen
        check([ok for _a, ok in res] == [True], "the ingest still succeeds")
        check("Could not widen" in out and "simulated" in out, "the failure is logged as a WARN")
        check(os.path.exists(os.path.join(nas, "projects", "alpha", "raw_linked", "e.tif")),
              "the link step after it still ran")
        check(not os.path.exists(os.path.join(reg_dir, locking.LOCK_FILENAME)), "the lock was released")


def test_ingest_autocreate():
    import ingest_raw

    print("ingest_raw: an auto-created project is dated by the acquisition")
    with tempfile.TemporaryDirectory() as nas:
        build_nas(nas)
        st = os.path.join(nas, "_st")
        write(os.path.join(st, "z.tif"), b"Z2019")
        cfg = batch_cfg(st, "2019-06-07", "z.tif", project="gamma", auto_create=True,
                        acp={"owner": "RT", "description": "Análisis — prueba"})
        res, out = run_quiet(ingest_raw.run_batch, cfg, nas)
        check([ok for _a, ok in res] == [True], "case ingested, project auto-created")
        row = projects_registry.find_project(
            projects_registry.read_projects(projects_registry.projects_registry_path(nas)), "gamma") or {}
        check((row.get("start_date"), row.get("last_activity")) == ("2019-06-07", "2019-06-07"),
              f"start_date = last_activity = the acquisition's date, not today (got "
              f"{row.get('start_date')}, {row.get('last_activity')})")
        y = read_bytes(os.path.join(nas, "projects", "gamma", "_project.yaml"))
        try:
            text = y.decode("utf-8")
            utf8 = True
        except UnicodeDecodeError:
            text, utf8 = "", False
        check(utf8 and "Análisis — prueba" in text, "_project.yaml is UTF-8 and holds the accented description")
        check(b"\r\n" not in y, "_project.yaml has LF line endings")
        check("start_date: 2019-06-07" in text and "last_activity: 2019-06-07" in text,
              "_project.yaml carries the acquisition date too")


# ================================================================== raw import

def test_raw_import():
    from manager import raw_import

    print("manager.raw_import: only acquisitions that gain the project widen it")
    with tempfile.TemporaryDirectory() as nas:
        build_nas(nas, projects=(("PROJ-0001", "alpha", "2026-05-01", "2026-05-20"),
                                 ("PROJ-0002", "beta", "2026-01-01", "2026-01-01")))
        rows = []
        for acq, day, pid in (("ACQ-20230405-ZWSI-001", "2023-04-05T08:00", ""),
                              ("ACQ-20270101-ZWSI-001", "2026-12-31", "PROJ-0002")):
            canonical = f"/raw/MICROSCOPY/{day[:4]}/{day[:7]}/{acq}/"
            write(os.path.join(nas, canonical.strip("/"), "s.czi"), acq.encode())
            rows.append({"acq_id": acq, "acquisition_datetime": day, "instrument": "ZWSI",
                         "data_ecosystem": "MICROSCOPY", "primary_kind": "file",
                         "primary_file_name": "s.czi", "original_name": f"{acq}.czi",
                         "canonical_path": canonical, "project_id": pid})
        with open(os.path.join(nas, "registries", "registry_raw.csv"), "w", encoding="utf-8",
                  newline="") as f:
            w = csv.DictWriter(f, fieldnames=registry.REGISTRY_FIELDS)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in registry.REGISTRY_FIELDS})
        logs = []
        res = raw_import.import_acquisitions(nas, project_row(nas, "PROJ-0001"), rows, "RT",
                                             log=lambda m, level="INFO": logs.append(m))
        check(res["linked"] == 2 and res["registered"] == 1 and res["shared"] == 1,
              f"two linked, one registered, one shared (got {res['linked']}/{res['registered']}/{res['shared']})")
        check(dates(nas, "PROJ-0001") == ("2023-04-05", "2026-05-20"),
              f"the registered 2023 acquisition moved start_date; the shared 2026-12-31 one did not move "
              f"last_activity (got {dates(nas, 'PROJ-0001')})")
        check(dates(nas, "PROJ-0002") == ("2026-01-01", "2026-01-01"), "the other project is untouched")
        check(any("dates widened" in m for m in logs), "the log says so")


# =================================================================== recompute

def _old_reopen_logic(acqs, proj):
    """reopen_project.py's inline computation before 2026-10 (kept here as the reference)."""
    ds = sorted(r["acquisition_datetime"][:10] for r in acqs if len(r["acquisition_datetime"]) >= 10)
    return (ds[0], ds[-1]) if ds else (proj["start_date"], proj["last_activity"])


def _seed_raw(nas, rows):
    with open(os.path.join(nas, "registries", "registry_raw.csv"), "w", encoding="utf-8",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=registry.REGISTRY_FIELDS)
        w.writeheader()
        for i, (pid, day) in enumerate(rows):
            w.writerow({**{k: "" for k in registry.REGISTRY_FIELDS},
                        "acq_id": f"ACQ-X-{i:03d}", "project_id": pid, "acquisition_datetime": day})


def test_recompute():
    import recompute_project_dates as rpd
    from ingest import project_ids as pids

    print("recompute_project_dates: the shared recompute, dry run, --apply")
    with tempfile.TemporaryDirectory() as nas:
        build_nas(nas, projects=(("PROJ-0001", "alpha", "2026-08-12", "2026-08-12"),   # creation date
                                 ("PROJ-0002", "beta", "2024-01-01", "2024-02-01"),    # already right
                                 ("PROJ-0003", "gamma", "2026-03-03", "2026-03-03")))  # no dated acqs
        _seed_raw(nas, [("PROJ-0001", "2018-02-03T10:00:00"), ("PROJ-0001", "2025-11-30"),
                        ("PROJ-0001", ""), ("PROJ-0001;PROJ-0002", "2024-02-01"),
                        ("PROJ-0002", "2024-01-01T00:00"), ("PROJ-0003", "")])
        raw = registry.read_registry(os.path.join(nas, "registries", "registry_raw.csv"))
        for pid in ("PROJ-0001", "PROJ-0002", "PROJ-0003"):
            acqs = [r for r in raw if pids.has_project_id(r.get("project_id"), pid)]
            s, l, _n, _u = projects_registry.recompute_dates(acqs, pid)
            if not s:
                s, l = project_row(nas, pid)["start_date"], project_row(nas, pid)["last_activity"]
            check((s, l) == _old_reopen_logic(acqs, project_row(nas, pid)),
                  f"{pid}: shared recompute == reopen_project's former logic ({s}..{l})")

        proj_csv = projects_registry.projects_registry_path(nas)
        before = read_bytes(proj_csv)
        rc, out = run_quiet(rpd.main, ["--nas-root", nas])
        check(rc == 0 and read_bytes(proj_csv) == before, "dry run exits 0 and writes nothing")
        check("PROJ-0001" in out and "2018-02-03" in out and "YES" in out, "dry run shows the change")
        check("none dated -- kept" in out, "a project with no dated acquisition is reported as kept")

        exists = os.path.join(nas, "_bk_exists")
        os.makedirs(exists)
        rc, out = run_quiet(rpd.main, ["--nas-root", nas, "--apply", "--backup-dir", exists])
        check(rc != 0 and read_bytes(proj_csv) == before, "--apply refuses an existing backup dir")
        rc, out = run_quiet(rpd.main, ["--nas-root", nas, "--apply"])
        check(rc != 0 and read_bytes(proj_csv) == before, "--apply refuses without --backup-dir")

        bk = os.path.join(nas, "_bk_scoped")
        rc, out = run_quiet(rpd.main, ["--nas-root", nas, "--apply", "--backup-dir", bk,
                                       "--project-id", "beta"])
        check(rc == 0 and read_bytes(proj_csv) == before, "--project-id beta: nothing to change there")
        check(read_bytes(os.path.join(bk, "registry_projects.csv")) == before, "the backup is byte-identical")

        bk = os.path.join(nas, "_bk")
        rc, out = run_quiet(rpd.main, ["--nas-root", nas, "--apply", "--backup-dir", bk])
        check(rc == 0, "--apply exits 0")
        check(read_bytes(os.path.join(bk, "registry_projects.csv")) == before,
              "the backup is the pre-write file, byte for byte")
        check(dates(nas, "PROJ-0001") == ("2018-02-03", "2025-11-30"),
              f"PROJ-0001 recomputed (moved inward from its creation date) (got {dates(nas, 'PROJ-0001')})")
        check(dates(nas, "PROJ-0002") == ("2024-01-01", "2024-02-01"), "PROJ-0002 unchanged")
        check(dates(nas, "PROJ-0003") == ("2026-03-03", "2026-03-03"), "PROJ-0003 kept (no dated acqs)")
        old = {r["project_id"]: r for r in csv.DictReader(io.StringIO(before.decode("utf-8")))}
        new = {r["project_id"]: r for r in projects_registry.read_projects(proj_csv)}
        check(all({k: v for k, v in new[p].items() if k not in projects_registry.DATE_FIELDS}
                  == {k: v for k, v in old[p].items() if k not in projects_registry.DATE_FIELDS}
                  for p in old), "no column other than the two dates changed")
        check(not os.path.exists(os.path.join(nas, "registries", locking.LOCK_FILENAME)), "lock released")


# ==================================================================== encoding

YAML_TEXT = ("project_id: PROJ-0001\nname: alpha\ndescription: \"Estudio de pulmón — fase 2\"\n"
             "status: active\nowner: RT\nnotes: |\n  Created by create_project.py\n")


def test_encoding_tool():
    import fix_project_yaml_encoding as fx

    print("fix_project_yaml_encoding: detect, dry run, convert")
    with tempfile.TemporaryDirectory() as nas:
        bad = write(os.path.join(nas, "projects", "alpha", "_project.yaml"),
                    YAML_TEXT.replace("\n", "\r\n").encode("cp1252"))
        good = write(os.path.join(nas, "projects", "beta", "_project.yaml"),
                     YAML_TEXT.replace("alpha", "beta").encode("utf-8"))
        bad0, good0 = read_bytes(bad), read_bytes(good)

        rc, out = run_quiet(fx.main, ["--nas-root", nas])
        check(rc == 0 and read_bytes(bad) == bad0 and read_bytes(good) == good0, "dry run writes nothing")
        check(f"cp1252: {bad}" in out and good not in out, "the cp1252 file is listed, the UTF-8 one is not")
        check("pulmón — fase 2" in out, "dry run shows the line as it will read")

        exists = os.path.join(nas, "_bk_exists")
        os.makedirs(exists)
        rc, _ = run_quiet(fx.main, ["--nas-root", nas, "--apply", "--backup-dir", exists])
        check(rc != 0 and read_bytes(bad) == bad0, "--apply refuses an existing backup dir")

        bk = os.path.join(nas, "_bk")
        rc, out = run_quiet(fx.main, ["--nas-root", nas, "--apply", "--backup-dir", bk])
        check(rc == 0, "--apply exits 0")
        check(read_bytes(bad) == YAML_TEXT.replace("\n", "\r\n").encode("utf-8"),
              "converted to UTF-8; the text and its CRLF line endings are unchanged")
        check(read_bytes(good) == good0, "the UTF-8 file is untouched")
        check(read_bytes(os.path.join(bk, "alpha", "_project.yaml")) == bad0,
              "the backup is the original cp1252 file, byte for byte")
        with open(os.path.join(bk, "manifest.csv"), encoding="utf-8", newline="") as f:
            man = list(csv.DictReader(f))
        check(len(man) == 1 and man[0]["result"] == "converted", "manifest.csv records the conversion")

        rc, out = run_quiet(fx.main, ["--nas-root", nas])
        check("0 cp1252" in out, "a second scan finds nothing to convert")


def test_writers():
    import create_project

    print("_project.yaml writers: UTF-8 everywhere")
    with tempfile.TemporaryDirectory() as nas:
        os.makedirs(os.path.join(nas, "registries"))
        (pid, ok), _ = run_quiet(create_project.create_project, "delta", "Análisis — piloto", "RT", nas)
        y = read_bytes(os.path.join(nas, "projects", "delta", "_project.yaml"))
        check(ok and "Análisis — piloto".encode("utf-8") in y and b"\r\n" not in y,
              "create_project writes UTF-8 with LF")
        (pid2, ok2), _ = run_quiet(create_project.create_project, "epsilon", "x", "RT", nas,
                                   start_date="2021-04-05T12:00:00")
        check(ok2 and dates(nas, pid2) == ("2021-04-05", "2021-04-05"),
              "create_project(start_date=...) dates the registry row by it")

        legacy = os.path.join(nas, "projects", "delta")
        write(os.path.join(legacy, "_project.yaml"), YAML_TEXT.encode("cp1252"))
        try:
            changed = project_layout.update_project_yaml(legacy, {"owner": "MBC"})
            raised = None
        except Exception as e:  # noqa: BLE001
            changed, raised = [], e
        check(raised is None and changed == ["owner"], f"a cp1252 file is edited, not refused ({raised})")
        text = read_bytes(os.path.join(legacy, "_project.yaml")).decode("utf-8")
        check("owner: MBC" in text and "pulmón — fase 2" in text, "...and written back as UTF-8")


def main():
    test_unit()
    test_ingest_widening()
    test_ingest_autocreate()
    test_raw_import()
    test_recompute()
    test_encoding_tool()
    test_writers()
    print()
    if FAILED:
        print(f"FAILED ({len(FAILED)}):")
        for m in FAILED:
            print(f"  - {m}")
        return 1
    print("ALL PASS (project dates + _project.yaml encoding)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
