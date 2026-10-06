# Handoff — repair the `-AE-biomaGUNE-None` subject identifiers

**Status:** 📋 **PROPOSED — nothing has been run.** Branch `fix/subject-id-null-alias`,
worktree `gjesus3-dev\subject-id-null-alias`, off `main` `4aa09b1`.
**Owning backlog item:** `tasks/BACKLOG.md` → *"Facility-DB null project alias → `-None` subject ids
(2026-06-13)"*, re-audited 2026-08-13.
**Every number below was measured against live production on 2026-08-13/14**, not estimated.

---

## 1. What is wrong

A subject in this system is identified by `<animal_code>-AE-biomaGUNE-<NNNN>` — the animal's number
plus its animal-ethics protocol code. **444 acquisition rows in production carry
`<animal_code>-AE-biomaGUNE-None` instead**, because the protocol code came out null.

The cause is one line. `animal_db._query_subject` resolves a project two ways — first by
`projectAlias`, then, if that misses, by `project_code` — and then composes the identity from
`proj["projectAlias"]`:

```python
"facility_animal_id": compose_subject_id(animal["animal_code"], proj["projectAlias"]),
```

For four protocols the facility DB has a **populated `project_code` and a NULL `projectAlias`**.
They resolve fine through the second query, the animal is found, and every attribute comes back
correct — but the identity is then composed from the one field that is null, giving the literal
string `"None"`.

| Project | rows | by instrument |
|---|---:|---|
| `AE-biomaGUNE-0219` | 330 | MRI 260 · CT 70 |
| `AE-biomaGUNE-0618` | 67 | MRI 67 |
| `AE-biomaGUNE-1521` | 45 | PET 23 · CT 21 · MRI 1 |
| `AE-biomaGUNE-0619` | 2 | ZWSI 2 |

Also affected: **65 rows in `registry_subjects.csv`** with `project_alias = 'None'`, and **444
`/raw/` sidecars** whose `subject.facility_animal_id` carries the same bad string.

## 2. What is NOT wrong — read this before deciding urgency

**The biology is correct everywhere.** Each acquisition looked up its own `(project, animal)` pair
and got the right animal back; only the composed *label* broke. Verified on both sides of a
collision:

```
ACQ-20220124-MRI-001  (0219)  sex=M dob=2021-11-18 strain=C57BL/6NCrl   <- correct for 0219 animal 23
ACQ-20220118-PET-010  (1521)  sex=F dob=2021-02-10 strain=A/JOlaHsd     <- correct for 1521 animal 23
```

`/raw/` — the immutable record — is right. `project_id` is right. `age_at_acquisition` is right
(it derives from the correct DOB). Nothing needs re-ingesting and no bytes are at risk.

## 3. The part that IS a real defect — an identity collision

`-None` is not just an ugly label, it is **ambiguous**: four different protocols all collapse onto
it, so animal 23 of `0219` and animal 23 of `1521` become *the same subject id*. The subjects table
upserts on that id, so two genuinely different animals were merged into one row.

**3 collided ids, 47 acquisition rows:**

| subject id | claimed by | acq rows |
|---|---|---:|
| `23-AE-biomaGUNE-None` | `0219` + `1521` | 17 |
| `3-AE-biomaGUNE-None` | `0618` + `1521` | 15 |
| `4-AE-biomaGUNE-None` | `0618` + `1521` | 15 |

What the merged row stores vs. what is true:

```
23-AE-biomaGUNE-None  stored: sex=M  dob=2021-11-18  strain=C57BL/6NCrl        (= 0219's animal 23)
                      but 1521's 2 acquisitions on it are: F, 2021-02-10, A/JOlaHsd
3-/4-AE-biomaGUNE-None stored: F, 2018-08-15, B6.129P2-ApoE(tm1Unc)            (= 0618's animals)
                      but 1521's acquisitions on them are: F, 2021-02-10, A/JOlaHsd
```

So **anyone reading the subjects table gets the wrong sex, strain and a DOB off by ~2.5 years for
one of the two animals sharing each row.** That is the same failure shape as the DTS24 wrong-date
bug: succeeded, reported success, wrote something untrue.

**Bounding it honestly:** the subjects table is derived, the per-acquisition sidecars are right, and
44 of the 47 rows are only mislabelled rather than mis-attributed. This is a correctness defect
worth fixing properly, not an emergency.

## 4. The fix, in order

**Do them in this order.** Fixing the source first means the backfill cannot race against a new
ingest re-creating the problem.

### 4.1 Stop it recurring — `tools/animal_db.py`

Compose from an alias that cannot be null. The caller already knows the code it asked for:

```python
        # The project may have resolved through project_code, whose projectAlias
        # is NULL for some protocols (0219 / 0618 / 0619 / 1521). Composing the
        # identity from that field yields "<n>-AE-biomaGUNE-None", which is not
        # just ugly — it is AMBIGUOUS, because every null-alias protocol collapses
        # onto the same id and the subjects-table upsert then merges two different
        # animals into one row. Fall back to the alias the caller asked for.
        alias = (proj["projectAlias"] or "").strip() or str(project_alias).strip()
```
```python
        "facility_animal_id": compose_subject_id(animal["animal_code"], alias),
```

Belt and braces in `compose_subject_id` itself — it should refuse to build an id it knows is
broken rather than return a plausible-looking string:

```python
    if not project_alias or str(project_alias).strip().lower() in ("none", "null"):
        raise ValueError(
            f"refusing to compose a subject id with a null project alias "
            f"(animal {animal_code!r}) — see tasks/BACKLOG.md 'Facility-DB null project alias'"
        )
```

⚠️ `animal_db.py` is **shared by every ecosystem's enrichment**. Keep the change to these lines.
Run the whole suite, not just the new tests.

### 4.2 A detector — `tools/validate_registries.py`

An ERROR (not a warning) for any `subject_ids` containing `-AE-biomaGUNE-None`, and for any
`registry_subjects.project_alias` equal to `None`/empty. This is exactly the class of thing that
sat unnoticed for two months. Expect it to report 444 + 65 until 4.3 runs — that is the point.

### 4.3 Backfill — a new `tools/recover_subject_ids.py`

Follow the established deferred-recovery pattern (`tools/recover_subject_metadata.py` is the
reference; see the memory note `recovery_tool_pattern.md`): worklist → re-derive → controlled
in-place write → verify → report. `--dry-run` by default, `--apply` to write.

**The correct value needs no DB call.** `registry_raw.project_id` → `registry_projects.name` →
the `NNNN` after `AE-biomaGUNE-`. That is already correct on all 444 rows, which is what makes
this repairable at all.

Three writes per acquisition, all idempotent:

1. **Sidecar** `subject.facility_animal_id` — the `/raw/` write. Atomic temp + replace, and
   **recompute the file's entry in `checksums.json`** if the sidecar is covered by it (check
   first — do not silently invalidate a checksum).
2. **`registry_raw.subject_ids`** — replace only the `-None` element, preserve the rest of the
   `;` list verbatim. Under `locking.registry_lock`, atomic temp + `os.replace`.
3. **`registry_subjects.csv`** — the only structural change. The 65 bad rows become **68**: the 3
   collided ids split into 6, each carrying its own animal's attributes. Take those attributes
   from the facility DB and **cross-check them against the sidecars** — if the two disagree, stop
   and report rather than pick one.

**Non-negotiables**, all precedented in this repo:

- **Back up all registry CSVs off-NAS first** and verify byte-identical before any write
  (`C:\Users\rtasseff\temp\gjesus3_subject_id_fix_<date>\`).
- Hold `locking.registry_lock` across each read-modify-write. Other sessions append rows during
  long operations — that has happened before, ~150 rows mid-run.
- **Line-oriented edits on `registry_raw.csv`, not a `csv` round-trip** — a round-trip rewrites
  all 15,474 rows and can disturb the BOM, quoting and line endings. Precedent: the 2026-08-12
  `99_test` removal.
- Idempotent: a second `--apply` must change 0 rows.

### 4.4 Fix the source data (independent, does not block)

Ask the animal facility to populate `projectAlias` for `0219` / `0618` / `0619` / `1521`, and to
audit for other null-alias projects. Ryan first emailed them 2026-06-13; it has not happened. The
code fix in 4.1 means we no longer depend on it.

## 5. Verification before calling it done

- `validate_registries` → **0** `-None` findings across all rows.
- `registry_subjects.csv` → **1,124** rows, no `project_alias` of `None`.
  ⚠️ **Corrected 2026-08-14 — this line previously said 1,149 and was wrong.** It
  assumed all 68 corrected ids are new. **25 of them already have rows** (animals whose
  other acquisitions resolved correctly — the partial 2026-06 back-fill), so the upsert
  merges those instead of inserting. The arithmetic is 1,146 − 65 stale + 43 genuinely
  new = **1,124**, i.e. the table gets *smaller*. Measured against live data, not estimated.
- The 3 previously-collided animals resolve to 6 distinct ids, each matching the facility DB.
- Spot-check both sides of a collision: `ACQ-20220124-MRI-001` → `23-AE-biomaGUNE-0219`;
  `ACQ-20220118-PET-010` → `23-AE-biomaGUNE-1521`.
- Sidecar, registry row and subjects row agree for a sample from each of the four projects.
- `verify_checksums` clean over the touched acquisitions.
- Re-run `--apply`: 0 changes.
- Full suite green.

## 6. Then

Update `CHANGELOG.md`, `tasks/STATUS.md`, and tick the boxes in the `BACKLOG.md` item (which
carries the full audit). Merge `--no-ff` and push — **pushing no longer needs permission**
(`CLAUDE.md` "## Git", changed 2026-08-14); NAS/production writes still do, and §4.3 is one of
those, so **get Ryan's go-ahead before `--apply`**.

## 7. Watch for

- **`0219` is the one to be careful with** — 330 of the 444 rows, and it reached that size because
  this item predicted it would surface during the no-DICOM regeneration pass and it was not fixed
  first. It spans MRI *and* NI, so it exercises two ingest paths.
- **The BACKLOG item's "452 rows already back-filled" claim no longer holds** — 328 MRI rows carry
  `-None` today. Re-measure; do not trust that count.
- **The `S:\gnuclear` NI backfill added 114 of the 444** (`0219` ×70, `1521` ×44) but is **not** the
  cause. Its anchored-`LIKE` fix changed *which project resolves*, not *how the identity is
  composed*; the old unanchored form resolved these same two codes just as well.
- **`registry_subjects.csv` also has 75 rows with a blank `project_alias`** (`facility_id` like
  `LEONE_1.01`, `source=dicom-header`). Those are DTS24 human subjects with no animal protocol —
  **legitimate, leave them alone.** Only `project_alias == 'None'` is in scope.
