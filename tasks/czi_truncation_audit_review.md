# `.czi` truncation audit (issue #17)

**Status:** ✅ Done 2026-10-17. Read-only; nothing was written to production.

**Tool:** `tools/audit_czi_truncation.py`, 10_TOOLS §3.10. It reads each file's ZISRAW header, directories and the furthest segments' headers, with no pixels.

**Result:** 17,271 live `.czi` primaries audited (CELL 14,596, LSM9 1,189, ZWSI 1,065, XMIC 421): **all `ok`**; 0 truncated, 0 unreadable, 0 missing. 829 s.

**Is the check meaningful?** For 17,269 files the furthest segment ends exactly at the last byte, so even a 1-byte truncation would show. The other two (`ACQ-20230530-CELL-052`, `ACQ-20241106-CELL-014`) have extra bytes after their last segment, the opposite of truncation.

**Sanity checks:** `ACQ-20251031-CELL-003` and `ACQ-20230707-CELL-001`, repaired in place on 2026-10-01 and 2026-10-06, read `ok`, as does the largest AxioScan file, `ACQ-20260304-ZWSI-005`.

**Repairs:** none needed. Any later ingest from a live share can be checked by re-running the tool.
