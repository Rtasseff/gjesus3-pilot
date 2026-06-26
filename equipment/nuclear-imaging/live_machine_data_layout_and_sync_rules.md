# Internal Nuclear Imaging — **live-machine** data layout & sync rules

**Status:** DRAFT — analysis of a real recursive listing of the Molecubes acquisition box's data
directory, done to design the **live-machine** NI ingest path (the "researcher syncs their own
folder to gjesus3" goal). The companion
[`internal_ni_data_handling_workflow_notes.md`](internal_ni_data_handling_workflow_notes.md)
covers the already-implemented **archive mode** (clean `.tgz` filenames pulled from
`\\cicmgsp02\gnuclear2$`); this document covers the **messier live data dir** that mode explicitly
defers ("Live-machine mode (future)").
**Last updated:** 2026-06-12 — **§3B/§3C/§7 reconciled to NI-LIVE-08:** `registry_subjects.csv` is
**one row per subject** (static record), **not** a `(acq_id, animal)` junction table (that shape was
vetoed); the scan→animal link is the packed `subject_ids` column, and per-(scan, animal)
`scan_position`/`age-at-acq` live in the sidecar `subjects:[…]` array. Earlier (2026-06-11): the
MFB-group scope/roster (§2A), the validated subject grammar + DB-as-validator (§3A), the
one-entry-per-animal multi-animal decision (§3B), the subject-data storage split (§3C), and the
two-program strategy (§7).
**Evidence:** `S:\gnuclear\2026\Jesus\Ryan\datapath.txt` — a full recursive path dump
(295,538 lines) of the Molecubes box data root `/Users/molecubes/Documents/volumes/remiW11/data/`.
All counts below are from that snapshot.

> **One-line takeaway.** On the live box there is exactly **one** reliable, machine-issued
> structural anchor: the acquisition folder named **`<YYYYMMDDhhmmss>_<MODALITY>`**. Everything
> *above* it (researcher / project / date / subject) is hand-typed, varies in depth, and is full of
> noise. So a non-technical sync script must **find acquisitions by that anchor (walk + match),
> never by fixed folder depth**, and derive the registry fields from the parent path + the files
> inside — not from a clean filename (the clean 7-field name only exists in *archive* mode, it is
> created by the archiving step, and is **not present on the live box**).

---

## 0. Build philosophy — MVP first, this has never run in practice

**This system has been used zero times in production.** The risk is designing an elaborate framework
for edge cases we've never actually hit. Standing rule for this work: **build the smallest thing that
makes the real data visible, look at it, then decide.** Concretely:

- The first artifact writes **nothing** — a discovery dry-run that prints what's on the box and what we
  *would* register (§7 Stage A1). Real examples beat speculation.
- Prefer the **simplest representation that loses no information** (e.g. one entry + animal list, §3B)
  over clever machinery (duplicate entries, splitting, forced standards) until real use demands it.
- Every "what about case X?" goes to **flag/queue** (the existing pending-recovery path), not to a new
  code branch. The mess is absorbed by a human-reviewed one-shot (§7 Program A), not by an
  ever-growing parser.

## 1. What the live data dir actually looks like

Recursive shape, dominant case (96.6% of acquisitions — see §3):

```
/Users/molecubes/Documents/volumes/remiW11/data/        <- the box's data root (the sync source lives under here)
└── <researcher>/                                        e.g.  irene, maria_g, jordi_starget
    └── <series_or_project>/                             e.g.  1025, 1207, 1123_tmcao, lu_177-dota-ptr-58
        └── <YYMMDD date>/                               e.g.  250527, 251002, 220728
            └── <subject / session label>/               e.g.  1025_m23-24, 0920-240-day3, 102_4h, 54
                └── <YYYYMMDDhhmmss>_<MODALITY>/          <- THE ACQUISITION (machine-issued name)  ★ anchor
                    ├── protocol.txt / protocol.xml / acqparams.xml / recontemplate.xml / acquisition.log
                    ├── recon_0/ … recon_N/              (per-reconstruction; CT: *_ISRA_*.dcm ; PET/SPECT: frame_<n>/iter_30/*.dcm)
                    ├── data.raw / eventdata_* / *.bin / *.amap / *.map   (raw + calibration — platform-owned)
                    └── monitoring.csv / sequence.csv / ACQSTATUS / DOWNLOADED / REMIDOWNLOADED  (status/logs)
```

**The inside of an acquisition folder is byte-for-byte the same shape we already ingest in archive
mode** (the `.tgz` is just a tarball of one of these folders). Verified against `irene/.../*_CT/`
(has `recon_0/*_ISRA_0.dcm`, `data.raw`, `protocol.txt`, `recon_2/ATTMAP.dcm`) and `maider_g/.../*_PET/`
(has `recon_0/frame_<n>/iter_30/*.dcm`, `eventdata_0.list`). **Consequence: the existing
slim-copy + metadata code applies to live mode unchanged** — see §6.

### Acquisition counts in the snapshot

| Modality | Acquisition folders |
|---|---|
| CT | 1570 |
| PET | 1250 |
| SPECT | 371 |
| **Total** | **3191** |

Every acquisition folder matches `^.../[0-9]{14}_(PET|CT|SPECT)$` — no exceptions, no other
modality token, no lowercase. The 14 digits are the machine timestamp `YYYYMMDDhhmmss`.

---

## 2. The reliable anchor vs. the unreliable everything-else

| Layer | Source | Reliability | Use it for… |
|---|---|---|---|
| `<YYYYMMDDhhmmss>_<MODALITY>` acq folder | **machine-issued** | **100% consistent** | Discovery (what *is* an acquisition), modality, candidate acq datetime |
| `recon_N/…*.dcm` inside | machine-issued | consistent (per-modality shape) | the actual primary images (already handled) |
| `protocol.txt` / `*.xml` / DICOM headers inside | machine-issued | consistent (one known bug — PI field, §5) | metadata enrichment, date corroboration, subject cross-check |
| `<subject/session label>` folder | hand-typed | free-form, no fixed shape | a label only (animal id + timepoint); never parse rigidly |
| `<YYMMDD date>` folder | hand-typed | 95.5% match machine date, 4.5% disagree | a label / weak corroboration only |
| `<series_or_project>` folder | hand-typed | mixes funded-project id, animal-protocol id, free text | a label; map with operator confirmation |
| `<researcher>` top folder | hand-typed | often researcher, sometimes researcher+project, has typo-variants | the sync scope + a *candidate* user/operator |

**Design rule that falls out of this table:** anchor on row 1, trust rows 1–3, treat rows 4–7 as
*free-form context labels* the operator confirms — never as a positional parse. This is the same
"filename/path chunks are free-form labels" principle already adopted for the other instruments.

---

## 2A. Scope = Jesus's group only — name-driven sync + roster allow-list

**Most of the box is *not* our data.** The high-volume folders (`jordi_starget` 1400, `maria_g` 415,
`jorge` 197, `jordi_novartis` 175, `mariana` 102, `esther` 95, `balbino` 94, …) belong to other
groups / CRO-sponsored work (starget, novartis, oncodesign = external sponsors). The MFB
(Jesus Ruiz-Cabello) group's NI data is a **small subset**. So the sync tool must be **scoped to an
explicit roster**, not "sync everything under `/data/`."

**Name-driven sync (answers "can we sync on command if the user gives their name?"): yes.** The
researcher gives their name → the tool resolves it to their box folder via the roster table below →
scopes to `/data/<folder>` → walks the anchor (§4-R2) → applies the most-common pattern as the happy
path (§3A) → previews → ingests. Because resolution goes through the roster, every out-of-scope
folder is excluded for free.

**Not all group members do NI** — so most roster members are *expected* to be absent from the box;
a "not seen" row is normal, not a mapping failure. Only the handful who actually run nuclear scans
need a confirmed folder.

**MFB group roster → box folder** (group = *Molecular and Functional Biomarkers*, PI Jesus
Ruiz-Cabello; source: cicbiomagune.es group page, fetched 2026-06-11). Folder column =
the `/data/<folder>` slug; ✓ = confirmed present with acquisitions in the snapshot.

| Roster member | Box folder | In snapshot |
|---|---|---|
| Irene Fernández Folgueral | `irene` | ✓ 129 acqs |
| Claudia B. Miranda Pérez de Alejo | `claudia` | ✓ 120 acqs |
| Ermal Ismalaj | `ermal` | ✓ 10 acqs |
| Aitor Zubillaga Unsain | `aitor` | ✓ 1 acq (a phantom) |
| Itziar Souto Riobo | `itziar` | ✓ 1 acq |
| Carlotta Scarponi | `carlotta` | ✓ 1 acq |
| Laura Fernández Méndez | `laura` | folder exists, 0 acqs |
| Susana Carregal Romero | `susana`? | not seen — confirm |
| Iraia Sánchez Arregui | `iraia`? | not seen — confirm |
| Adrián E. Lluveras Sires | `adrian`? | not seen — confirm |
| Ekine Olaizola Bárcena | `ekine`? | not seen — confirm |
| Tania M. Hernández Cruz | `tania`? | not seen — confirm |
| Elena González Lozano | `elena`? / `ely`? | `ely` exists — **ambiguous, confirm** |
| Marta Beraza Cabrerizo | `marta`? | not seen — confirm |
| Susana / others (TBD) | — | — |
| Jesus Ruiz-Cabello (PI) | `jrc`? / `mjesus`? | **ambiguous** — likely doesn't scan; confirm |
| Ryan A. Tasseff | — | Data Office, not a scanner user |
| Ainhize Urkola Arsuaga | — | Cell Observer / LSM 900, **not NI** |

**Explicitly out of scope** (not MFB members): all `jordi_*` / `jrc`-as-Jordi, `maria_g`/`maria`/
`mariag`, `jorge`, `mariana`, `esther`, `balbino`, `jinhai`, `irati`, `grace`, `bao`, `marina`,
`oscar`, `cristina`, `aitana`, `acsah`, `maider`/`maider_g`, `unai` (platform manager), `libe`,
`ander`, `kepa`, `karel_deprez` (vendor), `raquel`, plus the system folders in §3(b).

> **Build note:** keep the roster→folder map as a small editable table (config), not hard-coded —
> people join/leave and the `ely`/`jrc`/`mjesus` and "not seen" rows need the user's confirmation
> before they go live. New members just add a row.

---

## 3. The messiness, catalogued (what the script must survive)

**(a) Variable depth — the anchor is not at a fixed level.** Segments between `/data/` and the
acq folder:

| Segments after `/data/` | # acqs | Example |
|---|---|---|
| 5 (the norm) | 3081 | `irene/1025/250527/1025_m23-24/20260528103903_CT` |
| 6 (extra hand-made level) | 109 | `irene/1207/250408/0522_143/new recon/20250408172344_PET` · `jordi_starget/lu_177-dota-ptr-58/220728/220606_4h_rep/54/20220606155516_CT` |
| 4 (a level skipped) | 1 | `mariana/979_theradnostics/31/20241107132950_PET` |

The depth-6 cases are researcher-created subfolders (`new recon`, `reconstructed in cube`) or an
extra nested date level. **→ Discovery MUST be a recursive walk that matches the anchor regex, not
`glob` at a fixed depth.**

**(b) Top-level `/data/` is full of non-researcher noise** (siblings of the researcher folders).
A per-researcher sync (point at `/data/<me>`) sidesteps it, but a "sync everything" tool must
exclude:
- `recon_0` … `recon_100` — **scratch reconstruction working dirs** the recon engine drops at data root.
- `*.xml` calibration/param files at data root: `gpmouse_calibrationParameters*.xml`,
  `gprat_*`, `hisensmouse_*`, `reconstructionParameters{QCMTF,Bert,BertBone,ATTMAP,UHR,LR,HR}.xml`.
- QC / maintenance / vendor / test: `qc`, `qc_pet`, `maintenance2023`, `molecubes`, `reports`,
  `spectxmlold`, `ria_test`, `*_test` (e.g. `jordi_test`), `PostProcessing.py`, `qscale.db`,
  `xrayserver.ini`.

**(c) Top-level folder ≠ clean researcher identity.** It conflates researcher and project, and has
typo/variant duplicates:
- Same person, many project folders: `jordi`, `jordi_starget`, `jordi_novartis`, `jordi_oncodesign`,
  `jordi_frank`, `jordi_mayoralas`, `jordi-starget`, `jrc`.
- Variant spellings of one identity: `aitana-irati` vs `aitana_irati`; `jordi-starget` vs
  `jordi_starget`; `maria_g` vs `maria` vs `mariag`; `ane` vs `ane_g`; `unai` vs `unain` vs
  `unai_heras`; `maider` vs `maider_g`.

  → The script should **not** trust the folder name as the canonical researcher. Capture it as a
  label and let the operator confirm/normalise (a small mapping table or a prompt). Top researchers
  by volume in this snapshot: `jordi_starget` (1400), `maria_g` (415), `jorge` (197),
  `jordi_novartis` (175), `irene` (129), `claudia` (120), `mariana` (102), `esther` (95),
  `balbino` (94).

**(d) The date folder can lie; the machine clock can too.** Of 2956 acquisitions with a 6-digit
date folder, **2824 (95.5%) match** the acq-folder machine date and **132 (4.5%) disagree**; another
125 acqs have a non-date segment there. The disagreements cluster in `irene/1025/` where the
**scanner clock was set a year ahead** (machine `20260528`, folder `250527`). So *neither* source is
unconditionally authoritative.
→ Rule (§4-R5): take the **machine timestamp** as the primary acquisition datetime, **corroborate
against the DICOM `StudyDate`/`AcquisitionDate` header**, and when the date folder disagrees by more
than a day, **flag the acquisition for operator confirmation** rather than silently picking one.

**(e) Spaces and punctuation in hand-made levels** (`new recon`, `reconstructed in cube`,
`220606_4h_rep`). The walker and any path handling must be space-safe and not assume `_`/`-`
delimiters mean anything.

---

## 3A. Subject parsing — the critical `(project, animal)` → animal-facility-DB link

**This is the part that must be right** (user: "that subject is critical to get right"). The subject
folder carries the **`(project_code, animal_id)`** pair that joins to the animal-facility database to
fill the `subject:` metadata block (same `(project, animal_code)` join the Phase-3 enrichment writer
already uses — see the `animal_facility_db_metadata` design / `tools/ingest/enrichment.py`).

### Validated grammar (from real MFB-group subject folders in the snapshot)

```
<subject_label> = [<project code> <sep>] <animal-list> [<sep> <timepoint>]   |   phantom<...>

  project code : 3–4 digits (0324, 0522, 0525, 1025, 1320, 1622, 979). OFTEN OMITTED in the
                 subject folder; then recover from the PARENT series folder's leading digits
                 (e.g. parent "0622_WELAB" -> 0622; "1622_idif_florbetaben5" -> 1622).
  sep          : "_" OR "-"  — varies BY PERSON (irene uses "_", claudia uses "-"). Accept both.
  animal-list  : ONE OR MORE animal ids. Multiple = ONE acquisition imaging MULTIPLE animals.
  animal id    : [species prefix] + short number.
                 prefix is INCONSISTENT: "m" (mouse, common) | "r" (RAT, ermal) | NONE (bare number).
                 -> the parser MUST NOT require "m".
  timepoint    : <N>h  (2h, 4h, 1h — fast/dynamic, same animal multiple hours same day)
                 or dNN / dayNN (day marker).
  phantom      : "phantom..." — QC, NOT an animal. Skip the DB link entirely.
```

### Real examples (MFB group only) and how each parses

| Subject folder | Parent series | → project | → animals | → timepoint | Note |
|---|---|---|---|---|---|
| `0525_m25` (irene) | `0525` | 0525 | [m25] | — | the clean happy path |
| `0324_m59_m60` (irene) | `0324` | 0324 | [m59, m60] | — | **2 animals, one acq**, `_`-sep |
| `0324_m59_m60_2h` (irene) | `0324` | 0324 | [m59, m60] | 2h | 2 animals + hour |
| `0522_120` (irene) | `1207` | 0522 | [120] | — | **no `m` prefix**; project ≠ parent series |
| `1015_m10-15` (irene) | `1025` | 1015 | [m10 … m15]? | — | **ambiguous: range or pair?** flag |
| `0324_r20` (ermal) | `0324` | 0324 | [r20] | — | **`r` = rat**, not mouse |
| `64` (claudia) | `0622_WELAB` | 0622 (from parent) | [64] | — | **bare number; project recovered from parent** |
| `65-66` (claudia) | `0622_WELAB` | 0622 (from parent) | [65, 66] | — | 2 animals, `-`-sep, no prefix |
| `11-12-13` (claudia) | `1622_idif_florbetaben5` | 1622 (from parent) | [11,12,13] | — | **3 animals** |
| `0124_2-4-5-6` (claudia) | `979_0124_fdg4` | 0124 | [2,4,5,6] | — | **4 animals**, non-contiguous |
| `6-8-9` (claudia) | `1622_…` | 1622 | [6,8,9] | — | non-contiguous → explicit list, **not a range** |
| `phantom5_6` (aitor) | `0421` | — | — | — | phantom → no DB link |
| `12-1314` (claudia) | `0323_3tgad_fdg` | 0323 | [12,13,14]? | — | **typo** (missing sep) → flag |

### Hard truths this forces into the design

1. **One scan can image up to 4 animals.** The machine **physically holds ≤ 4 mice** (confirmed),
   so the animal-list is **1–4**, never more — `0124_2-4-5-6` (four) is the max case. **At raw
   ingest, one scan = one acquisition entry that records its 1–4 animals as a list** (Model 1, §3B);
   the scan→animal link is the packed `subject_ids` list on that one row, and the NAS subjects table
   (§3C) is one row **per animal** (not per scan). Per-animal *image* splitting is a deferred,
   optional derivative — not part of the sync.
2. **The animal prefix can't be required.** `m` (mouse), `r` (rat), or bare. Parse the prefix when
   present (it sets species), default-flag when absent.
3. **The project code is recovered from two places** (subject prefix first; else parent series
   leading digits) and the two can *conflict* (parent `1025` but subject `1015_…`). On conflict →
   flag, don't pick. **Implemented in `ni_live_discover.py`:** only a *typo-shaped near-miss*
   (same length, one differing digit — `1015` vs `1025`, `0324` vs `0314`) raises
   `project-conflict:<parent>`; a *wholesale*-different parent is **not** flagged, because the funded
   series id routinely differs from the animal-protocol code (§5) and the subject prefix is
   authoritative there (e.g. `0522_120` under series `1207`). On the snapshot this flags exactly two
   clusters (10 `1015`-vs-`1025` + 2 `0324`-vs-`0314` acqs) and nothing by-design. The tool still
   keeps the subject prefix and does **not** decide which wins — NI-LIVE-09.
4. **Ranges vs lists are ambiguous.** `m6-7` is obviously a pair, but `m10-15` could be a 6-animal
   range; `6-8-9` proves dashes are explicit lists, not ranges. Treat consecutive 2-tuples as a pair,
   flag anything wider for confirmation.

### The robust rule: **the facility DB is the validator, not the folder.**

**Researchers admit to mislabeling** — so the folder text is a *hint*, never the truth. Parse →
produce candidate `(project, animal)` pairs (expanded for multi-animal) → **look each up in the
animal-facility DB**:

- **All pairs hit** → accept, fill the minimal convenience subset (§3C), done (the happy path, e.g.
  Irene's `0525_m25`).
- **Any pair misses / is ambiguous / project conflicts / no prefix / phantom / typo / mislabel** →
  **flag and queue** for the researcher/Data-Office to confirm, via the existing non-blocking
  `pending_subject_metadata.csv` + `recover_subject_metadata.py` path. Ingest still succeeds; the
  subject link is back-filled. **Never silently mis-link an animal.**

**A DB miss at sync time is EXPECTED, not an error.** Facility records are entered after a time delay;
an animal is *usually* already there (it's registered at purchase) but **may not be yet**, or the
specific session record may lag. So the live tool must treat "not found" as a normal queue-for-later
outcome, never a hard failure — the back-fill (`recover_subject_metadata.py`) re-tries once the DB
catches up. (This is also why the credential must be **local to the sync machine** — see §5.)

So "sync on command, most common pattern" works automatically for the clean majority and *degrades to
a prompt/queue* for the messy minority and the DB-lag cases — the only safe behaviour when the subject
is critical.

---

## 3B. Multi-animal scan → ONE entry, animals listed (Model 1) — splitting deferred

**Reconsidered 2026-06-11 (user pushback + web evidence — avoid over-engineering).** An earlier draft
proposed N duplicate acquisition entries (one per animal) hard-linked to the same combined image. That
was over-engineered: it manufactures per-animal *entries* without per-animal *data*. The field doesn't
do this (see below). **Superseded by Model 1.**

**What the literature does** (so we copy practice, not invent it):
- DICOM is strictly one-patient-per-study (Patient→Study→Series→Instance) — a combined scan has no
  native "multiple subjects" slot.
- The published preclinical-DICOM practice for multi-mouse hotels keeps the **one combined scan**, and
  when per-animal data is required runs an **image-splitting routine** that crops each mouse, mints
  **new UIDs**, and stores a **reference back to the original** dataset. (PMC7934703; JNM 61(2):292.)
- → Splitting is a **downstream/derivative** step done *when an analysis needs it*, not at raw ingest.

**Decision — at raw ingest use Model 1:**
- **1 scan = 1 acquisition row = 1 ACQ-ID** (honest 1:1 with the real machine event; combined
  reconstruction kept whole). DICOMs stored once, **no duplication, no per-animal hard-link fan-out**.
- The scan's **1–4 animals are recorded as a list** in the acquisition row's packed **`subject_ids`**
  column (`;`-joined facility ids, always-a-list). **That column is where the scan→animal link lives**
  — the one acquisition row points at its 1–4 animals. The **NAS subjects table**
  (`registry_subjects.csv`, §3C) is **one row per animal** (the static record), **NOT** one row per
  scan-animal pair. The acquisition×animal relationship is fully recoverable by joining `subject_ids`
  against that table, so **no junction/mapping table is built now** (NI-LIVE-08 — a junction is a
  deferred query-layer option, explicitly vetoed for now).
- **Position** (which mouse in which bed slot) and **age-at-acquisition** are *per-(scan, animal)*
  facts, so they live in the per-acquisition **sidecar `subjects:[…]` array** (one element per animal
  in that scan) — **not** in the one-row-per-animal subjects table. Recorded when known; historical
  data → record the animal, flag position unknown. (Forcing a position convention going forward is a
  Program-B standard item, not an ingest blocker.)

**Per-animal image splitting (Model 2) — DEFERRED, optional, derivative.** If/when an analysis needs
separate per-mouse volumes: a project-workspace step crops each animal, mints new UIDs, and references
the original ACQ-ID. We do **not** build this for the sync; we just keep the combined scan + the animal
list so the split is possible later. Tracked as future-work, not Stage-A/B scope.

**Consequences for the rules:** idempotency key (R7) stays `(machine_timestamp, modality)` — one entry
per scan, no per-animal collisions. `link_filename`/ACQ-ID are per-scan as today. Single- and
multi-animal scans are the **same code path** (a list of length 1–4).

*Open: position-numbering convention going forward — NI-LIVE-11 (§8). The shared-FOV question (NI-LIVE-10)
now only matters if/when we build the deferred split.*

---

## 3C. Where subject/sample data lives — separate updatable table + minimal sidecar

**Design note to carry forward (user, 2026-06-11 — "something to think about"):** subject/sample
data is **mutable** (the facility DB fills in after a delay; sex/age/strain can be corrected), but
`/raw/` sidecars are **immutable**. So do **not** dump the full subject record into the JSON sidecar.

- **DECIDED (user, 2026-06-11; shape settled 2026-06-12 — NI-LIVE-08): our own NAS subjects table,
  one row per SUBJECT.** Full subject data → a separate, updatable registry on the NAS
  (`registry_subjects.csv`), **keyed by `facility_id` — exactly one row per animal**, holding the
  *static* record (`facility_id`, `project_alias`, `animal_code`, `species`, `sex`, `strain`,
  `date_of_birth`, + provenance). An animal seen in N scans still has **one** row — the writer is an
  **upsert by `facility_id`, never append-per-scan**. This is **NOT** a `(acq_id, animal)` mapping
  table — that shape was explicitly **vetoed** (NI-LIVE-08); the scan→animal link is the packed
  `subject_ids` column on the acquisition row (§3B), and the acq×animal relationship is recovered by
  joining the two. Back-filled/corrected over time by the recovery tool; self-contained on the NAS so
  it survives DB outages. Natural fit with the `subject_ids` column and the existing
  `pending_subject_metadata.csv` → `recover_subject_metadata.py` flow.
- **Sidecar holds only a minimal convenience subset** — enough to read an acquisition standalone: the
  `(project, animal, facility_id)` key, cached `species`/`sex`, plus the *per-(scan, animal)* facts
  that have **no home** in the one-row-per-animal table — **`scan_position` and `age-at-acquisition`** —
  as a small `subjects:[…]` array (one element per animal in the scan). Everything *static* lives in
  the updatable subjects table. (The sidecar `subjects:[…]` JSON shape is documented in `08_METADATA`
  at the live-ingest build stage.)
- This also respects the existing **metadata-location split** (immutable acquisition-level in
  `/raw/`, mutable study/subject-level elsewhere) and keeps the immutable sidecar from going stale
  when the DB is later corrected.

*Resolved (NI-LIVE-08/12, 2026-06-12): our own NAS table, **one row per subject** (static record);
per-(scan, animal) `scan_position`/`age-at-acq` + the scan→animal link live with the acquisition
(`subject_ids` + sidecar `subjects:[…]`), not in the subjects table; **no junction table**. The exact
sidecar `subjects:[…]` JSON shape is the only open detail — settled at the live-ingest build stage.*

### Decided sync-execution context (user, 2026-06-11)

- **The sync runs on the Mac/Molecubes box (push).** Implication: the read-only DB credential
  (`.my.cnf` / `GJESUS3_MYCNF`) must be installed **on the Mac**, on-network. And **hard-link
  behaviour on the Mac CIFS mount is unverified** → the `os.link` diagnostic
  (`correction_pass_handoff.md` item 11 / R10) is now a **hard prerequisite** before any real ingest;
  if `os.link` fails there, fall back to running the *ingest* from a Windows box (hard-links proven)
  while the Mac only stages/pushes, or to the `.lnk` path. This is the single biggest feasibility
  risk to confirm early.

---

## 4. Sync / ingest rules for the live-machine script

These are the rules the non-technical "sync my folder" tool should implement. They deliberately
lean on what already exists (§6) and add only the live-mode discovery + field-derivation layer.

- **R1 — Scope = one MFB-group researcher folder, resolved by name.** The researcher gives their
  name; the tool maps it to `/data/<folder>` via the **roster allow-list (§2A)** and scopes there.
  Only MFB-group members resolve — this is what excludes the high-volume out-of-scope folders
  (`jordi_*`, `maria_g`, `jorge`, …). Never crawl all of `/data/` by default (pulls in §3(b) noise
  and other groups' data).

- **R2 — Discover acquisitions by the anchor, recursively.** Walk the scoped subtree and select
  every directory whose **basename matches `^[0-9]{14}_(PET|CT|SPECT|OI)$`**. That directory *is*
  one acquisition. Do not assume a fixed depth. Stop descending once an anchor is hit (its children
  are `recon_N/…`, not more acquisitions).

- **R3 — Exclude noise explicitly.** Skip any path element in the §3(b) deny-list (`recon_<N>` at
  data root, `qc*`, `maintenance*`, `molecubes`, `reports`, `*_test`, `ria_test`, `spectxmlold`,
  and the `*.xml`/`.db`/`.ini`/`.py` data-root files). Because acquisitions are matched positively
  by R2, noise is excluded for free *inside* a researcher folder too (only real acq folders match).

- **R4 — Field derivation: machine first, path-chunks as labels, operator confirms.**
  - From the **anchor name**: `modality`, `acq_datetime_full` (= the 14 digits), `acq_date`.
  - From the **subject folder**: parse `(project_code, animal_id[…], timepoint)` per the **§3A
    grammar** (multi-animal → a *list* of subjects; species prefix m/r/none; project recovered from
    subject-prefix or parent-leading-digits). **Validate every `(project, animal)` against the
    facility DB (§3A)** — accept on hit, flag+queue on miss/ambiguity. Never silently mis-link.
  - From the rest of the **relative path** (variable length): capture each segment as a free-form
    context label — `discovered.researcher_folder`, `discovered.series_or_project`,
    `discovered.subject_label`, plus the full relpath — and the `researcher` from the roster (§2A),
    not by blind position (depth varies — §3(a)/(c)).
  - From **inside the files** (already parsed by `ni_metadata.py`): `protocol.txt`, the XMLs, and
    DICOM headers fill/cross-check the rest. **Do not** read PI from `protocol.txt` (§5).

- **R5 — Acquisition date: machine timestamp, DICOM-corroborated, mismatch-flagged.** Primary =
  anchor timestamp. Cross-check the recon DICOM `StudyDate`/`AcquisitionDate`. If the hand-typed
  date folder disagrees by >1 day, record both and **flag for confirmation** (don't silently
  resolve — the `irene/1025` clock-skew cohort is exactly this case).

- **R6 — Copy the slim surface only (unchanged from archive mode).** Keep DICOMs (`recon<X>.dcm` /
  `recon<X>_frame<Y>.dcm` / `recon<X>_frameMULTI.dcm`) into `<ACQ-ID>.data/`; parse
  `protocol.txt` + XMLs + DICOM headers into `metadata.json.ni`; **drop** `data.raw`, `eventdata_*`,
  `*.bin`, `*.amap`, calibration, status, and per-recon non-DICOM. The platform archive on
  `\\cicmgsp02\gnuclear2$` remains the deep-time store for the dropped bytes. (~6 GB source →
  a few MB on gjesus3.) This is exactly `copy_ni_acquisition()` today.

- **R7 — Idempotent re-sync.** A researcher will re-run the tool after each session and expect only
  *new* acquisitions to land. Dedupe on a stable key — the natural one is
  `(machine timestamp, modality)` (globally unique per acquisition) and/or the source relpath.
  Re-running must skip already-ingested acquisitions with **no** new ACQ-IDs and **no** duplicate
  rows. *(Note: this is the same idempotency concern flagged for archive ingest in
  `tasks/correction_pass_handoff.md` item (4) — the live-mode key must be chosen so re-sync is a
  true no-op.)*

- **R8 — Don't delete the source.** The live box / platform owns the originals; sync **copies**.
  No `--delete-source` on the live path.

- **R9 — Empty/partial acquisition = fail loud, write nothing.** If an anchor folder has **no**
  primary DICOM (e.g. an interrupted/aborted scan, a `recon_N` still in progress, or a status file
  set but no recon), skip it with a clear per-folder message; do not register an empty acquisition.
  (Same class as `correction_pass_handoff.md` item (6).)

- **R10 — Read-only, on-network, no laptops.** Mac-fronted box; hard-link behaviour on the
  Mac/Linux CIFS mount is **unverified** — see the `os.link` diagnostic in
  `correction_pass_handoff.md` item (11). If hard-links fail on that mount, the project linking
  step needs the Windows-remote or `.lnk` fallback. Flag, don't assume.

---

## 5. Known data-quality gotchas (carried over + newly confirmed)

- **`protocol.txt` "Principal Investigator" holds the *operator username*, not the PI** — a Molecubes
  labelling bug already documented for archive mode. The live script must **not** populate PI from
  it; leave PI empty (recover later) and keep the raw value verbatim in `ni._raw_metadata`.
- **PI is a *path* fact, not a file fact.** In archive mode PI = the `<PI first name>` directory on
  the SMB share. On the live box the data root has **no** PI level (it goes straight
  `data/<researcher>/…`), so the live tool cannot infer PI from the path either — PI comes from
  operator entry or a researcher→PI lookup. (For this group it is Jesus by construction.)
- **`series_id` (funded-project id) ≠ `short_project` (animal-protocol id).** Same numbers
  sometimes, different others (the archive `1207` series uses animal protocol `0424`). On the live
  box these live in the hand-typed `<series_or_project>`/`<subject>` levels and are **not**
  separable by position — operator confirmation resolves which is which.
- **Scanner clock skew is real** (the `irene/1025` 2026-vs-2025 cohort). → R5.
- **DB credential must live on the sync machine.** The DB validation (§3A) runs *where the sync runs*,
  so the read-only `.my.cnf` (or `GJESUS3_MYCNF` path) must be installed on **that** machine, and the
  machine must be on-network/VPN to reach the facility DB. If it isn't, every animal simply queues for
  back-fill (non-blocking) — the sync still completes. (Same credential mechanism as
  `correction_pass_handoff.md` item (10); install procedure belongs in `tools/operator/README.md`.)
- **DB record may be absent/wrong at sync time** (entry delay). Covered in §3A — treat as a normal
  queue outcome, not a failure.

---

## 6. How this reuses existing tooling (build delta is small)

| Need | Already exists | Live-mode delta |
|---|---|---|
| Copy slim surface (DICOM-only) | `tools/ingest_raw.py::copy_ni_acquisition()` | none — same inner structure |
| Parse `protocol.txt` + XML + DICOM headers → `ni:` sidecar | `tools/ingest/ni_metadata.py` | none |
| Per-instrument config shape, `link_filename`, modality→instrument | `tools/templates/instruments/molecubes_ni.yaml` | a **live** variant (`molecubes_ni_live.yaml`): source = folder tree, **no** archive-name regex; fields come from path-walk + prompt |
| Operator front-end (dead-simple script) | `tools/operator/ni_ingest.py` + `metadata_prompt.py` | add the **recursive anchor-discovery + per-acq confirm** loop; multi-acquisition per run |
| Archive extraction | `tools/extract_ni_archives.py` | **not needed** live (folder is already a folder — the `.tgz`/`--strip-components=6` step disappears) |

**So the genuinely new work for live mode is:** (1) the recursive anchor walk + noise exclusion
(R2/R3), (2) deriving registry fields from a variable-depth path + operator confirmation instead of
from a clean filename (R4), (3) the date tie-break/flag (R5), and (4) the idempotent re-sync key
(R7). The copy + metadata internals are done.

---

## 7. Strategy — two programs: a one-time vetted migration, then a simple standard sync

> **UPDATE 2026-06-12 — reconciled with merged `origin/main` (correction pass + NI-LIVE-08); Step 1 is BUILT + validated.**
>
> **Now DONE upstream (reuse, don't rebuild):** registry lock + durable ACQ-ID reservation
> (`tools/ingest/locking.py`), BOM/newline-safe CSV appends (`csv_safe.py`), archive re-run
> idempotency, crash-orphan rollback (registry append = commit point), empty-folder fail-loud,
> cross-drive relpath guard, the `os.link` diagnostic (`tools/diagnostics/test_oslink.py`), and the
> single-animal DB-lookup + `pending_subject_metadata.csv` recovery chain. These cover R7/R8/R9/R10
> and the DB-as-validator path — the remaining build is much smaller than this section first assumed.
>
> **Now DECIDED (NI-LIVE-08, 2026-06-12):** packed `subject_ids` (`;`-joined, always-a-list) replaces
> singular `subject_id`; a TRUE one-row-per-subject `registry_subjects.csv`; minimal sidecar
> `subjects:[…]`; **no** mapping/junction table; query layer deferred. Steer: *stop expanding the
> model; capture the small group's data; then build query.* **The `subject_id`→`subject_ids` rename is
> ✅ DONE 2026-06-12** (code + sandbox header; rename-aware migrator). Still greenfield: the subjects-table
> writer, the multi-animal list assembly (glue), `molecubes_ni_live.yaml`.
>
> **Step 1 BUILT: `tools/ni_live_discover.py`** (read-only discovery dry-run). Validated against the
> snapshot — **254/262 (97%) of MFB NI scans parse to a DB-keyable `(project, animal)`**; only **7**
> (ermal bare-number with no recoverable project) genuinely need human input, plus 8 possible-range to
> eyeball. Most flags are informational (species deferred to the DB: 160; project recovered from the
> parent folder: 93). **102 of 262 scans image >1 animal** (cap 4). Rats (`r20`) parse correctly.
>
> **Step-1 review (2026-06-12, data-office):** independently re-ran against the snapshot — the numbers
> reproduce exactly. Added the typo-shaped **`project-conflict:<parent>`** flag (§3A #3) so the 10
> `1015`-vs-`1025` + 2 `0324`-vs-`0314` near-misses no longer pass as confident, unflagged keys (they
> were silently picking the subject prefix); wholesale series≠protocol differences stay unflagged by
> design. Added **`tools/test_ni_live_discover.py`** (30 checks, green) pinning the §3A example table,
> the conflict flag, and the `facility_id`↔`animal_db.compose_subject_id` contract. Parsing/headline
> counts are unchanged — the flag only adds review signal. NI-LIVE-09's *resolution* (which code wins)
> is still open for Unai.
>
> **Leaner plan:** **Gate 0** — run `test_oslink.py` on the Mac (push-from-Mac feasibility) + confirm
> host/layout with Unai. **Step 1** — `ni_live_discover.py` (done; review the table, `--csv` for full).
> **Step 2** — `molecubes_ni_live.yaml` + multi-animal wiring (animal list → per-animal DB lookup →
> packed `subject_ids` + `registry_subjects.csv` rows + sidecar array). The `subject_id`→`subject_ids`
> rename is ✅ DONE (2026-06-12). **Step 3** — vetted one-shot to `J:\gjesus3-sandbox`. **PARKED:** Program B
> forward standard, the mapping table, per-animal splitting, the query layer.
>
> **Path forward (2026-06-12 — proposed division of labor; Step 1 is DONE + tested + reviewed by both).**
> The remaining pre-ingest work is two external gates and a clean split of Step 2 so we don't both edit
> the shared registry code:
> - **Gate 0 (external, the real unblock — on the user):** run `tools/diagnostics/test_oslink.py` on the
>   Mac (push-from-Mac hard-link feasibility) and confirm host/layout + the forward standard with Unai.
>   Gates a *real* ingest (Step 3), not Step-2 coding.
> - **Two decisions Step 2 needs (small):** **NI-LIVE-09 resolution** — on a `project-conflict` flag,
>   which code wins? (proposed: keep the subject prefix per §3A but route the 12 flagged acqs through the
>   `pending_subject_metadata.csv` review queue before the DB key is trusted — "flag, don't guess");
>   **NI-LIVE-07** — confirm "dashes are explicit lists; flag gap>1 (`possible-range`)" as the rule.
> - **Step 2 split:** the `subject_id`→`subject_ids` column rename in `registry.py`/`resolver.py` is
>   ✅ DONE (2026-06-12, data office); the **designer still owns the rest of the schema reshape** — the
>   multi-animal list-packing in `build_row` + the `registry_subjects.csv` writer; **the live-NI glue is
>   separable** — `molecubes_ni_live.yaml` + the
>   discovery→ingest wiring that assembles the 1–4 animal list, calls the existing per-animal
>   `animal_db` lookup, and emits the packed `subject_ids` + sidecar `subjects:[…]`. Each stays in its
>   lane → no conflicts on shared registry code. Sequence: decisions → designer lands the schema →
>   live-NI glue wires onto it → Step 3 one-shot once Gate 0 clears.


**DECIDED direction (user, 2026-06-11):** split the problem in two so the *ongoing* tool stays simple.

> **Program A — one-time historical migration (messy → clean).** A **prevetted, human-in-the-loop**
> crawl of the existing in-scope MFB folders on the box. It does the hard parsing (§3A grammar, project
> recovery, multi-animal expansion) **once**, emits a **review table** for a human to eyeball/correct
> *before* anything commits, then ingests with the §3B one-entry-per-animal shape. It does **not** need
> to be a clean, reusable, bulletproof parser — it's a bounded, vetted, one-shot. Mislabels and DB
> misses are resolved interactively / queued here.
>
> **Program B — forward standard sync (clean → trivial).** After the one-shot, **force a naming
> standard at acquisition** so new data is unambiguous (project, animal(s), position, modality, date).
> Then the ongoing "sync my folder" tool is a thin, dependable: *resolve name (roster) → walk anchor →
> parse the **known** standard → dry-run preview → DB-validate → ingest*. Minimal parsing, because the
> input is now regular.

**Recommendation (asked for):** this is the right call, with one caveat — **Program B still needs the
dry-run + DB-validate + flag-on-miss path**, because two messiness sources survive *any* naming
standard: (1) humans still mislabel, and (2) the facility DB still lags (§3A/§5). So "force a standard"
shrinks the parser to near-nothing but does **not** remove the validate/flag/queue safety net. Also:
the bounded historical set is quasi-production (slated for the post-exhibition purge/reload anyway), so
a hand-vetted one-shot carries low risk and high clarity — exactly the right place to absorb the mess.

### Sequencing

- **Stage 0 — lock the convention with Unai** (prerequisite, GAP): canonical layout for *all* NI users
  and *both* systems (Molecubes + MILabs VECTor)? push vs pull (where does the sync run → where the
  `.my.cnf` goes)? the forward acquisition standard itself (who enforces it — researcher-typed folder
  vs platform template)? *Do not invent answers.*
- **Stage A1 — discovery-only dry run (no writes):** walk a scoped MFB folder, emit the review table
  (per acquisition: researcher, project, animal(s) expanded, position?, date + mismatch flag, modality,
  timestamp, DB hit/miss per animal). Validate against `datapath.txt` (irene = cleanest start). Highest
  value, zero risk.
- **Stage A2 — vetted one-shot ingest to the sandbox:** human reviews/edits the table → ingest with
  §3B (one entry **per scan**, animals recorded as a list in `subject_ids`; the subjects table holds
  one row **per animal**) + §3C (minimal sidecar, subjects table) → verify idempotent re-run (R7), empty-folder guard
  (R9), `os.link` on the real mount (R10).
- **Stage B — forward standard + simple sync:** define + document the acquisition naming standard;
  ship the thin "sync my folder" front-end (point-at-folder → preview → dry-run → live) reusing
  `copy_ni_acquisition()` + `ni_metadata.py`; document in `tools/operator/README.md`.

### What the program looks like (component sketch — both programs share most of it)

```
ni_live_sync/
  roster.{yaml|csv}        §2A  name → /data/<folder> allow-list (editable; MFB only)
  discover.py              §4-R2/R3  recursive anchor walk + noise exclusion -> [acq folders]
  parse_subject.py         §3A  subject -> (project, [animals], timepoint, phantom?) ; A=messy/vetted, B=standard/strict
  animal_db.py (exists)    §3A  (project, animal) -> facility record ; MISS = queue, not fail
  plan.py                  build the per-SCAN entry + 1–4 animal list (§3B) + date tie-break (R5)
  review_table.{csv|tui}   Program A: human vets BEFORE commit ; Program B: dry-run preview
  ingest  (reuses ingest_raw.copy_ni_acquisition + ni_metadata + standard project hard-link, one per scan)
  subjects_table writer    §3C  UPSERT one row per ANIMAL (PK facility_id) -> registry_subjects.csv ; scan→animal link via subject_ids ; position/age in sidecar ; NO junction table
  pending queue (exists)   §3A  pending_subject_metadata.csv + recover_subject_metadata.py
```

The only Program-A-specific piece is `parse_subject.py`'s permissive/vetted mode + the human review
gate; Program B swaps in the strict standard parser and an unattended dry-run. Everything else (walk,
DB, the per-scan entry build + animal-list, standard project hard-link, subjects table, pending queue)
is shared and mostly **already exists**.

---

## 8. Open questions (for Unai / the user — do not assume)

| ID | Question |
|---|---|
| NI-LIVE-01 | Is `data/<researcher>/<project>/<date>/<subject>/<ts>_<modality>/` the canonical layout for **all** NI users and **both** systems (Molecubes **and** MILabs VECTor), or Molecubes-only? |
| NI-LIVE-02 | Can we get a researcher→canonical-identity and researcher→PI mapping to normalise the typo/variant + researcher-vs-project folder names (§3(c))? |
| NI-LIVE-03 | Sync direction: does the researcher run the tool **on the Mac/box** (push), or do we **pull** from a reachable mount? Drives R10 and the `os.link` fallback choice. |
| NI-LIVE-04 | The scanner-clock-skew cohort (`irene/1025`, machine year 2026 vs folder 2025): is the **machine** clock wrong, or the **folder** label? Decides the R5 tie-break default. |
| NI-LIVE-05 | For acquisitions with multiple `recon_N` (CT often has `recon_0`/`recon_1`/`recon_2=ATTMAP`): keep all, or let the operator select (archive mode kept all)? |
| NI-LIVE-06 | Confirm the roster→folder map (§2A): is `ely` = Elena González? are `jrc`/`mjesus` Jesus (and does the PI ever scan)? do Susana / Iraia / Adrián / Ekine / Tania / Marta have NI folders (different slug / no NI use)? |
| NI-LIVE-07 | Subject grammar (§3A): is `m10-15` a 6-animal **range** or a pair? Confirm dashes are explicit lists except obvious consecutive pairs. Is the species prefix (`m`/`r`/none) reliable enough to set species, or always defer to the DB? |
| NI-LIVE-08 | ✅ **RESOLVED 2026-06-12** — packed `subject_ids` (`;`-joined, always-a-list) on `registry_raw.csv` + a true one-row-per-subject `registry_subjects.csv` + minimal sidecar `subjects:[…]`; no mapping table; query layer deferred. |
| NI-LIVE-12 | ✅ **RESOLVED 2026-06-12** — our own NAS `registry_subjects.csv` (not the facility DB as the table). Minimal sidecar subset still TBD beyond species/sex/age-at-acq. |
| NI-LIVE-09 | ⚠️ **PARTIAL (2026-06-12)** — `ni_live_discover.py` now **flags** the typo-shaped near-miss (`project-conflict:<parent>`, e.g. subject `1015_…` under parent `1025`) instead of silently picking; wholesale series≠protocol differences are left unflagged by design. **Still open:** the *resolution rule* — on a confirmed conflict, which code wins? And when the subject is a bare number, is "parent series leading digits" the right project source for the DB join, given series_id (funded) ≠ animal-protocol code? |
| NI-LIVE-10 | §3B: confirm a multi-mouse scan is **one shared-FOV reconstruction** (all mice in one volume) so hard-link-same-DICOM is exactly right — vs. the platform ever exporting per-mouse cropped images. |
| NI-LIVE-11 | §3B: the **position-numbering standard** — how is "which mouse is in slot N" determined and recorded (researcher-entered? bed geometry? a fixed head-first / left-to-right convention)? For historical data position is usually unknown → record animal, flag position. |
| NI-LIVE-13 | §7 Program B: who **enforces the forward naming standard** — researchers typing folders (then B still needs defensive parse + dry-run), or a platform-side acquisition template that emits regular names? |

---

## 9. Related

- [`internal_ni_data_handling_workflow_notes.md`](internal_ni_data_handling_workflow_notes.md) — archive-mode (implemented); the inside-the-acquisition keep/drop rules and the `ni:` sidecar shape this doc reuses.
- [`nuclear_imaging_platform_description.md`](nuclear_imaging_platform_description.md) — equipment/vendor spec (Molecubes + MILabs VECTor).
- `tools/templates/instruments/molecubes_ni.yaml` — archive-mode template (the live variant derives from it).
- `tools/operator/ni_ingest.py`, `tools/operator/metadata_prompt.py` — operator front-end to extend.
- `tools/ingest_raw.py::copy_ni_acquisition`, `tools/ingest/ni_metadata.py` — slim-copy + metadata internals (reused unchanged).
- `tasks/correction_pass_handoff.md` items (4)/(6)/(11) — idempotency, empty-folder guard, and the `os.link` diagnostic that this live path also depends on.
- Evidence snapshot: `S:\gnuclear\2026\Jesus\Ryan\datapath.txt` (295,538-line recursive listing).

**Field-practice references (multi-mouse + DICOM one-patient, for §3B):**
- "Design and Implementation of the Pre-Clinical DICOM Standard in Multi-Cohort Murine Studies" — the split-routine + new-UID + reference-original practice. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7934703/
- "High-Throughput PET/CT Imaging Using a Multiple-Mouse Imaging System" (mouse hotel, ~4× throughput). https://jnm.snmjournals.org/content/61/2/292 · https://pmc.ncbi.nlm.nih.gov/articles/PMC7002164/
- DICOM hierarchy (one patient per study): https://www.candelis.com/blog/dicom-hierarchy
