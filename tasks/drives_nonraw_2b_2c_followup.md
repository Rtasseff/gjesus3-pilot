# Historical drives — what is left after the non-raw placement: Ryan's mapping (2b), then the holding folder (2c)

**Status:** 🕗 PLANNED / waiting on Ryan · **Written:** 2026-10-02 by stream A (`feat/drives-nonraw-placement`)
**Read this if you are:**
- **Ryan:** read [Part 1](#part-1--for-ryan-the-mapping) (what to fill in) and [Part 0](#part-0--one-decision-first-where-the-files-come-from) (one decision first).
- **The session that applies Ryan's answers, possibly months from now:** read everything, start to finish. You need no other conversation; everything you need is in the repo and on the paths below.

Background, if you want it: [`drives_nonraw_placement_review.md`](drives_nonraw_placement_review.md) (stream A's numbers and decisions), [`historical_drives_closeout_plan.md`](historical_drives_closeout_plan.md) Step 5 items 2, 2b and 2c.

---

## What 2b and 2c are, in three sentences

1. The two operator drives held material that **could not be tied to a project**: 32,494 non-raw files (210.6 GB of exports, figures, documents, EM images, …) and **5,055 raw acquisitions already in gjesus3 production with a blank project**.
2. **2b is the mapping:** Ryan says, group by group, which project they belong to. The tool then:
   - copies the non-raw files into that project's `working\historical_drives\…`;
   - links the raw acquisitions into the project and records the project on them.
3. **2c is the holding folder:** whatever stays unmapped goes to `J:\gjesus3-data\staging\historical_drives_unassigned\`, keeping the drives' own folder structure, with a `README.txt` and a `manifest.csv`.

Nothing in 2b or 2c deletes anything, re-ingests anything, or changes a raw file.

---

## Part 0 — one decision first: where the files come from

Every non-raw file is today read from the **staged copy of the drives on Ryan's D:**
(`D:\projects\gjesus3\staging\`). The close-out plan says that staging is erased "after Step 5's items 2–5 are done", and 2b/2c are part of item 2. **If the mapping takes months, D: has to be kept for months.**

| Option | What happens | D: can be erased | NAS cost |
|---|---|---|---|
| **A. As planned** | Ryan maps; the mapped groups are copied from D:; then the rest goes to the holding folder; then D: is erased. | only after the mapping round closes | about 212 GB, at the end |
| **B. Holding first** | Fill the holding folder **now** with all 32,558 unassigned files. Ryan maps whenever he can; each mapped group is copied **from the holding folder** into its project (`copy --from-holding`). | as soon as the other streams finish | about 212 GB in `staging\` now, plus a copy of each mapped group in its project (holding is never trimmed automatically) |

**Stream A's recommendation: B**, if the mapping will take more than a few weeks. It removes the only reason to keep D:, and the holding folder is what 2c produces anyway; the only change is *when*. **This is Ryan's call,** because his decision of 2026-10-02 says the holding folder is filled "only when Ryan closes the mapping round".

The **raw** half of 2b never needs D:. It works on `/raw/` on the NAS.

---

## Part 1 — for Ryan: the mapping

**The file:** `tasks/drives_nonraw_mapping_worksheet.csv` in this repo. It opens in Excel; it is UTF-8 with a BOM, so the accents show correctly.

**What a row is:** one group of related files with no project, for example `Laura | Proyectos_Laboratorio_Laura\Lung-surfactant` or `zuri | Drive zuri 170823.zip!PAPERS/…`. There are **288 rows**.

**Do the `A` rows first.** The `priority` column marks **62 rows `A`** (≥ 1 GB of files, or ≥ 20 blank-project acquisitions). Those 62 rows hold **190 of the 211 GB and 4,855 of the 5,055 acquisitions**. The 226 `B` rows are the long tail, and **leaving them blank is a fine answer**: blank means the holding folder.

**For each row you decide on:**
1. Read `researcher`, `series`, the date range, `example_1..3` and `acq_ids` (the blank-project acquisitions in the same place).
2. Type the **project name exactly as it is in gjesus3** in `project` (for example `AE-biomaGUNE-0721`, `laura`, `Project-0521`). The list is `J:\gjesus3-data\registries\registry_projects.csv`, column `name`.
   - **A new project** is fine. Write its name, and the applying session creates it after you confirm (it will ask).
   - **A closed project** (`AE-biomaGUNE-1521`, `-0618`, `-0320`, `-1519`, `-1121`, `-0220`) is refused until you say "reopen it".
3. Optionally write a note in `note_for_ryan`, for example "only the PPTs", "ask Laura", or "split: images to 0721, the rest holding". A note is read by a human, not by the tool, so a row with a "split" note will be asked about.

**Do not:**
- edit or delete the `group_key` column (it is how your answer is matched to the files; the `G001…` numbers are only display order);
- add or delete rows;
- sort and save away other columns.

**When you are done, save it as CSV.** Either "CSV UTF-8" or plain "CSV" works: the tool reads Excel's Spanish `;` format and ANSI encoding, and it was tested with exactly that. **Then:**
- commit it (or just leave it in the repo folder), and tell a session "apply the 2b mapping, see `tasks/drives_nonraw_2b_2c_followup.md`";
- say **"go"** for the writes. Setting projects on blank raw rows needs your go (weekend rule of 2026-10-02); your filled worksheet plus "go" is that go.

**Partial answers are fine.** Map the `A` rows, have them applied, and come back later. Re-applying is safe: everything already placed or linked is skipped.

**Your other open decisions** are in [`drives_nonraw_placement_review.md` §8](drives_nonraw_placement_review.md#8-open-questions-for-the-coordinator--ryan):
- path length;
- reopening `1519`/`0320`;
- the `.svs` scans;
- `Simu_2_V_XYZ.zip`;
- three damaged `.czi`;
- the raw one-offs.

---

## Part 2 — for the session that applies the mapping

You start cold. **Rules that still apply:**
- `CLAUDE.md`;
- production is real;
- every NAS write needs a dry run you have checked, Ryan's go, and a back-up of the registries to a **fresh, dated** folder under `C:\Users\rtasseff\temp\`;
- one writer at a time.

Work in a **new worktree** off `main` (e.g. `feat/drives-2b-apply`), per `CLAUDE.md`.

### 2.1 Check that the inputs still exist (read-only, 2 minutes)

The tool reads all of these; if one is gone, **stop** and tell Ryan which.

| Input | Path | Needed for |
|---|---|---|
| Ryan's filled worksheet | `tasks\drives_nonraw_mapping_worksheet.csv` | everything |
| blank-project acquisitions | `tasks\drives_blank_project_list.csv` | raw half |
| catalog | `D:\projects\gjesus3\staging\_analysis\catalog\files.csv`, `archive_members.csv`, `archives.csv` | `plan` (option A, and B's plan step) |
| claims | `D:\…\_analysis\codes\file_claims.csv`, `archive_member_claims.csv`, `noclaim_groups.csv` | `plan` |
| stream B's lists | `D:\…\_analysis\drives-dicom\imaging_roots.csv`, `nonraw_for_A.csv` (use the newest version B published) | `plan` |
| nested archives | `D:\…\_analysis\drives-nonraw-placement\nested_members.csv`, `nested_czi_dedup.csv` | `plan` |
| staged drives | `D:\projects\gjesus3\staging\drive1_FRIO-X6_2322E4A111E7\files\`, `drive2_MFB-Disco-2_2322E4A112BD\files\` | **option A copies** |
| holding folder | `J:\gjesus3-data\staging\historical_drives_unassigned\` | **option B copies** |

> If **D: is already erased** (option B), only these are needed:
> - the worksheet;
> - `drives_blank_project_list.csv`;
> - the record manifest kept in `J:\…\historical_drives_unassigned\_record\` (§2.6);
> - the holding folder.
>
> `remap` and `copy --from-holding` use exactly those. `plan` (the catalog route) can then no longer be re-run, and does not need to be.

Then run the tests: `python tools\test_nonraw_placement.py` (expect `all passed`).

### 2.2 Validate Ryan's answers (read-only)

**Use `remap`.** It applies the worksheet to stream A's **record manifest** and needs no catalog and no D:, so it works under option A and option B alike:

```
python tools\drive_staging\nonraw_placement.py --out "<NEW folder, e.g. D:\projects\gjesus3\staging\_analysis\drives-2b-YYYYMMDD>" remap --mapping tasks\drives_nonraw_mapping_worksheet.csv
```

**Where the record manifest is:**
- by default `D:\projects\gjesus3\staging\_analysis\drives-nonraw-placement\placement_manifest.csv`;
- once D: is erased, the copy kept in `J:\gjesus3-data\staging\historical_drives_unassigned\_record\` (§2.6); pass it with `remap --manifest <path>`.

`remap` refuses the default folder as `--out`, so the record is never overwritten. It was cross-checked on 2026-10-02 against the catalog-based route: both re-decided the same 4,040 files for a 2-group trial mapping.

> **Only if stream B published a newer `nonraw_for_A.csv` after 2026-10-02 *and* D: still exists,** refresh the record first:
> 1. `python tools\drive_staging\nonraw_placement.py plan` (rewrites the record manifest and the committed per-project summary; commit them);
> 2. then `remap`.
>
> `plan --mapping <worksheet>` with a new `--out` does both in one step and prints the same report into `plan.log`.

**Read `remap`'s output** (or `plan.log` for `plan --mapping`):
- `2b mapping: N groups mapped`: this must equal the number of filled `project` cells.
- `… non-raw files re-decided from K groups; U mapped groups matched no holding file`:
  - **U > 0 is normal for raw-only groups.** For every `unmatched:` line, check that the group has `nonraw_files` = 0 in the worksheet. If it has files, the key was edited: stop and fix it from git.
- Per project: decision `unclear` with "neither in the registry nor approved" means **a project that does not exist yet**. List them for Ryan, and create them only after he confirms (§2.3). `closed-project` means **closed**, and needs Ryan's "reopen".
- `note_for_ryan` cells: read every non-empty one, and if a note changes the mapping ("split", "only…"), ask Ryan; the tool does not read notes.

### 2.3 Projects (writes; Ryan's go)

- **New projects:** `python tools\create_project.py --nas-root "J:\gjesus3-data" --name "<name>" --owner Data-Office --description "<what it is>" --notes "Created for the historical-drives 2b mapping (tasks/drives_nonraw_2b_2c_followup.md)" --dry-run`, then again without `--dry-run`.
  - Back up `registries\` first (fresh dated folder).
  - The `AE-biomaGUNE-0118` row in `registry_projects.csv` is the model for owner and description.
- **Reopen** (only where Ryan said so): `python tools\reopen_project.py --nas-root "J:\gjesus3-data" --project <name> --reason "historical-drives 2b mapping" --dry-run`, then without.

Then **re-run §2.2**: the `unclear` and `closed-project` rows must be gone.

### 2.4 The raw half — link the blank-project acquisitions (registry write; Ryan's go)

```
python tools\drive_staging\nonraw_placement.py --out <same new folder> apply-raw --mapping tasks\drives_nonraw_mapping_worksheet.csv
```

**What `apply-raw` does:**
- It is a dry run by default.
- It writes `apply_raw_<project>.csv` per project into `--out`.
- It uses `tools/manager/raw_import.py`, the Project Manager's own "import from raw" engine:
  - a hard link in `<project>\raw_linked\`;
  - a provenance row;
  - `registry_raw.project_id` set **only where it is still blank** (`set_project_id_if_blank`).

**Link names** follow the drives ingest's rule (`CELL_<name>`, then `_<YYYYMMDD>`, then `_<ACQ-ID>`); without it the flat `raw_linked\` collides. **Expect every status to be `new`** (or `already-in-project` on a re-run). Any `collision` or `raw-missing` line stops that project: read the CSV and resolve it.

**Then:**
1. back up `registries\` to a fresh dated folder;
2. add `--execute`;
3. after it:
   - `python tools\validate_registries.py --nas-root "J:\gjesus3-data" --no-enrichment`: the error count must equal the baseline (10,314 on 2026-10-02, all the MRI `operator` placeholder, unless D1 was settled since). A new error class means stop.
   - Regenerate each touched project's Finder page: `python tools\generate_index.py --nas-root "J:\gjesus3-data" --project <PROJ-ID>`.
4. **Re-run the same command:** every row must now be `already-in-project`.

### 2.5 The non-raw half — copy the mapped groups (copies only; pre-approved class)

**Where files land: one shared rule** (Ryan, 2026-10-02), [`tools/drive_staging/historical_paths.py`](../tools/drive_staging/historical_paths.py). Review §6 explains it in full.
- The layout is `<project>\working\historical_drives\<FRIO-X6|MFB-Disco-2>\<study folder>\…`, with every path at most 240 characters.
- Each tree carries `_INDEX.csv`, `README.txt`, `_ORIGIN.txt` and `_PATHMAP.csv`.
- **`remap` and `plan` load the tree's `_PATHMAP.csv` from the NAS, so folders placed earlier keep their names.** A mapped group's study folder is the group's own folder (its `series`).
- `copy` publishes the updated index documents after the files.
- If a tree cannot fit the budget without renaming a placed folder, the run **stops** ("cannot bring under 240"): nothing is written, and a human decides.

```
python tools\drive_staging\nonraw_placement.py copy --manifest <new out>\placement_manifest.csv                 (dry run)
python tools\drive_staging\nonraw_placement.py copy --manifest <new out>\placement_manifest.csv --execute       (option A: from D:)
python tools\drive_staging\nonraw_placement.py copy --manifest <new out>\placement_manifest.csv --execute --from-holding   (option B)
python tools\drive_staging\nonraw_placement.py verify --manifest <new out>\placement_manifest.csv
```

**How `copy` behaves:**
- It copies every `place` row of that manifest.
- Rows already placed (stream A's first round, or an earlier partial 2b) are **skipped as identical**, so re-running is safe.
- A destination holding *different* bytes is a **collision**: it is never overwritten, that project stops, and the collision is listed.
- **`verify`** compares count and bytes per project against the manifest and re-hashes a random 2%.
- **Option B:** `--from-holding` reads each mapped file from its holding-folder copy and still checks its SHA-256 against the drive manifest. The holding copy is left in place.
- **Big copies:** run them in the background (about 60 MB/s to the NAS) with `--project <name>` to split them.

### 2.6 Before D: is erased (option B)

The erase is Ryan's (close-out plan, "The staged drive data on D: is erased…").

**Before it, the following must be done in this order:**
1. **`holding --execute`** with stream A's last full manifest (§2.7), verified;
2. copy, **off D:**, the record files 2b/2c still need, to `J:\gjesus3-data\staging\historical_drives_unassigned\_record\`:
   - `placement_manifest.csv` (stream A's, default folder);
   - `nested_members.csv`;
   - `nested_czi_dedup.csv`;
   - the drive manifests `drive1_…\manifest.csv` and `drive2_…\manifest.csv`.

After that, every 2b step still works without D::
1. `remap --manifest J:\gjesus3-data\staging\historical_drives_unassigned\_record\placement_manifest.csv` (§2.2);
2. `copy --from-holding` (§2.5);
3. `apply-raw` (§2.4), which never needed D:.

### 2.7 2c — fill the holding folder (copies only; the plan says "when Ryan closes the mapping round", or now under option B)

```
python tools\drive_staging\nonraw_placement.py holding --manifest <latest manifest>                 (dry run: totals, README + manifest previews)
python tools\drive_staging\nonraw_placement.py holding --manifest <latest manifest> --execute
```

**Which manifest:**
- if the round is closed: the manifest of the **last** `plan --mapping` run, so mapped groups are not also put in holding;
- under option B, now: stream A's manifest. Mapped groups are then *also* in holding, which is accepted, see Part 0.

**What it writes:**
- `J:\gjesus3-data\staging\historical_drives_unassigned\<drive label>\<original path>`, with the same exclusions as the placement;
- `README.txt`: where the files came from, why they are not in gjesus3, that the originals stay on the owners' drives, and to ask the Data Office;
- `manifest.csv`: relative path, size, SHA-256.

**Afterwards:**
- the folder must be **group-readable**: compare its ACL with `J:\gjesus3-data\staging\` (`icacls`);
- spot-check 2% (`verify` works on `place` rows only, so re-hash a sample by hand or extend `verify`).

2,489 holding paths exceed 259 characters (see the review §6): the same long-path note applies.

### 2.8 Done means

- [ ] every mapped group's non-raw files are in their project, verified (`verify` all OK);
- [ ] every mapped group's blank-project acquisitions are linked, and `project_id` is set where it was blank; the validator is unchanged;
- [ ] the holding folder holds everything still unmapped, with `README.txt` and `manifest.csv`;
- [ ] Ryan has a short report: per project, files / GB / acquisitions; what stayed in holding; anything refused (missing or closed project, collision, a note that needed a question);
- [ ] `tasks/STATUS.md` and `CHANGELOG.md` updated (dated), and BACKLOG items closed;
- [ ] **only then** tell Ryan the D: staging may be erased (option A), and delete `D:\projects\gjesus3\scratch_drives-nonraw-placement\`.
  - That folder includes two **throwaway trial** folders, `trial_mapping\` (with `worksheet_TRIAL_filled.csv`, **test** mappings G001 → `laura`, G008 → `AE-biomaGUNE-1123`) and `trial_remap\`. **Never apply them.** Stream A's session could not delete them (permission).

---

## Traps (each one has already happened in this effort)

- **Never re-plan with a destination rule other than `historical_paths.py`,** and never place drive material without loading the tree's NAS `_PATHMAP.csv`. Otherwise placed folders get a second, differently shortened twin.
- **An error handler must never rewrite decisions in the record manifest.** A budget failure once marked 37,000 rows `unclear` before the fail-stop was added. The tool now stops instead; if you add code, keep it that way.

- **Never join on the `G001…` numbers.** They change when the worksheet is regenerated. The tool joins on `group_key`.
- **Never regenerate the worksheet over Ryan's answers.** `worksheet` refuses if any `project` cell is filled; don't pass `--force` unless the answers are saved elsewhere.
- **Member paths from the claims pass use backslashes and lost their accents** (`Haizpea_2020-2022.7z`). The tool's `member_key` handles it; any new script that joins `archive_member_claims.csv` to the catalog must do the same.
- **Bash heredocs mangle backslashes:** `\x00` became a real NUL byte, and `\Z…` paths lost their slashes. Write scripts with the editor and run them; never patch code through a heredoc.
- **`raw_linked\` is flat.** Same-named files from different folders collide. Use `apply-raw` (it names links like the ingest did), not hand-made links.
- **Registry CSVs** are BOM-free and CRLF. Write them only through the tools (`raw_import`, `create_project.py`, `reopen_project.py`), which take the registry lock.
- **Never suppress stderr** on tree-wide searches under OneDrive.
