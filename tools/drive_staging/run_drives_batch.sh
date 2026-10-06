#!/bin/bash
# The historical-drives .czi ingest: ONE production batch, exactly as tasks/drives_microscopy_ingest_runbook.md
# §2 (step 0, then a-f). It stops on the first failed condition, before the run if it can.
#   bash tools/drive_staging/run_drives_batch.sh B05
# Read the output: every line must be as the runbook's pass conditions say. Git Bash on Windows.
set -u
B=$1
D=$(date +%Y%m%d)
cd "C:/Users/rtasseff/OneDrive - CIC biomaGUNE/projects/DataInfra/gjesus3-archive/gjesus3-dev/drives-microscopy-ingest" || exit 9
CFG=tools/configs/drives_2026-09/drives_$B.yaml
N=$(awk -F, -v b="$B" '$1==b {print $4}' tools/configs/drives_2026-09/batches.csv)

# 0. the frozen plan is still right for this batch (fresh production hash index; all checks PASS)
python tools/drive_staging/catalog.py production > /dev/null 2>&1 || { echo "STOP: catalog.py production failed"; exit 3; }
python tools/drive_staging/ingest_check.py --batch $B > "/tmp/drives_check_$B.log" 2>&1
grep -E "^(PASS|FAIL)" "/tmp/drives_check_$B.log"
if grep -q "^FAIL" "/tmp/drives_check_$B.log" || ! grep -q "'skips': 0" "/tmp/drives_check_$B.log"; then
  echo "STOP: step 0 failed (see /tmp/drives_check_$B.log)"; exit 3; fi

# a. backup
BK="C:/Users/rtasseff/temp/gjesus3_registry_backup_${D}_drives_${B}"
if [ -e "$BK" ]; then echo "STOP: backup dir exists"; exit 1; fi
mkdir -p "$BK" && cp -p /j/gjesus3-data/registries/*.csv /j/gjesus3-data/registries/.acq_id_seq.json "$BK/" || exit 1
( cd /j/gjesus3-data/registries && sha256sum *.csv .acq_id_seq.json ) > "$BK/SHA256SUMS.src"
( cd "$BK" && sha256sum -c --quiet SHA256SUMS.src ) || { echo "STOP: backup does not verify"; exit 1; }
echo "a. backup $BK verified"

# b. target
grep -n "staging_dir\|auto_create_projects\|instrument:" "$CFG"

# c. dry run
python tools/ingest_raw.py -c "$CFG" --nas-root "J:\gjesus3-data" --dry-run > "$BK/dryrun.log" 2>&1
SK=$(grep -c "SKIP" "$BK/dryrun.log"); CASES=$(grep -o "Batch: [0-9]* cases" "$BK/dryrun.log")
echo "c. dry run: $CASES (planned $N), SKIP lines $SK"
if [ "$CASES" != "Batch: $N cases" ] || [ "$SK" != "0" ]; then echo "STOP: dry run does not match the plan"; exit 2; fi
case "$B" in B15|B16)
  st=$(awk -F, '$2=="AE-biomaGUNE-1019"||$2=="AE-biomaGUNE-0219"{print $2"="$6}' /j/gjesus3-data/registries/registry_projects.csv)
  echo "$st" | grep -q "=closed" && { echo "STOP: target project still closed ($st) -- reopen first (runbook §1)"; exit 2; } ;;
esac

# d. the run
s=$(date +%s)
python tools/ingest_raw.py -c "$CFG" --nas-root "J:\gjesus3-data" --refresh-index projects > "$BK/run.log" 2>&1
echo "d. run exit=$? secs=$(( $(date +%s) - s ))"
grep -A4 "BATCH SUMMARY" "$BK/run.log" | grep -E "Total|Success|Failed"
grep -q "Success:  $N$" "$BK/run.log" && grep -q "Failed:   0$" "$BK/run.log" || { echo "STOP: the run did not ingest all $N with 0 failed"; exit 4; }

# e. verify + provenance + validator
python tools/drive_staging/ingest_verify.py --nas-root "J:\gjesus3-data" --batch $B \
    --provenance tasks/drives_ingest_provenance.csv || { echo "STOP: ingest_verify FAILED"; exit 5; }
python tools/validate_registries.py --nas-root "J:\gjesus3-data" --no-enrichment > "$BK/validate_after.txt" 2>&1
NE=$(grep -c 'ERROR: \[' "$BK/validate_after.txt"); NP=$(grep 'ERROR: \[' "$BK/validate_after.txt" | grep -vc '<REQUIRED - set via mri-ingest')
echo "e. validator errors $NE, non-placeholder $NP (baseline 10314 / 0)"
[ "$NE" = "10314" ] && [ "$NP" = "0" ] || { echo "STOP: validator count moved"; exit 6; }
grep -E "Refreshing|targeted refresh" "$BK/run.log" | tail -2

# f. idempotency
python tools/ingest_raw.py -c "$CFG" --nas-root "J:\gjesus3-data" > "$BK/rerun.log" 2>&1
echo "f. re-run: $(grep 'Total:' "$BK/rerun.log")"
grep -q "Total:    0$" "$BK/rerun.log" || { echo "STOP: the re-run added rows"; exit 7; }
echo "WARN lines in run: $(grep -c WARN "$BK/run.log")"
grep WARN "$BK/run.log" | sed 's/\[[0-9:]*\] //; s/ACQ-[0-9A-Z-]*//g; s/[0-9]*-AE-biomaGUNE-[0-9]*//g' | cut -c1-100 | sort | uniq -c | sort -rn | head -6
echo "BATCH $B DONE"
