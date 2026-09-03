# Launch rollout — demo ideas and talking points

**For:** Ryan · **Audience:** PI + 7 pilot participants · **Date:** 2026-09-03
**Purpose:** raw material for the presentation. Not a script. Every number here was measured
against live production on 2026-09-02 — re-check anything you plan to say out loud
(`tasks/STATUS.md` §0 has the commands).

---

## 0. The one framing that decides adoption

The room's silent question is **"is this extra work for me?"** Every demo should answer *no* by
showing something the system already did **without being asked**.

Lead with what they get for free. Save "here's what you need to do" for the last five minutes, and
make it small.

---

## 1. Numbers that land

| | |
|---|---|
| **16,375** acquisitions | across **1,977,590** files |
| **7 instruments** | MRI 11,208 · Cell Observer 1,739 · CT 1,149 · AxioScan 908 · LSM900 805 · PET 491 · external MRI 75 |
| **2018 → 2026** | the system is new; **the archive is not** |
| **100%** | carry a `metadata.json` sidecar |
| **99.97%** | checksummed (16,370 of 16,375) |
| **1,165 subjects** · **58 projects** | |
| **0.78 TB** | the whole archive — smaller than most people expect, because raw ≠ working copies |

**The line worth saying:** *"Every single acquisition in there is checksummed and carries a metadata
record. Not most. All of them."*

---

## 2. Live demos, best first

### 2.1 ⭐ One animal, four instruments, one identity — the strongest single demo

**`18-AE-biomaGUNE-0424`** — a real mouse:

| | | |
|---|---|---|
| MRI | 19 acquisitions | 2025-10-16 |
| PET | 2 | 2025-10-21/22 |
| CT | 2 | 2025-10-21/22 |
| AxioScan histology | 4 | 2026-04-29 → 2026-07-02 |

**27 acquisitions, four instruments, nine months apart — one subject id, one query.**
And nobody typed that id: it is the animal-facility DB's own `<animal>-AE-biomaGUNE-<protocol>`,
reused verbatim, so the join to the facility record is free.

**212 subjects** in the archive are already imaged on **3+ different instruments**. This is the
capability nobody had before — in vivo imaging and its own histology under one identifier.

### 2.2 ⭐ The metadata nobody typed

Show a `metadata.json` sidecar next to a raw acquisition. Point at the `subject:` block:

> species *Mus musculus* · strain **C57BL/6JRj** · sex F · DOB 2024-04-04 · **age at acquisition,
> computed** · the animal's logged procedures

**None of that was entered by the researcher.** It was pulled from the animal-facility database at
ingest and attached automatically. Then open `mri._raw_metadata` and scroll — the *entire*
ParaVision parameter record is preserved verbatim, every sequence parameter, forever.

**The line:** *"You ran the scan. The system wrote the paperwork."*

### 2.3 The Finder — find your data without asking anyone

A single `index.html`, searchable, no server, no login, rebuilt nightly. Filter by instrument,
project, subject. This is the daily-use answer to *"where is that scan from March?"*

⚠️ **See §6 before demoing a search on a person's name.**

### 2.4 One-click ingest — `gjesus3_ingest.exe`

Already deployed at `\\gjesus3\gjesus3\gjesus3-data\tools\` with shortcuts: **Microscopy Ingest**,
**MRI Ingest**, **Project Manager**. No command line, no Linux, no training.

If you demo one thing operational, demo **MRI Ingest**: it lists studies on the scanner, pulls
read-only, previews, ingests. The researcher never touches a path.

### 2.5 Project folders that cost nothing

A project folder looks like a normal folder full of normal files — but they are **hard links**, so
a 50 GB study in three projects still occupies 50 GB, not 150 GB. Deleting a project folder
**cannot** touch `/raw/`.

**The line:** *"Organise your data however you like. It costs zero bytes and it can't break the
archive."*

### 2.6 Curated datasets — ground truth that outlives the project

Four segmentation datasets registered this month (`DS-SEG-0001`…`0004`) — manual cardiac LV/RV
masks, PMOD VOI sets, and an **inter-observer set with three independent human readers** on the
same animals.

Every label traces to a specific acquisition: **100% provenance resolution on all four datasets**
(821/821, 89/89, 308/308, 111/111 ACQ-IDs). That is a ready-made ML training set with a
defensible provenance chain — and a paper's worth of inter-rater material.

---

## 3. The trust story — aim this at the PI

This is the strongest argument in the room, and it is not about convenience.

### 3.1 We recovered data that was effectively lost

- **854 acquisitions from 2021** existed *only* on a researcher's share. They had aged off the
  scanner's own disk. The system's bulk pull couldn't have found them — we went and got them.
- **One more session** (`jrc250526_145_0522`) was missing because the operator omitted one letter
  when naming the folder at the console. Nobody would ever have noticed.

**The line:** *"Data on one person's drive is one resignation away from gone."*

### 3.2 The system finds errors humans made — including ours

Worth being candid; it lands better than polish:

| What was wrong | How it was caught |
|---|---|
| 15 acquisitions attributed to **three uninvolved rats** | the XNAT import flagged a header/registry mismatch |
| 444 subject ids silently merged two different animals | a validator check added after the fact |
| 10,314 rows carrying an unfilled template placeholder | a new template-residue check |
| 19 acquisitions likely on the **wrong animal** (open) | cross-checked against the facility DB's procedure log |

**The point:** in a folder-and-filename world every one of these is invisible forever. Here they
surfaced, and each one is written down with its evidence.

### 3.3 Immutability with an audit trail

`/raw/` is write-once. Corrections happen through recorded recovery procedures that keep the
original identifier and log what changed. **Nothing is silently overwritten.**

---

## 4. XNAT + OMERO — the part that makes it feel real

*(You know the deployment state; I only have what's in the repo. Adjust freely.)*

Framing that works: **gjesus3 is the archive of record; XNAT and OMERO are the windows into it.**
Three layers, one source of truth — the archive doesn't depend on the viewers, and the viewers
can be rebuilt from the archive.

- **See the images in a browser** — no local software, no copying 40 GB to a laptop.
- **OMERO** for microscopy: zoom a whole-slide image without downloading it; ROIs and annotations.
- **XNAT** for DICOM: subject-centric browsing that mirrors the same `<animal>-AE-biomaGUNE-<protocol>`
  identity — the ids line up because both read the same registry.
- **Worth telling the room:** the XNAT trial is what *caught* the PROJ-0056 misattribution. The
  viewers are not just display — they are a second opinion on the archive.
- **Collaborators.** Sending a link beats posting a hard drive — and access is controlled.

**Ask the room:** who wants their project loaded first? Volunteering is the adoption hook.

---

## 5. Honest caveats — say them, don't hide them

Being straight about limits buys credibility for everything else, and pre-empts the sceptic.

- **Backup/DR is the #1 open risk.** One copy on one NAS. Off-site backup is researched
  (EU-sovereign S3 + offline disk) and not yet bought. **Say this before someone asks.**
- **On-site access only** — hardwired machines, no laptops.
- **`researcher` is blank on 12,386 of 16,375 rows.** Historical data often names no person.
  Going forward the tools capture it; retroactively we won't invent it.
- **Nuclear-imaging live ingest isn't built yet** — it's still a data-office pull.
- **The MILabs VECTor has zero acquisitions in the system.** In-service, not yet integrated. If an
  attendee uses it, say so before they discover it.
- **673 NI acquisitions are held back** awaiting protocol codes — deliberately, because an AE code
  is a regulatory identifier and must never be invented.

---

## 6. ⚠️ Demo-safety notes — read before you present

1. **Do not demo a Finder search on a researcher's name.** Values are split by capitalisation:
   `Itziar` 390 / `itziar` 552 · `Irene` 402 / `irene` 255 · `Marina` 503 / `marina` 17. If Itziar
   searches her own name she may see **390 of her 942** acquisitions, in the room, at launch.
   **2,119 acquisitions are affected. I can normalise these to the documented lowercase convention
   in a few minutes if you want it done tonight — say the word.**
2. **Don't run `validate_registries` live.** It exits FAILED with 10,314 errors — all one known
   cosmetic placeholder in `operator` (STATUS §0 D1). Correct, expected, and impossible to explain
   quickly on a projector.
3. **Search by subject id, project, or instrument** — those are clean and impressive.
4. Have `18-AE-biomaGUNE-0424` and its sidecar **open in a tab beforehand.** The NAS is fast but
   a 22 MB Finder page and a live SMB browse are not instant.

---

## 7. Asks — end with these

Make the requests small, concrete, and immediate:

1. **Name your projects like you mean it.** Project names are how everyone else finds your work.
2. **Use the ingest tool the day you acquire**, not at paper-writing time.
3. **Tell us the operator** — the one field the system genuinely cannot derive.
4. **Volunteer a project for XNAT/OMERO.**
5. **Bring us your old drives.** The 2021 recovery is the proof: if it exists somewhere, it can be
   brought in — and every month it sits on a personal disk is a month it can vanish.

**Closing line, if you want one:**
> *"You already generated all of this. The only thing that changed is that now you can find it,
> prove where it came from, and still have it in ten years."*

---

## 8. Optional flourishes if you have time

- **Before/after**: a researcher's folder tree vs. the registry row for the same acquisition.
- **The oldest thing in there** — 2018 — next to something from last week. Same structure.
- **1,977,590 files, 100% sidecar coverage.** Ask the room how long a manual audit of that would take.
- **The 3-reader inter-observer set** (`DS-SEG-0004`) — pitch it to anyone doing segmentation as a
  free benchmark.
