# LEONE comparison scripts (one-off, kept as the record)

One-off analysis for [`../leone_ingest_review.md`](../leone_ingest_review.md), 2026-10-02.
**Not reusable infrastructure.** Do not promote to `tools/` (BACKLOG 🔺 "one row per EXAM": code
that knows one collaborator's layout stays a record).

Run order:

1. `scan_zip_members.py` scans the DTS24 primaries (via `run_dts24.sh`); `scan_zip_sequential.py`
   scans `LEONE.zip`.
2. `s04` builds the DTS24 SOP index.
3. `s05` runs the comparison.
4. `s06`–`s07` are the drill-down.
5. `s08` writes the member disposition.
6. `s09` is the pixel sample.
7. `s10` builds the per-case table.

8. After Ryan's ruling (2026-10-02): `s11` builds the placement manifest (header-driven layout);
   `s12_place.py` dry-runs or executes the copy into `projects\DTS24\working\historical_drives\`
   (it imports stream A's `historical_paths.py` read-only); `s13_privacy_grep.py` checks published
   files for DOB values (counts only).

`s01`/`s03` are the catalog filter and zip-structure listing.

Inputs and outputs live in `D:\projects\gjesus3\staging\_analysis\leone-ingest\` and the SSD scratch
`C:\Users\rtasseff\temp\scratch_leone-ingest\`. The scanners write patient names and DOBs to
separate `*_identifiers.csv` files, used only as privacy-grep needles. Those files never leave D:
and are never committed.
