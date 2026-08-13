# Review findings — `ni_gnuclear_production_runbook.md`, 2026-08-13

**Status:** 🔶 **ACTION REQUIRED before the §3 production run.** Ryan reviewed the runbook and
asked for these changes first. **Everything below is measured, not estimated** — the commands were
run read-only against the live staging snapshot, the live production registry, and the
animal-facility DB.

**The plan itself is sound.** Staging first, per-recon identity keyed on the machine-issued
filename, escalating batches with a hard stop between them, `original_name` = the acquisition key
so the existing dedup becomes canonical without touching `_build_dedupe_index` — all of that
stands. Verified independently: 1,523 / 131 / 658 reproduces exactly, production NI is still 132
rows (66 PET + 66 CT), the sandbox's 227 rows carry proper ISO-8601 `acquisition_datetime`
(`2024-09-30T09:19:38Z`) and `checksum_present=Y`, all 16 `tools/test_*.py` suites pass, and
61 TB is free for a ~195 GB write.

Also worth recording, since it is the freshest production scar: **this path does not touch
`dicom_utils.extract_study_date`.** `acquisition_datetime` comes from the 14-digit filename
timestamp. The HIGH-priority backlog trap that put two 2019 exams into production as
`ACQ-20260812-XMRI-*` cannot fire here.

---

## Framing — this is a one-time move (Ryan, 2026-08-13)

This data grew up on a drive with **no standards enforcement**, and it is being moved **once**.
Future NI ingest will run close to real time by the operators/researchers themselves, out of a
system with standards — the data path comes off the acquisition device uniformly — and the
operator will be shown a **dry run with review tables** where corrections get made before
anything is written.

**So: fix this here, scoped to this pull. Do not build a general architecture for it.** The
patches below are deliberately small and live in this pull's own tools. The one exception
(§5.4, `animal_db.py`) is a genuine latent bug in shared code and is four lines.

---

## 1. ⛔ The blocking finding — 21 of the 25 new projects are not real protocols

The run as written auto-creates **25 new projects** in production. Validated against the
animal-facility DB `projects` table: **14 of the 35 resolved codes are real protocols
(1,409 acqs); 21 are not (114 acqs).**

They are not near-misses. They are other things in the path being read as a protocol code:

```
2023/Jesus/Marina/1321/231120/100/Respiratory gated/…  → code "100"   (real: 1321 — 100 is the animal)
2023/Jesus/MJ/0522/230217-FDG/16/…                     → code "2302"  (real: 0522 — 2302 is the DATE 230217)
2023/Jesus/Ermal/Carlotta_b/0421/231026/230/r1/…       → code "230"   (real: 0421)
2023/Jesus/Kepa/cancer/241/1 week/…                    → code "241"   (animal number; no protocol in the path at all)
2022/Jesus/MOLECUBES/211217/245_2h30min/…              → code "245"   (animal number)
```

`2301 / 2302 / 2306 / 2506` are **date prefixes** (`230119`, `230217`, `230612`, `250613`) turned
into regulatory identifiers. The rest are animal numbers.

**This contradicts the branch's own stated principle.** 658 acquisitions are held back because
"an AE code is a regulatory identifier and must never be guessed" — while 114 get a guessed one,
each becoming a project folder, a registry row, and a `subject_ids` value like
`r1-AE-biomaGUNE-230`.

Note that **batch 1 — the single-acquisition production smoke test — is one of these.** It would
open the run by creating `AE-biomaGUNE-245`.

Two things I checked rather than assumed, both good news: none of the 114 receives *wrong*
subject metadata today (all miss the DB and queue to pending), and the failure is confined to the
project cell. But there is a latent path to real wrong metadata — see §5.4.

---

## 2. The fix — validate against the facility DB, and walk up to the real code

The true code is usually **already in the path**, one or two levels above where the parser
stopped. So rather than just rejecting a bad code, walk up whole path segments to the first
DB-valid one.

### Measured result

| | acqs |
|---|---:|
| code already DB-valid — unchanged | **1,409** |
| **recovered to the real code** | **99** |
| no valid code anywhere → joins the held-back set | **15** |
| **TOTAL INGESTED** | **1,508** (was 1,523) |
| held back | **673** (was 658) |

Recovery map: `2302→0522` ×32 · `2306→0522` ×30 · `2506→0324` ×12 · `2301→0522` ×4 ·
`231→0421` ×4 · `236→0421` ×4 · `237→0421` ×4 · `230→0421` ×3 · `100→1321` ×2 · `101→1321` ×2 ·
`102→1321` ×2

**Independent proof the recovered codes are right: 93 of 93 recovered `(project, animal)` pairs
resolve in the animal-facility DB — 0 not-found.** (The other 6 parse no animal number.) Animal 16
really does exist under protocol 0522. That is confirmation from a source that knows nothing about
the folder tree.

**New projects created drops from 25 (21 bogus) to 4 — `1122`, `0324`, `1024`, `0421` — all four
DB-verified real protocols.**

### ⚠️ Correction to the number Ryan was given

The review said "recovers 100 of 114, skip the last 14." The tested implementation recovers
**99 and drops 15**. The difference is a deliberate rejection: a looser prototype rescued
`245 → 1217` by finding a 4-digit run *inside* the date folder `211217`. That is the same
guessing problem in a new place, so the shipped rule matches **whole segments only** and correctly
refuses it. Ryan's instruction to skip the unrecoverable remainder stands — it is 15, not 14.

### The 15 that drop (they join the 658, no further work)

`Kepa` 241/242/243/244 (8) · `Alba` 304/305/306/308/386 (6) · `211217` 245 (1)

**These are entire batches.** Runbook batches **1 (`211217`), 2 (`Kepa`) and 3 (`Alba`) disappear
completely** — every one of their acquisitions was under a fabricated code. See §4.

---

## 3. The patches

### 3.1 `tools/ni_gnuclear_discover.py` — validation + walk-up

Add after the existing regex block (near `BARE_NUM_RE`):

```python
# --- animal-protocol code validation (tasks/REVIEW_FINDINGS_2026-08-13.md) ---
# An AE code is a regulatory identifier, so it is validated against the facility
# DB rather than trusted from the path. `AE_CODE_RE` is ANCHORED on the
# `AE-biomaGUNE-` segment: project_code `AE-biomaGUNE-1317/PRO-AE-SS-101` yields
# 1317 and NOT 101 — an unanchored suffix match is exactly the bug in §5.4.
AE_CODE_RE = re.compile(r"AE-biomaGUNE-(\d{3,4})(?![0-9])")
# A candidate must be the WHOLE segment (or its `<code>_…` / `<code>-…` head).
# Matching any digit run inside a segment re-introduces the guessing: it pulls
# `1217` out of the date folder `211217`.
SEG_CODE_RE = re.compile(r"^(\d{3,4})(?:[_-]|$)")

_VALID_CODES = None


def valid_protocol_codes(conn=None):
    """The authoritative set of animal-protocol codes, from the facility DB.

    One query, cached for the process. Raises rather than returning an empty set:
    for a one-time bulk write, refusing to run beats silently reverting to
    guessing codes from the path.
    """
    global _VALID_CODES
    if _VALID_CODES is not None:
        return _VALID_CODES
    import animal_db
    own = conn is None
    conn = conn or animal_db.get_connection()
    codes = set()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT project_code, projectAlias FROM projects")
            for r in cur.fetchall():
                alias = (r.get("projectAlias") or "").strip()
                if re.fullmatch(r"\d{3,4}", alias):
                    codes.add(alias)
                codes.update(AE_CODE_RE.findall(r.get("project_code") or ""))
    finally:
        if own:
            conn.close()
    if not codes:
        raise RuntimeError(
            "the facility DB returned no protocol codes — refusing to run rather "
            "than fall back to guessing codes from the path"
        )
    _VALID_CODES = codes
    return codes


def recover_project(segs, valid):
    """First DB-valid protocol code walking UP whole path segments."""
    for seg in reversed(segs):
        m = SEG_CODE_RE.match(seg)
        if m and m.group(1) in valid:
            return m.group(1)
    return None
```

Change the signature to `def analyse(rel, size=0, valid_codes=None):`, then insert between the
`date_flag` block and the `keys = [...]` line (currently 220/221):

```python
    # The parser stops at the first non-noise level walking up, which on this
    # source is often an animal number or a date rather than the protocol. Check
    # it, and if it is wrong look further up — the real code is usually already
    # in the path, one or two levels above.
    project = p["project"] or ""
    if valid_codes is not None and project and project not in valid_codes:
        rec = recover_project(segs[:-1], valid_codes)
        if rec:
            flags.append(f"project-recovered:{project}->{rec}")
            project = rec
        else:
            flags.append(f"project-rejected:{project}")
            project = ""
```

Then use `project` in the two places that read `p["project"]`:

```python
    keys = [ni_live_discover.facility_id(a["number"], project) for a in p["animals"]]
```
```python
        "project": project,
```

In `main()`, load the codes so the review table shows the corrected values (add a `--no-db`
escape hatch if you want one for offline use):

```python
    valid = valid_protocol_codes()
    ...
        row = analyse(rel, size, valid_codes=valid)
```

**Deliberately NOT done:** the same walk-up would also rescue some of the 658 held-back
acquisitions. Left alone — that cohort is D-G and belongs to the researcher mapping, and touching
it would invalidate the measured numbers above. Worth a note in the plan, not a change here.

### 3.2 `tools/ingest/ni_flat.py` — thread it through

```python
def discover(staging_dir, registry_path=None, researchers=None,
             require_project=True, validate_projects=True):
    valid = nd.valid_protocol_codes() if validate_projects else None
```
```python
            row = nd.analyse(rel, valid_codes=valid)
```

Add the counts to the summary the operator reads — a silent repair is not much better than a
silent guess:

```python
    n_recovered = sum(1 for e in index.values()
                      if any(f.startswith("project-recovered")
                             for f in e["discovered"]["parse_flags"]))
    if n_recovered:
        print(f"[ni_flat] {n_recovered} acquisition(s) had a path-derived project "
              f"code that is NOT a real protocol; the real code was recovered from "
              f"higher in the path (see the parse_flags column).")
```

### 3.3 `tools/templates/instruments/molecubes_ni_gnuclear.yaml` + `config.py`

Under `auto_discover:`:

```yaml
  # Validate the path-derived protocol code against the animal-facility DB, and
  # walk up to the real code when it is wrong. Leave TRUE — with it off, 114 of
  # these acquisitions file themselves under an invented AE code.
  validate_projects: true
```

In `config.py`'s `ni_flat.discover(...)` call, defaulting to on so it cannot be forgotten:

```python
            validate_projects=bool(disco.get("validate_projects", True)),
```

### 3.4 Tests

Add to `tools/test_ni_flat.py`, using a fixed fake code set (no DB in tests):

- `2023/Jesus/MJ/0522/230217-FDG/16/…` → `0522`, flag `project-recovered:2302->0522`
- `2023/Jesus/Marina/1321/231120/100/Respiratory gated/…` → `1321`
- `2023/Jesus/Kepa/cancer/241/1 week/…` → `""`, flag `project-rejected:241`, held back
- `2022/Jesus/MOLECUBES/211217/245_2h30min/…` → `""` — **the date folder `211217` must NOT
  yield `1217`**; this is the regression guard for the whole-segment rule
- `2025/Jesus/Irene/250117_Ermal/0324_19/…` → `0324` unchanged, no flag

---

## 4. Consequences for the runbook

**§3.2's batch table changes.** Batches 1–3 (`211217`, `Kepa`, `Alba`) vanish entirely — 10
batches become 8:

| # | `researchers:` | Acqs (was) |
|---|---|---:|
| 1 | `[CarlottaS]` | 20 (20) |
| 2 | `[Ermal]` | 25 (25) |
| 3 | `[IAZ_MJ]` | 133 (133) |
| 4 | `[MJ]` | **216 → 282** (2302/2306/2301 recovered into 0522) |
| 5 | `[Itziar]` | 227 (227) — sandbox-proven |
| 6 | `[Irene]` | **384 → 396** (2506 → 0324) |
| 7 | `[Marina]` | **503 → 509** (100/101/102 → 1321) |
| | **TOTAL** | **1,508** |

Re-derive this table from the code rather than copying it — the per-researcher totals above are
measured, but the batch-size pass condition in §3.3 depends on them being exact.

**The 1-acquisition smoke test is gone.** Either accept `CarlottaS` (20 acqs, 8.9 GB, ~8 min) as
the new batch 1, or carve a deliberate one-acquisition slice. Do not skip the smoke step.

**Re-run Phase 3 in the sandbox before production.** Not the whole cohort — `MJ` is the cheap,
high-value check, because it is where the recovery actually fires (66 acqs move to 0522). Confirm
those land in `AE-biomaGUNE-0522` and their DB lookups resolve.

**§6 of the runbook:** the `--from-plan <snapshot>/_plan.csv` command references a file that is not
in the snapshot (`ls` shows only `_manifest.jsonl`, `_pull.log`, `_verify.log`). Use `--root`.

---

## 5. Secondary — fix before the run, not blockers

### 5.1 The batch-config generator can silently produce a full-source run

§3.1 builds each batch config with `str.replace` on `'  # researchers: [Irene, Itziar]'`. A
non-matching `replace` returns the original **silently**, and a config with no `researchers:` key
ingests **all 1,508 in one go**. The `grep` afterwards catches it, but it is advisory — one line
makes it structural:

```python
out_text = t.replace('  # researchers: [Irene, Itziar]', '  researchers: [<WHO>]')
assert out_text != t, "researchers: substitution did not match — refusing to write a config that would ingest EVERYTHING"
```

### 5.2 §4's resume claim is too broad

Cross-source dedup is on `(timestamp, modality)` but the ingest unit is per-recon, and **142
scans in this set have more than one reconstruction (290 acqs)**. If a batch dies between two
recons of the same scan, the re-run skips the surviving sibling **silently** — it looks like a
clean resume. §4's "re-run the same command — dedup makes it resume, not duplicate" is true only
for single-recon scans.

§3.3's "NI row count up by exactly the batch size" catches the shortfall, so this is a wording fix
plus knowing to look. Reword §4 and add a line to §3.3 saying what a shortfall means.

### 5.3 `operator` is blank on every new row

The existing 132 NI rows carry `operator = irene`; these carry `''`. Either populate it in the
template or record it as a deliberate decision for historical data where the equipment operator is
not recoverable from the path. (`anatomical_entity` is blank on both old and new — consistent, not
an issue. `modalities_in_study` is `PT`/`CT` on the old rows and blank on the new; low priority,
but note it if the Finder groups on that column.)

### 5.4 The unanchored `LIKE` in `animal_db.py:247`

```python
"WHERE project_code LIKE %s LIMIT 1", (f"%{project_alias}",)
```

`'%101'` matches `AE-biomaGUNE-1317/PRO-AE-SS-101`. A lookup for protocol **101** therefore
resolves to project **1317**, and if an animal of that number exists there, the acquisition gets
**that animal's species, strain, sex, DOB and procedures** — succeeding, and reporting success.
That is the DTS24 failure shape: wrong data, no error.

It does not fire in this run (the affected folders parse no animal number), so it is latent, not
live. Fix it anyway — it is four lines, and the fallback exists for a good reason (`0219` and
`1521` have a NULL `projectAlias` and resolve only through `project_code`):

```python
            like = f"AE-biomaGUNE-{project_alias}"
            cur.execute(
                "SELECT id, project_code, projectAlias FROM projects "
                "WHERE project_code = %s OR project_code LIKE %s "
                "   OR project_code LIKE %s LIMIT 1",
                (like, like + "-%", like + "/%"),
            )
```

**Regression-checked:** against all 24 protocol codes referenced by production `subject_ids`,
**nothing stops resolving and nothing starts** — 22 resolve under both rules, 2 under neither.

⚠️ `tools/animal_db.py` is currently **identical to `main`** on this branch. Editing it makes this
the first shared-code change here beyond `config.py`/`ingest_raw.py`. Keep it to exactly these
lines so the merge stays trivial.

---

## 6. Before asking for the go-ahead again

1. Land §3.1–§3.4 and §5.1–§5.4.
2. Re-run discovery and confirm **1,508 / 673 / 131** and the recovery map in §2.
3. Confirm **4** new projects (`1122`, `0324`, `1024`, `0421`) and no others.
4. Sandbox-run `MJ` into a clean root; confirm the 66 recovered acquisitions land in
   `AE-biomaGUNE-0522` with resolving DB lookups.
5. Full suite green.
6. Update the runbook: new batch table, new smoke test, §4 resume wording, §3.3 shortfall note,
   §6 `--from-plan` → `--root`.
7. Update `ni_gnuclear_active_space_plan.md` §-2 and §0.6 — the 1,657/655 split there is
   superseded, and the "72% resolved a project code" figure was measuring path parsing, not
   correctness.

Then it is a go as far as this review is concerned.
