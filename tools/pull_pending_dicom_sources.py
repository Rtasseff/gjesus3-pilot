#!/usr/bin/env python3
"""pull_pending_dicom_sources.py — stage the ParaVision studies behind the
pending DICOM-regeneration worklist onto local scratch.

Reads `registries/pending_dicom_regen.csv`, takes every row with
`status == "pending"` (the regenerable set — `not-applicable` spectroscopy rows
are ignored), resolves each to its ParaVision **study** folder on the platform
host, and mirrors those studies to a local staging dir. Whole study folders, per
the runbook's step 1: an exam cannot be regenerated on its own because
`paravision_regen.prepare_virtual_exam` reads the study-level `subject` file from
`exam_path.parent`.

READ-ONLY ON THE PLATFORM HOST. It reuses `ftp_mirror.mirror`, whose only remote
calls are `stat` / `listdir_attr` / `get` — there is no put/remove/rename/mkdir
anywhere in that path. The MRI acquisition host must never be written to.

RESUMABLE. `ftp_mirror` skips files already present (size+mtime) and downloads via
`.part` + atomic rename, so an interrupted overnight run is restarted by simply
re-running this: completed files are skipped, a half-file is re-fetched. Nothing
is deleted locally.

Staging lives on scratch (D:), not the NAS: it is a disposable working copy whose
primary is the platform host (D:\\README.md rule 1).

  # what would transfer, no writes anywhere (also a connectivity/credential check)
  PYTHONPATH=tools python tools/pull_pending_dicom_sources.py --dry-run

  # the real pull (run it out of hours — this is a lot of files)
  PYTHONPATH=tools python tools/pull_pending_dicom_sources.py --apply

Credentials: ~/.ssh/gjesus3_mri.cred ([mri] host/user/password/port), or the
GJESUS3_FTP_* env vars. See equipment/mri-platform/mri_data_access_strategy.md
and .../mri_no_dicom_regeneration_runbook.md.
"""
import argparse
import collections
import getpass
import os
import sys
import time

import paramiko

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ftp_mirror  # noqa: E402
from ingest import pending_dicom  # noqa: E402

# The two concurrent ParaVision installs on the acquisition host; the worklist's
# paravision_version column picks which root a study lives under.
PV_ROOTS = {
    "7.0.0": "/opt/PV-7.0.0/data/nmr",
    "6.0.1": "/opt/PV6.0.1/data/nmr",
}
DEFAULT_STAGING = r"D:\temp\mri_regen_20260715"


def studies_to_pull(registries_dir):
    """[(pv_version, study, [exam, ...])] for the pending (regenerable) rows."""
    rows = pending_dicom.read_pending_dicom(
        pending_dicom.pending_dicom_path(registries_dir))
    pending = [r for r in rows if (r.get("status") or "") == "pending"]
    by_study = collections.defaultdict(list)
    for r in pending:
        # original_name is the kenia identity: "<study>/<exam>"
        parts = (r.get("original_name") or "").split("/")
        if len(parts) < 2:
            continue
        by_study[(r.get("paravision_version", ""), parts[0])].append(parts[-1])
    return rows, pending, sorted((pv, s, sorted(e)) for (pv, s), e in by_study.items())


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nas-root", default=os.environ.get("GJESUS3_ROOT", "J:/gjesus3-data"))
    ap.add_argument("--staging", default=DEFAULT_STAGING,
                    help=f"local scratch root (default {DEFAULT_STAGING})")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="list what would transfer; writes nothing, transfers nothing")
    mode.add_argument("--apply", action="store_true", help="perform the pull")
    ap.add_argument("--limit", type=int, default=0, help="only the first N studies (debug)")
    args = ap.parse_args(argv)

    registries_dir = os.path.join(os.path.normpath(args.nas_root), "registries")
    all_rows, pending, studies = studies_to_pull(registries_dir)
    if args.limit:
        studies = studies[:args.limit]

    n_exams = sum(len(e) for _, _, e in studies)
    print(f"worklist      : {len(all_rows)} rows, {len(pending)} pending "
          f"({len(all_rows) - len(pending)} not-applicable, ignored)")
    print(f"to stage      : {len(studies)} study folders covering {n_exams} exams")
    for pv, n in collections.Counter(pv for pv, _, _ in studies).most_common():
        print(f"                PV {pv}: {n} studies  (root {PV_ROOTS.get(pv, '??')})")
    print(f"staging root  : {args.staging}")
    unknown = sorted({pv for pv, _, _ in studies if pv not in PV_ROOTS})
    if unknown:
        print(f"  ERROR: unknown paravision_version(s): {unknown} — "
              f"cannot resolve a PV root. Fix the worklist first.")
        return 2

    creds = ftp_mirror.cred_file_defaults()
    host = os.environ.get("GJESUS3_FTP_HOST") or creds.get("host")
    user = os.environ.get("GJESUS3_FTP_USER") or creds.get("user")
    password = os.environ.get("GJESUS3_FTP_PASSWORD") or creds.get("password")
    port = int(os.environ.get("GJESUS3_FTP_PORT") or creds.get("port") or 22)
    if not host or not user:
        print("ERROR: no host/user (~/.ssh/gjesus3_mri.cred or GJESUS3_FTP_*)")
        return 2
    if not password:
        password = getpass.getpass(f"SFTP password for {user}@{host}: ")

    print(f"connecting    : sftp://{user}@{host}:{port}  (READ-ONLY: stat/listdir/get)")
    t0 = time.time()
    transport = paramiko.Transport((host, port))
    tot_x = tot_s = tot_b = 0
    failed = []
    try:
        transport.connect(username=user, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        print("connected.\n")
        for i, (pv, study, exams) in enumerate(studies, 1):
            remote = f"{PV_ROOTS[pv]}/{study}"
            local = os.path.join(args.staging, f"PV{pv}", study)
            print(f"[{i}/{len(studies)}] PV{pv} {study}  (need exams {','.join(exams)})")
            try:
                x, s, b = ftp_mirror.mirror(
                    sftp, remote, local, dry_run=args.dry_run,
                    log_callback=lambda m, level="INFO": None,  # per-file noise off
                )
            except Exception as e:  # noqa: BLE001 — one bad study must not kill the run
                print(f"    FAILED: {e}")
                failed.append((pv, study, str(e)))
                continue
            tot_x += x
            tot_s += s
            tot_b += b
            verb = "would transfer" if args.dry_run else "transferred"
            print(f"    {verb} {x} files ({b/1e9:.2f} GB), skipped {s} already-present")
    finally:
        transport.close()

    mins = (time.time() - t0) / 60
    print(f"\n{'DRY RUN — nothing transferred' if args.dry_run else 'DONE'}")
    print(f"  studies      : {len(studies) - len(failed)} ok, {len(failed)} failed")
    print(f"  files        : {tot_x} {'to transfer' if args.dry_run else 'transferred'}, "
          f"{tot_s} skipped (already present)")
    print(f"  bytes        : {tot_b/1e9:.2f} GB")
    print(f"  elapsed      : {mins:.1f} min")
    if failed:
        print("  FAILED studies (re-run to retry — the pull is resumable):")
        for pv, s, e in failed[:20]:
            print(f"    PV{pv} {s}: {e}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
