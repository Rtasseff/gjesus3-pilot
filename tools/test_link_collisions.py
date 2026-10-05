#!/usr/bin/env python3
"""test_link_collisions.py -- a project link name is never merged into (2026-10-05).

Stream F (2026-10-04) found that `linker.create_hardlink` silently MERGED two
acquisitions that resolved to one link name: a folder primary was linked file by
file into the first acquisition's folder (`makedirs(exist_ok)` + "link only the
files that do not exist yet"), and a file primary was silently skipped. 209
production acquisitions ended up with no link of their own.

Covered, against throwaway folders (never the NAS):

  linker (unit)
    * two acquisitions, one name -- FOLDER primaries (overlapping and disjoint
      file names) and FILE primaries: the second is refused, the first untouched
    * an idempotent re-run of the same acquisition is a no-op (folder + file)
    * a folder holding only some of the acquisition's own files (an interrupted
      run) or nothing at all (an empty shell) is completed
    * a partial-MERGE state (two acquisitions' files in one folder): every
      acquisition is refused and nothing changes
    * a folder where a file belongs, a file where a folder belongs, a different
      file under the name, an extra file in an otherwise own folder: refused
    * the pre-copy check (no raw primary yet): anything at the name is taken,
      including an empty folder and a queued `.PENDING-LINK.txt` stand-in
    * LinkCollisionError is NOT an OSError (so no caller queues it for a relink)
    * dry_run=True runs the same check and creates nothing

  ingest_raw (end to end on a scratch NAS, file primaries)
    * two cases, one link name: case 1 linked; case 2 FAILS at the pre-flight,
      before its copy -- no raw folder, no registry row, the link untouched
    * --dry-run reports a name taken on disk AND two cases of one batch that
      would take the same name, and writes nothing
    * a name taken after the pre-flight (simulated) is refused at the link step:
      the acquisition stays registered, nothing is queued to pending_links.csv

Run:  python tools/test_link_collisions.py
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

from ingest import linker, provenance, registry  # noqa: E402

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


def folder_primary(root, acq, names):
    d = os.path.join(root, "raw", acq, acq + ".data")
    for n in names:
        write(os.path.join(d, n), (acq + n).encode())
    return d


def file_primary(root, acq):
    return write(os.path.join(root, "raw", acq, acq + ".czi"), acq.encode())


def snapshot(path):
    """{relative name: (st_dev, st_ino)} of a link file or folder -- what 'untouched' compares."""
    if os.path.isfile(path):
        st = os.stat(path)
        return {"": (st.st_dev, st.st_ino)}
    out = {}
    for r, _d, fs in os.walk(path):
        for fn in fs:
            p = os.path.join(r, fn)
            st = os.stat(p)
            out[os.path.relpath(p, path)] = (st.st_dev, st.st_ino)
    return out


def refused(fn):
    try:
        fn()
    except linker.LinkCollisionError:
        return True
    return False


# ============================================================== linker (unit)

def test_linker():
    print("linker: two acquisitions, one name")
    with tempfile.TemporaryDirectory() as root:
        proj = os.path.join(root, "projects", "p")
        os.makedirs(os.path.join(proj, "raw_linked"))

        # --- folder primaries, overlapping file names (the MRI case: recon1_frame01 ...)
        a = folder_primary(root, "ACQ-A", ["recon1_frame01.dcm", "recon1_frame02.dcm"])
        b = folder_primary(root, "ACQ-B", ["recon1_frame01.dcm", "recon1_frame02.dcm",
                                           "recon1_frame03.dcm"])
        dest = linker.create_hardlink(proj, "MRI_m1_x_20260101_2_1", a)
        check(linker.inspect_link_target(proj, "MRI_m1_x_20260101_2_1", a)[0] == linker.LINK_OWN,
              "folder link created and inspected as OWN")
        before = snapshot(dest)
        check(refused(lambda: linker.create_hardlink(proj, "MRI_m1_x_20260101_2_1", b)),
              "folder primary B on A's name: refused (LinkCollisionError)")
        check(snapshot(dest) == before, "A's link folder untouched (same names, same file ids, no extra)")
        check(not os.path.exists(os.path.join(dest, "recon1_frame03.dcm")),
              "B's non-clashing file was NOT added (the old merge)")

        # --- folder primaries, disjoint names
        c = folder_primary(root, "ACQ-C", ["recon3_frame01.dcm"])
        check(refused(lambda: linker.create_hardlink(proj, "MRI_m1_x_20260101_2_1", c)),
              "folder primary with disjoint file names: refused too")
        check(snapshot(dest) == before, "still untouched")

        # --- file primaries
        fa, fb = file_primary(root, "ACQ-FA"), file_primary(root, "ACQ-FB")
        fdest = linker.create_hardlink(proj, "ZWSI_slide.czi", fa)
        check(os.path.samefile(fdest, fa), "file link created (same file as the raw primary)")
        check(refused(lambda: linker.create_hardlink(proj, "ZWSI_slide.czi", fb)),
              "file primary B on A's name: refused (it used to be skipped silently)")
        check(os.path.samefile(fdest, fa), "the name still points at A")

        print("linker: idempotent re-run")
        check(linker.create_hardlink(proj, "MRI_m1_x_20260101_2_1", a) == dest and snapshot(dest) == before,
              "folder: re-running A is a no-op")
        check(linker.create_hardlink(proj, "ZWSI_slide.czi", fa) == fdest and os.path.samefile(fdest, fa),
              "file: re-running A is a no-op")

        print("linker: incomplete own folders are completed")
        part = os.path.join(proj, "raw_linked", "PARTIAL")
        os.makedirs(part)
        os.link(os.path.join(b, "recon1_frame01.dcm"), os.path.join(part, "recon1_frame01.dcm"))
        st, _d, detail = linker.inspect_link_target(proj, "PARTIAL", b)
        check(st == linker.LINK_PARTIAL, f"1 of B's 3 files and nothing else -> PARTIAL ({detail})")
        linker.create_hardlink(proj, "PARTIAL", b)
        check(linker.inspect_link_target(proj, "PARTIAL", b)[0] == linker.LINK_OWN,
              "completed: all of B's files, nothing else")
        shell = os.path.join(proj, "raw_linked", "SHELL")
        os.makedirs(shell)
        check(linker.inspect_link_target(proj, "SHELL", b)[0] == linker.LINK_PARTIAL,
              "an empty shell is completable for an existing acquisition")
        linker.create_hardlink(proj, "SHELL", b)
        check(linker.inspect_link_target(proj, "SHELL", b)[0] == linker.LINK_OWN, "the shell is filled")

        print("linker: a partial-merge (polluted) folder")
        merged = os.path.join(proj, "raw_linked", "MERGED")
        os.makedirs(merged)
        os.link(os.path.join(a, "recon1_frame01.dcm"), os.path.join(merged, "recon1_frame01.dcm"))
        os.link(os.path.join(a, "recon1_frame02.dcm"), os.path.join(merged, "recon1_frame02.dcm"))
        os.link(os.path.join(b, "recon1_frame03.dcm"), os.path.join(merged, "recon1_frame03.dcm"))
        mbefore = snapshot(merged)
        for who, prim in (("A (its files + 1 of B's)", a), ("B (1 of its files + A's)", b),
                          ("C (none of its files)", c)):
            check(refused(lambda: linker.create_hardlink(proj, "MERGED", prim)),
                  f"merged folder: {who} is refused")
        check(snapshot(merged) == mbefore, "the merged folder is left exactly as it was")
        check(linker.inspect_link_target(proj, "MERGED", a)[0] == linker.LINK_TAKEN,
              "inspect reports it TAKEN for A as well")

        print("linker: wrong kind / foreign content")
        os.makedirs(os.path.join(proj, "raw_linked", "DIR_AT_FILE_NAME"))
        check(refused(lambda: linker.create_hardlink(proj, "DIR_AT_FILE_NAME", fa)),
              "a folder where a file's link belongs: refused")
        write(os.path.join(proj, "raw_linked", "FILE_AT_FOLDER_NAME"))
        check(refused(lambda: linker.create_hardlink(proj, "FILE_AT_FOLDER_NAME", a)),
              "a file where a folder's link belongs: refused")
        write(os.path.join(proj, "raw_linked", "OTHER.czi"), b"researcher's own file")
        check(refused(lambda: linker.create_hardlink(proj, "OTHER.czi", fa)),
              "a different file under the name: refused")
        extra = linker.create_hardlink(proj, "WITH_EXTRA", a)
        write(os.path.join(extra, "notes.txt"), b"added by a researcher")
        check(linker.inspect_link_target(proj, "WITH_EXTRA", a)[0] == linker.LINK_TAKEN,
              "A's own folder with an extra foreign file is TAKEN (nothing foreign is allowed)")
        check(refused(lambda: linker.create_hardlink(proj, "WITH_EXTRA", a)),
              "... and a re-run refuses rather than touching it")

        print("linker: the pre-copy check (a new acquisition, raw primary not written yet)")
        st = lambda n: linker.inspect_link_target(proj, n, None)[0]  # noqa: E731
        check(st("NOTHING_HERE") == linker.LINK_FREE, "absent name -> FREE")
        check(st("ZWSI_slide.czi") == linker.LINK_TAKEN, "a file -> TAKEN")
        os.makedirs(os.path.join(proj, "raw_linked", "EMPTY"))
        check(st("EMPTY") == linker.LINK_TAKEN, "an EMPTY folder -> TAKEN (it may be a queued link's shell)")
        write(os.path.join(proj, "raw_linked", "QUEUED" + linker.PENDING_STANDIN_SUFFIX))
        check(st("QUEUED") == linker.LINK_TAKEN, "a .PENDING-LINK.txt stand-in claims the name -> TAKEN")
        check(linker.inspect_link_target(proj, "NOTHING_HERE", os.path.join(root, "nope"))[0]
              == linker.LINK_FREE, "a raw primary that does not exist yet is the pre-copy mode")
        if sys.platform == "win32":
            check(st("zwsi_SLIDE.CZI") == linker.LINK_TAKEN, "case-insensitive on Windows/SMB")
            check(refused(lambda: linker.create_hardlink(proj, "mri_M1_X_20260101_2_1", b)),
                  "a case-variant of A's folder name is refused for B")

        print("linker: the error type and dry_run")
        check(not issubclass(linker.LinkCollisionError, OSError),
              "LinkCollisionError is not an OSError (never queued to pending_links.csv)")
        try:
            linker.create_hardlink(proj, "ZWSI_slide.czi", fb)
        except linker.LinkCollisionError as e:
            check(e.dest.endswith("ZWSI_slide.czi") and e.reason, "the error names the destination and why")
        check(refused(lambda: linker.create_hardlink(proj, "ZWSI_slide.czi", fb, dry_run=True)),
              "dry_run on a taken name: refused")
        d = linker.create_hardlink(proj, "DRY_FREE", fb, dry_run=True)
        check(d.endswith("DRY_FREE") and not os.path.lexists(d), "dry_run on a free name: nothing created")


# ============================================================ ingest_raw (e2e)

PROJECT_COLS = ["project_id", "name", "description", "owner", "start_date",
                "status", "last_activity", "folder_location", "notes"]


def build_nas(root):
    reg = os.path.join(root, "registries")
    os.makedirs(reg)
    os.makedirs(os.path.join(root, "raw"))
    with open(os.path.join(reg, "registry_raw.csv"), "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(registry.REGISTRY_FIELDS)
    with open(os.path.join(reg, "registry_projects.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(PROJECT_COLS)
        w.writerow(["PROJ-0001", "alpha", "", "RT", "2026-01-01", "active", "2026-01-01",
                    "/projects/alpha/", ""])
    proj = os.path.join(root, "projects", "alpha")
    os.makedirs(os.path.join(proj, "raw_linked"))
    provenance.write_empty(os.path.join(proj, "provenance.csv"))
    return proj


def batch_cfg(staging, link):
    return {
        "ingest": {"delete_source_after_ingest": False},
        "auto_discover": {"staging_dir": staging, "pattern": "*.tif"},
        "registry": {
            "instrument": "ZWSI", "data_ecosystem": "MICROSCOPY", "instrument_model": "NA",
            "modalities_in_study": "NA", "researcher": "RT", "data_source": "internal",
            "sample_id": "S1", "sample_type": "NA", "acquisition_datetime": "2026-01-02",
            "project_name": "alpha", "notes": "NA",
        },
        "operator": "RT",
        "link_filename": link,
    }


def run_quiet(fn, *a, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out = fn(*a, **kw)
    return out, buf.getvalue()


def registry_rows(nas):
    with open(os.path.join(nas, "registries", "registry_raw.csv"), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def raw_folders(nas):
    out = []
    for r, ds, _fs in os.walk(os.path.join(nas, "raw")):
        out += [d for d in ds if d.startswith("ACQ-")]
    return sorted(out)


def test_ingest():
    import ingest_raw

    print("ingest_raw: two cases, one link name (real run)")
    with tempfile.TemporaryDirectory() as nas:
        proj = build_nas(nas)
        staging = os.path.join(nas, "_staging1")
        write(os.path.join(staging, "a.tif"), b"AAAA")
        write(os.path.join(staging, "b.tif"), b"BBBB")
        cfg = batch_cfg(staging, "SAME.tif")
        results, out = run_quiet(ingest_raw.run_batch, cfg, nas)
        oks = [ok for _a, ok in results]
        check(oks == [True, False], f"case 1 succeeds, case 2 fails (got {oks})")
        rows = registry_rows(nas)
        check(len(rows) == 1, f"one registry row, not two (got {len(rows)})")
        check(len(raw_folders(nas)) == 1, "case 2 was refused BEFORE its copy: one raw folder")
        link = os.path.join(proj, "raw_linked", "SAME.tif")
        acq1 = rows[0]["acq_id"] if rows else ""
        raw1 = os.path.join(nas, rows[0]["canonical_path"].strip("/"), rows[0]["primary_file_name"]) if rows else ""
        check(rows and os.path.samefile(link, raw1), "the link is case 1's file")
        check("already taken" in out and "SAME.tif" in out, "the log says which name is taken")
        check("-> project link alpha/raw_linked/SAME.tif is already taken" in out,
              "the batch summary gives the reason for the failed case")
        check(not os.path.exists(os.path.join(nas, "registries", "pending_links.csv")),
              "nothing queued to pending_links.csv")

        print("ingest_raw: re-run (case 1 deduped, case 2 refused again)")
        results, out = run_quiet(ingest_raw.run_batch, batch_cfg(staging, "SAME.tif"), nas)
        check([ok for _a, ok in results] == [False], "only case 2 is attempted, and refused again")
        check(len(registry_rows(nas)) == 1 and os.path.samefile(link, raw1), "nothing changed")

        print("ingest_raw: --dry-run shows a taken name and an in-batch duplicate")
        staging2 = os.path.join(nas, "_staging2")
        write(os.path.join(staging2, "c.tif"), b"CCCC")
        write(os.path.join(staging2, "d.tif"), b"DDDD")
        results, out = run_quiet(ingest_raw.run_batch, batch_cfg(staging2, "DUP.tif"), nas, dry_run=True)
        check([ok for _a, ok in results] == [True, False],
              "dry run: the 2nd case planning the same name fails")
        check("also planned for" in out, "dry run names the in-batch partner")
        results, out = run_quiet(ingest_raw.run_batch, batch_cfg(staging2, "SAME.tif"), nas, dry_run=True)
        check([ok for _a, ok in results] == [False, False], "dry run: a name taken on disk fails both")
        check(len(registry_rows(nas)) == 1 and len(raw_folders(nas)) == 1
              and not os.path.exists(os.path.join(proj, "raw_linked", "DUP.tif")),
              "the dry runs wrote nothing")

        print("ingest_raw: a name taken after the pre-flight is refused at the link step")
        real = ingest_raw._preflight_project_link
        ingest_raw._preflight_project_link = lambda *a, **k: (True, None)   # 'free' at pre-flight
        try:
            results, out = run_quiet(ingest_raw.run_batch, batch_cfg(staging2, "SAME.tif"), nas)
        finally:
            ingest_raw._preflight_project_link = real
        check([ok for _a, ok in results] == [True, True],
              "both cases commit (the pre-flight was bypassed)")
        rows = registry_rows(nas)
        check(len(rows) == 3, f"3 registry rows (got {len(rows)})")
        check(os.path.samefile(link, raw1), "the existing link still points at case 1's file")
        check("Registered WITHOUT a project link (name taken): 2" in out,
              "the batch summary lists both as registered without a link")
        check(not os.path.exists(os.path.join(nas, "registries", "pending_links.csv")),
              "a collision is NOT queued to pending_links.csv")
        check(not any(n.endswith(".PENDING-LINK.txt") for n in os.listdir(os.path.join(proj, "raw_linked"))),
              "no stand-in written")


def main():
    test_linker()
    test_ingest()
    print()
    if FAILED:
        print(f"{len(FAILED)} CHECK(S) FAILED")
        for m in FAILED:
            print("  -", m)
        sys.exit(1)
    print("ALL LINK-COLLISION CHECKS PASSED")


if __name__ == "__main__":
    main()
