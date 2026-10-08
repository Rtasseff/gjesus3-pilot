#!/bin/bash
# ONE production batch of a historical-drive .czi ingest: step 0, then a-f, exactly as the profile's
# procedure says (drives 1+2: tasks/drives_microscopy_ingest_runbook.md §2; drive 3: tasks/drive3_czi_gate.md §4).
# It stops at the first failed condition, before the run whenever it can.
#   bash tools/drive_staging/run_drives_batch.sh B05                    # drives 1+2 (the default profile)
#   bash tools/drive_staging/run_drives_batch.sh drive3_2026-10 C01    # M. Jesus's drive
# Read the output: every line must be as the pass conditions say. Git Bash on Windows.
# Generalised 2026-10-06 (third drive): the checkout is where this script lives (no hard-coded worktree);
# the profile's settings come from ingest_plan.PROFILES; the validator is compared with its own run just
# before the batch (the old fixed "10314" baseline went stale on 2026-10-05, when D1(a) made it 0).
set -u
if [ $# -eq 1 ]; then PROFILE=drives_2026-09; B=$1; elif [ $# -eq 2 ]; then PROFILE=$1; B=$2; else
  echo "usage: run_drives_batch.sh [PROFILE] BATCH"; exit 9; fi
D=$(date +%Y%m%d)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE/../.." || exit 9
export PYTHONDONTWRITEBYTECODE=1
NAS="J:\gjesus3-data"
SETTINGS=$(python -c "
import sys; sys.path.insert(0, 'tools/drive_staging'); import ingest_plan as P
P.use_profile('$PROFILE'); print(P.config_file('$B')); print(P.CONFIG_DIR_REL + '/batches.csv')
print(P.CAT); print(P.PROVENANCE); print(P.PROFILE_NAME.split('_')[0])") || { echo "STOP: unknown profile $PROFILE"; exit 9; }
CFG=$(echo "$SETTINGS" | sed -n 1p); BATCHES=$(echo "$SETTINGS" | sed -n 2p); CAT=$(echo "$SETTINGS" | sed -n 3p)
PROV=$(echo "$SETTINGS" | sed -n 4p); TAG=$(echo "$SETTINGS" | sed -n 5p)
N=$(awk -F, -v b="$B" '$1==b {print $4}' "$BATCHES")
[ -n "$N" ] || { echo "STOP: batch $B is not in $BATCHES"; exit 9; }
echo "profile $PROFILE, batch $B: $N files, config $CFG"

# 0. the frozen plan is still right for this batch (fresh production hash index; all checks PASS)
python tools/drive_staging/catalog.py production --out "$CAT" > /dev/null 2>&1 || { echo "STOP: catalog.py production failed"; exit 3; }
python tools/drive_staging/ingest_check.py --profile "$PROFILE" --batch "$B" > "/tmp/drives_check_${TAG}_$B.log" 2>&1
grep -E "^(PASS|FAIL)" "/tmp/drives_check_${TAG}_$B.log"
if grep -q "^FAIL" "/tmp/drives_check_${TAG}_$B.log" || ! grep -q "'skips': 0" "/tmp/drives_check_${TAG}_$B.log"; then
  echo "STOP: step 0 failed (see /tmp/drives_check_${TAG}_$B.log)"; exit 3; fi

# a. backup, and the validator as it stands before the batch
BK="C:/Users/rtasseff/temp/gjesus3_registry_backup_${D}_${TAG}_${B}"
if [ -e "$BK" ]; then echo "STOP: backup dir exists"; exit 1; fi
mkdir -p "$BK" && cp -p /j/gjesus3-data/registries/*.csv /j/gjesus3-data/registries/.acq_id_seq.json "$BK/" || exit 1
( cd /j/gjesus3-data/registries && sha256sum *.csv .acq_id_seq.json ) > "$BK/SHA256SUMS.src"
( cd "$BK" && sha256sum -c --quiet SHA256SUMS.src ) || { echo "STOP: backup does not verify"; exit 1; }
echo "a. backup $BK verified"
python tools/validate_registries.py --nas-root "$NAS" --no-enrichment > "$BK/validate_before.txt" 2>&1
NE0=$(grep -c '^  ERROR: ' "$BK/validate_before.txt"); grep -E "^(errors|warnings):" "$BK/validate_before.txt" | tr '\n' ' '; echo

# b. target: the config points at the farm, the run at J:; every target project exists and is active
grep -n "staging_dir\|auto_create_projects\|instrument:" "$CFG"
python -c "
import csv, io, sys
b = [r for r in csv.DictReader(io.open('$BATCHES', encoding='utf-8-sig', newline='')) if r['batch'] == '$B'][0]
st = {r['name']: r['status'] for r in csv.DictReader(io.open(r'$NAS\registries\registry_projects.csv', encoding='utf-8-sig', newline=''))}
bad = [p for p in b['projects'].split(';') if p and p != '(none)' and st.get(p) != 'active' and b.get('auto_create') != 'Y']
print('b. target projects:', b['projects'], '| not active:', bad or 'none')
sys.exit(1 if bad else 0)" || { echo "STOP: a target project is not active -- reopen it first (the procedure)"; exit 2; }

# c. dry run (read-only on J:): every planned case, no SKIP, no refused link name
python tools/ingest_raw.py -c "$CFG" --nas-root "$NAS" --dry-run > "$BK/dryrun.log" 2>&1
SK=$(grep -c "SKIP" "$BK/dryrun.log"); CASES=$(grep -o "Batch: [0-9]* cases" "$BK/dryrun.log")
RF=$(grep -c "Refusing" "$BK/dryrun.log")
echo "c. dry run: $CASES (planned $N), SKIP lines $SK, refused link names $RF"
if [ "$CASES" != "Batch: $N cases" ] || [ "$SK" != "0" ] || [ "$RF" != "0" ] || ! grep -q "Failed:   0$" "$BK/dryrun.log"; then
  echo "STOP: dry run does not match the plan"; exit 2; fi

# d. the run
s=$(date +%s)
python tools/ingest_raw.py -c "$CFG" --nas-root "$NAS" --refresh-index projects > "$BK/run.log" 2>&1
echo "d. run exit=$? secs=$(( $(date +%s) - s ))"
grep -A4 "BATCH SUMMARY" "$BK/run.log" | grep -E "Total|Success|Failed"
grep -q "Success:  $N$" "$BK/run.log" && grep -q "Failed:   0$" "$BK/run.log" || { echo "STOP: the run did not ingest all $N with 0 failed"; exit 4; }

# e. verify + provenance; the validator unchanged against step a
python tools/drive_staging/ingest_verify.py --profile "$PROFILE" --nas-root "$NAS" --batch "$B" \
    --provenance "$PROV" || { echo "STOP: ingest_verify FAILED"; exit 5; }
python tools/validate_registries.py --nas-root "$NAS" --no-enrichment > "$BK/validate_after.txt" 2>&1
NE=$(grep -c '^  ERROR: ' "$BK/validate_after.txt")
echo "e. validator errors before $NE0, after $NE"
grep '^  ERROR: ' "$BK/validate_before.txt" | sort > "$BK/errors_before.txt"; grep '^  ERROR: ' "$BK/validate_after.txt" | sort > "$BK/errors_after.txt"
cmp -s "$BK/errors_before.txt" "$BK/errors_after.txt" || { echo "STOP: the validator's errors changed (diff $BK/errors_before.txt errors_after.txt)"; exit 6; }
grep -E "Refreshing|targeted refresh" "$BK/run.log" | tail -2

# f. idempotency
python tools/ingest_raw.py -c "$CFG" --nas-root "$NAS" > "$BK/rerun.log" 2>&1
echo "f. re-run: $(grep 'Total:' "$BK/rerun.log")"
grep -q "Total:    0$" "$BK/rerun.log" || { echo "STOP: the re-run added rows"; exit 7; }
echo "WARN lines in run: $(grep -c WARN "$BK/run.log")"
grep WARN "$BK/run.log" | sed 's/\[[0-9:]*\] //; s/ACQ-[0-9A-Z-]*//g; s/[0-9]*-AE-biomaGUNE-[0-9]*//g' | cut -c1-100 | sort | uniq -c | sort -rn | head -6
echo "BATCH $B DONE"
