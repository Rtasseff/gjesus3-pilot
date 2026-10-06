#!/usr/bin/env python3
"""a2_claims.py -- every project claim on drive 3, classified CONFIRMED / A / B / C against the animal DB.

Runs the SAME engine that classified drives 1+2 (tools/drive_staging/project_claims.py, Ryan's rule
of 2026-09-29, tasks/drives_project_codes_findings.md) over the drive-3 manifest. Nothing in the engine
is changed: this wrapper only points its inputs at drive 3 (in memory):

  * load_manifest  -> D:\\projects\\gjesus3\\drive3_analysis\\drive3_manifest.csv (byte-identical to the
                      NAS copy); drives 1 and 2 are given empty manifests;
  * STAGING/DRIVES -> J:\\_staging_drive3_MJ\\drive3_MJesus_WX22D623YP29 (the two .zip archives are
                      LISTED there, read-only, never extracted);
  * --out          -> D:\\projects\\gjesus3\\drive3_analysis\\a2\\claims\\.

READ-ONLY: J:\\ is only read; the animal-facility DB only gets SELECTs (tools/animal_db.py, the
credentials stay in ~/.my.cnf). Outputs (claims.csv, file_claims.csv, archive_member_claims.csv,
noclaim_groups.csv, rejected_tokens.csv, safety_net.csv, run_summary.txt, db_cache.json,
archive_members.json) are the engine's own, documented in its docstring.

    set PYTHONDONTWRITEBYTECODE=1
    python tools/drive_staging/drive3/a2_claims.py [--fresh-db]
"""
import csv
import io
import os
import sys

import a2_common as C

import project_claims as PC  # noqa: E402  (the drives-1+2 engine, unchanged)

DRIVE3_DIR = os.path.basename(C.STAGED_ROOT)


def load_manifest(drive):
    if drive != "drive3":
        return {}
    rows = {}
    with io.open(C.MANIFEST, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            rows[r["relpath"]] = r
    return rows


def main():
    C.stdout_utf8()
    PC.STAGING = os.path.dirname(C.STAGED_ROOT)
    PC.DRIVES = {"drive1": "(none)", "drive2": "(none)", "drive3": DRIVE3_DIR}
    PC.load_manifest = load_manifest
    out = os.path.join(C.OUT, "claims")
    os.makedirs(out, exist_ok=True)
    argv = [sys.argv[0], "--out", out] + [a for a in sys.argv[1:] if a == "--fresh-db"]
    sys.argv = argv
    PC.main()


if __name__ == "__main__":
    main()
