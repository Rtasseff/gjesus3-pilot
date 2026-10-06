#!/bin/bash
# DTS24 zip primaries, sequential over SMB (one at a time).
cd /d/projects/gjesus3/staging/_analysis/leone-ingest
rm -f scan/dts24_ACQ-*.csv
: > scan/dts24.log
tr -d '\r' < scan/dts24_list.txt > scan/dts24_list_lf.txt
while IFS='|' read -r acq p; do
  python scan_zip_members.py "$p" scan/dts24_$acq --label "$acq" >> scan/dts24.log 2>&1 || echo "FAILED $acq" >> scan/dts24.log
done < scan/dts24_list_lf.txt
echo "DTS24 ALL DONE" >> scan/dts24.log
