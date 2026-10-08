#!/usr/bin/env bash
# Stream AR: the production run of the MRI platform's archive ingest, mechanical. Gate: tasks/mri_archive_ingest_gate.md §7.
#
#   bash tools/drive_staging/mri_archive/ar_16_production.sh preflight          # read-only; any time after the last other writer
#   bash tools/drive_staging/mri_archive/ar_16_production.sh write              # the window (Ryan's go): reopen 0220, the batches, the claim workbook
#   bash tools/drive_staging/mri_archive/ar_16_production.sh write --from AR08_1019   # resume after a STOP (once its cause is fixed)
#   bash tools/drive_staging/mri_archive/ar_16_production.sh post               # read-only, after the window: full re-hash verify, idempotent dry runs, lists
#
# Git Bash on Ryan's workstation, from any directory. Every step prints its EXPECTED result next to what it got and
# STOPs at the first unexpected one (exit 1), naming the step, the log, and the rollback. Writes: the NAS (write phase
# only), the run folder below (off-NAS backups and logs), and D:\projects\gjesus3\mri_archive\out (logs).
# ONE REGISTRY WRITER AT A TIME: no other ingest (Cell Observer, drives, NI sync) may write during `write`.
#
# Rollback, per batch (no delete tool; Data Office, backup first): the batch's rows are exactly those whose ingest_config
# is tools/configs/mri_archive/mri_archive_<batch>.yaml. Restore $RUN/bk_<batch>/registry_raw.csv and ingest_manifest.csv
# if no other writer touched them since (rows = backup + the batch's), else remove the rows byte-exact (no BOM, CRLF);
# delete each row's /raw/DICOM/<YYYY>/<YYYY-MM>/<ACQ-ID>/ and its link folder in projects\<p>\raw_linked\ (the backup's
# raw_linked\<p>.txt lists what was there before); restore provenance\<p>.csv under the same rule; remove the subjects new
# in this batch from registry_subjects.csv (diff against the backup); regenerate the project's index.html
# (tools/generate_index.py --project <PROJ-ID>). The 0220 reopen is left in place (Q5). Full table: the gate, §7.

set -u
WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$WT" || exit 2
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools PYTHONIOENCODING=utf-8
NAS="${NAS:-J:/gjesus3-data}"          # REHEARSAL: NAS=<the D: rehearsal root> REHEARSAL=1 RUN=<a D: folder>
VALFLAG="${REHEARSAL:+--allow-missing-folders}"
S=tools/drive_staging/mri_archive
C=tools/configs/mri_archive
O="D:/projects/gjesus3/mri_archive/out"
RUN="${RUN:-C:/Users/rtasseff/temp/gjesus3_mri_archive_20261009}"   # off-NAS run folder: backups + logs (override with RUN=...)
CHK="python $S/ar_16_checks.py"
BACKUP="python tools/drive_staging/drive3/mri_09_backup.py"

# The batches, in the order they are written. AR03_0220 is FIRST so the 0220 reopen (Q5) sits immediately before it
# and before the baseline backup. Expected rows per batch = its case table (re-checked identical by the pre-flight).
BATCHES="AR03_0220 AR01_0118 AR02_0219 AR02n_0219 AR04_0320 AR04n_0320 AR05_0618 AR05n_0618 AR06_0619 AR07_0721 AR08_1019 AR09_1116 AR09n_1116 AR10_1319 AR11_1321 AR12_1519 AR13_noproject AR14_phantoms"
PROJECTS="AE-biomaGUNE-0118 AE-biomaGUNE-0219 AE-biomaGUNE-0220 AE-biomaGUNE-0320 AE-biomaGUNE-0618 AE-biomaGUNE-0619 AE-biomaGUNE-0721 AE-biomaGUNE-1019 AE-biomaGUNE-1116 AE-biomaGUNE-1319 AE-biomaGUNE-1321 AE-biomaGUNE-1519"
# The claim workbook after every batch: sessions / acquisitions to append (the extra m131 exam joins a session already
# listed, so it is in neither number). Set from the final plan; the gate §7 shows the derivation.
CLAIM_SESSIONS=__CLAIM_SESSIONS__
CLAIM_ACQS=__CLAIM_ACQS__

mkdir -p "$RUN/preflight" "$RUN/write" "$RUN/post"
LOG="$RUN/$(date +%Y%m%d_%H%M%S)_${1:-none}.log"
exec > >(tee -a "$LOG") 2>&1
step() { echo; echo "=== $(date +%H:%M:%S) $*"; }
stop() { echo; echo "##### STOP: $*"; echo "##### log: $LOG"; exit 1; }
project_of() { case "$1" in AR13_*|AR14_*) echo "";; *) echo "AE-biomaGUNE-${1##*_}";; esac; }
cfg() { echo "$C/mri_archive_$1.yaml"; }

preflight() {
  step "P1 validator (expect: validation OK; the pending-claim line is saved as the baseline)"
  python tools/validate_registries.py --nas-root "$NAS" --no-enrichment > "$RUN/preflight/validate.txt" 2>&1
  $CHK validator "$RUN/preflight/validate.txt" $VALFLAG --save-baseline "$RUN/preflight/pending_claim.txt" || stop "P1 the validator is not green: read $RUN/preflight/validate.txt"
  step "P2 the plan against live production (expect: names 0; session+day 0; sample+day = the 12 A2 only; links taken 0; dated 2026 0)"
  python $S/ar_05_plan.py > "$RUN/preflight/plan.txt" 2>&1 || stop "P2 ar_05_plan.py failed"
  $CHK plan "$RUN/preflight/plan.txt" || stop "P2 a live check differs: read $RUN/preflight/plan.txt"
  step "P3 the case tables rebuilt from the extract tree (expect: problems 0, taken 0; git: no change)"
  python $S/ar_07_cases.py > "$RUN/preflight/cases.txt" 2>&1 || stop "P3 ar_07_cases.py reports problems: $RUN/preflight/cases.txt"
  [ -z "$(git status --porcelain -- $C)" ] || stop "P3 the case tables or configs differ from the committed ones: git status -- $C"
  step "P4 every subject id in the facility DB now (expect: found == ok, 0 -None)"
  python $S/ar_14_subject_check.py > "$RUN/preflight/subjects.txt" 2>&1; rc=$?; head -1 "$RUN/preflight/subjects.txt"
  [ $rc = 0 ] || stop "P4 a subject id is not ok: $RUN/preflight/subjects.txt"
  step "P5 bytes (expect: exams with any file production holds: 0)"
  python $S/ar_06_bytes.py > "$RUN/preflight/bytes.txt" 2>&1
  grep -q "exams with any file production holds: 0 \[\]" "$RUN/preflight/bytes.txt" || stop "P5 a planned DICOM is in production: $RUN/preflight/bytes.txt"
  step "P6 dry runs, each bracketed (expect: every rc=0, registries changed=False; dedup proof total 0)"
  local all="$C/mri_archive_dedup_proof.yaml"; for b in $BATCHES; do all="$all $(cfg $b)"; done
  python $S/ar_09_run.py "$NAS" prod_pre $all > "$RUN/preflight/dryruns.txt" 2>&1 || stop "P6 a dry run failed or changed the registries: $RUN/preflight/dryruns.txt"
  python $S/ar_10_check_log.py "$O/dryrun_prod_pre_mri_archive_dedup_proof.log" DEDUP || stop "P6 the dedup proof listed an exam"
  for b in $BATCHES; do
    python $S/ar_10_check_log.py "$O/dryrun_prod_pre_mri_archive_$b.log" $b || stop "P6 $b: the dry run differs from its case table"
  done
  step "P7 snapshot of the registries (the write phase checks that no other MRI row arrived since)"
  $CHK snapshot "$NAS" "$RUN/preflight/snapshot.txt" || stop "P7 snapshot"
  date > "$RUN/preflight/PASS"; echo; echo "PREFLIGHT PASS"
}

batch() {
  local b=$1 p bk exp; p=$(project_of $b); exp=$($CHK cases $b)
  if [ "$b" = AR03_0220 ]; then
    step "W2 reopen AE-biomaGUNE-0220 (Q5), immediately before its batch (expect: dry run lists the changes; then status active)"
    python tools/reopen_project.py --nas-root "$NAS" --project AE-biomaGUNE-0220 --dry-run > "$RUN/write/reopen_dry.txt" 2>&1 || stop "W2 reopen dry run failed: $RUN/write/reopen_dry.txt"
    python tools/reopen_project.py --nas-root "$NAS" --project AE-biomaGUNE-0220 --reason "the MRI platform's archive: 3 studies of 2022 (STATUS 0.6 Q5, Ryan 2026-10-07)" > "$RUN/write/reopen.txt" 2>&1 || stop "W2 reopen failed: $RUN/write/reopen.txt (the project stays closed; nothing of the batch was written)"
    $CHK project-active "$NAS" AE-biomaGUNE-0220 || stop "W2 0220 is not active after the reopen"
    step "W3 baseline backup after the reopen, every target project (the post phase verifies against it)"
    [ -d "$RUN/bk1" ] || $BACKUP "$NAS" "$RUN/bk1" $PROJECTS > "$RUN/write/bk1.txt" 2>&1 || stop "W3 backup failed (another writer?)"
    bk="$RUN/bk1"
  else
    bk="$RUN/bk_$b"
    [ -d "$bk" ] || $BACKUP "$NAS" "$bk" ${p:-AE-biomaGUNE-0118} > "$RUN/write/bk_$b.txt" 2>&1 || stop "$b backup failed (another writer?)"
  fi
  step "$b: write $exp exams$([ -n "$p" ] && echo " into $p") (expect: Total = Success = $exp less any already committed, Failed 0)"
  python tools/ingest_raw.py --config "$(cfg $b)" --nas-root "$NAS" --refresh-index projects > "$RUN/write/run_$b.log" 2>&1
  grep -E '^\s*(Total|Success|Failed):' "$RUN/write/run_$b.log" | tr -s ' ' | tr '\n' ' '; echo
  $CHK run-log "$RUN/write/run_$b.log" "$exp" "$NAS" "$(cfg $b)" \
    || stop "$b: the run is not clean ($RUN/write/run_$b.log). Fix the cause and resume with: write --from $b (committed exams are skipped). Rollback: the gate §7, baseline $bk"
  step "$b: verify against $bk (expect: every check PASS)"
  python $S/ar_12_verify.py "$NAS" "$bk" $b > "$RUN/write/verify_$b.txt" 2>&1
  tail -1 "$RUN/write/verify_$b.txt"
  grep -q "^PASS  R1 the new rows" "$RUN/write/verify_$b.txt" && ! grep -q "^FAIL" "$RUN/write/verify_$b.txt" \
    || stop "$b: verify FAILED ($RUN/write/verify_$b.txt). An R1 failure with more rows than the batch's = another writer. Rollback: the gate §7, baseline $bk"
}

write() {
  local from="${1:-}"
  [ -f "$RUN/preflight/PASS" ] || stop "W0 no pre-flight PASS in $RUN/preflight: run the preflight first"
  step "W0 no other MRI row since the pre-flight; the validator green; the live plan checks again (expect: OK, OK, 6 of 6)"
  $CHK mri-unchanged "$NAS" "$RUN/preflight/snapshot.txt" || stop "W0 another writer added or removed MRI rows: re-run the preflight"
  python tools/validate_registries.py --nas-root "$NAS" --no-enrichment > "$RUN/write/validate_W0.txt" 2>&1
  $CHK validator "$RUN/write/validate_W0.txt" $VALFLAG || stop "W0 the validator is not green"
  if [ -z "$from" ]; then
    python $S/ar_05_plan.py > "$RUN/write/plan.txt" 2>&1; $CHK plan "$RUN/write/plan.txt" || stop "W0 a live check differs: $RUN/write/plan.txt"
    step "W1 backup before anything (rollback of the whole run, the reopen included)"
    [ -d "$RUN/bk0" ] || $BACKUP "$NAS" "$RUN/bk0" $PROJECTS > "$RUN/write/bk0.txt" 2>&1 || stop "W1 backup failed (another writer?)"
  fi
  local go=0; [ -z "$from" ] && go=1
  for b in $BATCHES; do
    [ "$b" = "$from" ] && go=1
    [ $go = 1 ] && batch $b
  done
  [ $go = 1 ] || stop "--from $from is not a batch"
  finish
}

finish() {
  step "W4 every batch complete (expect: each config's rows == its case table)"
  local total=0 b n exp
  for b in $BATCHES; do
    n=$($CHK rows "$NAS" "$(cfg $b)"); exp=$($CHK cases $b); total=$((total + n))
    [ "$n" = "$exp" ] || stop "W4 $b holds $n rows, expected $exp"
  done
  echo "rows written by this stream: $total"
  step "W5 validator after (expect: validation OK; pending-claim = the pre-flight's + $total)"
  python tools/validate_registries.py --nas-root "$NAS" --no-enrichment > "$RUN/write/validate_after.txt" 2>&1
  $CHK validator "$RUN/write/validate_after.txt" $VALFLAG --expect-pending-from "$RUN/preflight/pending_claim.txt" --plus $total \
    || stop "W5 the validator after the write: $RUN/write/validate_after.txt"
  python $S/ar_13_validate_new.py "$NAS" prod_after > "$RUN/write/validate_new.txt" 2>&1; head -1 "$RUN/write/validate_new.txt"
  grep -q "findings on them: 0;" "$RUN/write/validate_new.txt" || stop "W5 findings on the new rows: $O/validate_prod_after.txt"
  step "W6 the claim workbook, dry run (expect: to append $CLAIM_SESSIONS sessions ($CLAIM_ACQS acquisitions); every existing cell unchanged)"
  python tools/claim_workbooks.py claims-append --nas-root "$NAS" --preview-dir "$RUN/claims_preview" > "$RUN/write/claims_dry.txt" 2>&1 \
    || stop "W6 claims-append dry run refused (Excel open somewhere? lock file ~\$...): $RUN/write/claims_dry.txt"
  $CHK claims "$RUN/write/claims_dry.txt" $CLAIM_SESSIONS $CLAIM_ACQS || stop "W6 the claim-workbook preview differs: $RUN/write/claims_dry.txt"
  step "W7 the claim workbook, append (expect: APPENDED (claims); the workbook's copy in $RUN/claims_backup)"
  python tools/claim_workbooks.py claims-append --nas-root "$NAS" --apply --backup-dir "$RUN/claims_backup" > "$RUN/write/claims_apply.txt" 2>&1
  grep -q "^APPENDED (claims)" "$RUN/write/claims_apply.txt" || stop "W7 the append did not complete: $RUN/write/claims_apply.txt (it restores the workbook itself on a failed verification)"
  echo; echo "WRITE COMPLETE: $total acquisitions; claim workbook appended. Next (read-only, after the window): post"
}

post() {
  step "Q1 full verify, every file re-hashed, against the post-reopen baseline (expect: 18/18 checks PASS)"
  local list; list=$(echo $BATCHES | tr ' ' ',')
  python $S/ar_12_verify.py "$NAS" "$RUN/bk1" "$list" --rehash > "$RUN/post/verify_all.txt" 2>&1; tail -1 "$RUN/post/verify_all.txt"
  grep -q "^FAIL" "$RUN/post/verify_all.txt" && stop "Q1 a check FAILED: $RUN/post/verify_all.txt"
  step "Q2 idempotent dry runs (expect: every total 0; the dedup proof unchanged)"
  local all="$C/mri_archive_dedup_proof.yaml"; for b in $BATCHES; do all="$all $(cfg $b)"; done
  python $S/ar_09_run.py "$NAS" prod_post $all | tee "$RUN/post/dryruns.txt" | grep -v "'total': 0," && stop "Q2 a dry run lists something: $RUN/post/dryruns.txt"
  python $S/ar_10_check_log.py "$O/dryrun_prod_post_mri_archive_dedup_proof.log" DEDUP || stop "Q2 the dedup proof changed"
  step "Q3 the hand-over lists with the ACQ-IDs (assign workbook, placement batch)"
  python $S/ar_15_lists.py "$NAS"
  echo; echo "POST PASS"
}

case "${1:-}" in
  preflight) preflight ;;
  write) shift; [ "${1:-}" = "--from" ] && write "${2:-}" || write "" ;;
  finish) finish ;;
  post) post ;;
  *) echo "usage: $0 preflight | write [--from <batch>] | finish | post"; exit 2 ;;
esac
