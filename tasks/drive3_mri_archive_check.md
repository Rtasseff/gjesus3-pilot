# The M. Jesús drive's MRI (stream M) against the MRI platform's archive: the originals check

**Status:** 🔶 DRAFT for the coordinator, 2026-10-08. **Read-only:** production (`J:\gjesus3-data`) was read, never
written; nothing was repaired. **Branch:** `feat/mri-archive-ingest`.
**What:** BACKLOG "after the platform-archive MRI ingest" (Ryan's M2, STATUS §0.5): every exam stream M registered from
M. Jesús's drive copies, compared with the platform's own archive copy.
**Per exam:** [`drive3_mri_archive_check.csv`](drive3_mri_archive_check.csv) (the 3,309 rows of
[`drive3_mri_for_archive_check.csv`](drive3_mri_for_archive_check.csv), with `archive_result`, `archive_detail` and
`recon_states` filled). **Census:** [`mri_archive_census.md`](mri_archive_census.md) §3.
**Source:** the 130 tier-C archives, pulled to `D:\projects\gjesus3\mri_archive\pull\` (each SHA-1-verified), extracted
locally; the archive itself was never contacted by this work.

## Summary

| Result | Exams | Studies | What it means |
|---|---:|---:|---|
| **identical** | **1,576** | 85 all-identical | the archive's DICOM set equals production's, file for file (bytes) |
| **pixel-identical** | **340** | 20 | same instances; the differing bytes are a re-export: pixel data and geometry equal, only `InstanceCreationDate` / `InstanceCreationTime` (and in 68 also `TimezoneOffsetFromUTC`) differ |
| **source-identical** | **63** | 4 | Dicomifier exams (production's DICOM was made from the drive's `2dseq`): the archive holds `2dseq` only, and its `2dseq`, `visu_pars` and `reco` equal the drive copy's |
| **missing on one side** | **367** | 25 | an export, a reconstruction or the exam is on one side only; nothing shared differs (below) |
| **different** | **0** | 0 | no shared instance differs in pixels or geometry; no shared ParaVision source differs |
| *not in the archive* | *963* | *59* | *the study is not in the archive: 267 on the 11.7 T (the archive is the 7 T's); 696 on 7 T days the archive lacks (census §3)* |
| **Total** | **3,309** | **189** | |

Every one of the 2,346 exams whose study is in the archive was compared; **no shared image differs**. Production's
DICOM digest equals the list's (made from the staged drive copy) for all 3,309.

**"Missing on one side", 367 exams, by what is missing:**

| Kind | Exams | Studies | Detail |
|---|---:|---:|---|
| The archive copy predates the DICOM export: it holds the `2dseq` only, **identical to the drive's** | 107 | 15 | the June 2020 `2DG` rats of `0118` (M01), `jrc200305_m36_flow` (M02), `jrc200615_m21_1019` (M05) |
| as above, and the drive also holds a **later reconstruction** (`pdata/2`) the archive lacks | 139 | 11 | June 2020 `2DG` rats (M01) |
| A later reconstruction only (the shared ones identical or pixel-identical) | 7 | 4 | `jrc200610_r169_2DG` (M01, 4); `jrc210323_m127`, `m133`, `m144_0619` (M03, 1 each) |
| **The archive holds the scanner's DICOM; production holds Dicomifier's** (the drive copy had `2dseq` only); the `2dseq` is identical | 106 | 6 | 2021-03-22, `0619`: `m125`, `m126`, `m131`, `m132`, `m137`, `m138` (M03) |
| The archive holds a reconstruction's DICOM production lacks | 1 | 1 | `jrc210322_m126_0619/11`, reconstruction 1 (reconstruction 2 pixel-identical) |
| The exam is not in the archive copy: **its tarball is short** | 7 | 1 | `jrc200615_m21_1019` (M05), exams after 19 |

**The other direction** (archive exams of these 130 studies that stream M did not register): 30. **29 are not images**
(28 never acquired, 1 k-space without a reconstruction), as stream M decided. **1 is an image exam production lacks:
`20210322_083218_jrc210322_m131_0619_1_1/7`** (`Cine MPA (E7)`, IgFLASH, 38 scanner DICOM). It was not on the drive copy.
It is not in the Part 2 plan (tiers A, A2, B); see "Unsettled".

## Findings

1. **No image disagrees.** Where both sides hold DICOM of a reconstruction, it is byte-identical (3,023 reconstructions) or a
   re-export with equal pixels and geometry (572). The drive copies stream M registered are faithful copies of the scans.
2. **Two archive tarballs are short, and their `.sha1` was made from the short file.** `2020_pv6/20200615_115642_
   jrc200615_m21_1019_1_1.tar.gz` (320,405,504 bytes) ends inside exam 19's k-space, and `2020_pv6/20200302_143910_
   jrc200302_m3r7f2_Caff_1_1.tar.gz` (19,333,120 bytes, a Part 2 study) ends inside exam 4's. Both sizes are multiples of
   4,096, and both `.sha1` files match the short file, so the archive was written short and then checksummed; the
   download is exact. `gzip -t` and `tar` both report "unexpected end". **For `m21`, the drive copy is the only complete
   copy known** (19 of its exams are partly or wholly absent from the archive). Everything read before the cut was kept
   and compared.
3. **The archive's 2020-06 studies predate their DICOM export.** For 246 exams the archive holds the reconstruction
   (`2dseq`) but no DICOM, while the drive holds the scanner's DICOM made later from the same `2dseq` (identical bytes);
   139 of them also carry a later reconstruction on the drive. Nothing is lost on either side.
4. **106 Dicomifier exams in production have the scanner's own DICOM in the archive** (2021-03-22, `0619`, 6 animals).
   The `2dseq` they were converted from is identical, so the images are the same acquisition; production simply holds
   Dicomifier's rendering where the scanner's export exists. A replacement is possible later with the recovery-tool
   pattern (not done: "a difference is reported, not repaired").
5. **Parameter files.** Of the 2,339 exams with source files on both sides, 2,329 agree on every shared non-k-space file.
   The other 10 (`r158`, `r159` `2DG`, 2020-06-08) differ only in the exam-level `b0` and `traj` files, which were
   rewritten when the drive's later reconstruction was made; their `2dseq`, `visu_pars` and `reco` are identical. Junk
   files (`.DS_Store`, `Thumbs.db`, `*.cache`) were ignored.

## Method

- **Extraction** (`ar_01_extract.py`): each tarball stream-read once; its SHA-1 recomputed in the same pass and equal to
  the fetch manifest's for all 130; members checked by `tarfile.data_filter` and confined to `<study>/`; k-space not
  extracted (listed with its size); every extracted file's SHA-256 recorded (`extract\_manifests\<study>.csv`). A short
  tarball is salvaged up to the cut, and the incomplete exam is recorded.
- **Inventory** (`ar_02_inventory.py`): per exam, reconstructions with `2dseq` and with DICOM, the DICOM-set digest by
  stream M's rule (SHA-256 over the sorted `recon<idx>_frame<NN>.dcm <sha256>` lines), method, dates, class. A fast
  JCAMP reader is used; `--check-parser` compares it with `tools/ingest/jcampdx` on 400 random exams: 0 disagreements.
- **Compare** (`ar_03_archive_check.py`), per exam and per reconstruction: production's DICOM from its `checksums.json`
  on `J:` (read-only) against the archive's extracted DICOM; where bytes differ, **pydicom** compares pixel data (raw
  `PixelData`, else the decoded array) and geometry (`Rows`, `Columns`, `NumberOfFrames`, `PixelSpacing`,
  `SliceThickness`, `ImagePositionPatient`, `ImageOrientationPatient`, bits, rescale), reading production's file
  read-only, and lists the other tags that differ (`out\archive_check_pixel_detail.csv`). Where the archive holds `2dseq`
  only, its `2dseq`, `visu_pars` and `reco` are compared with the drive copy stream M staged
  (`D:\projects\gjesus3\drive3_streams\mri\out\stage_result.csv`).

## Unsettled (for the coordinator)

| # | Item | Recommendation |
|---|---|---|
| P1-a | **`jrc210322_m131_0619/7`**: an image exam (38 scanner DICOM) production lacks, in a stream-M study | Register it with the archive ingest as one more exam of `AE-biomaGUNE-0619` (subject `131-AE-biomaGUNE-0619`, as its study's other exams); it is outside tiers A/A2/B, so it needs a one-exam batch. Or leave it, listed. |
| P1-b | **106 Dicomifier exams** whose scanner DICOM is in the archive (finding 4) | A later in-place replacement (recovery-tool pattern), if wanted; the archive's DICOM is on `D:` (`extract\C\`). Not urgent: same `2dseq`. |
| P1-c | **The short `m21_1019` archive** (finding 2) | Tell the platform manager with Q7 (the archive copy is incomplete; the drive copy is complete). |
| P1-d | The 246 exams whose archive copy has no DICOM, and the 146 exams with a later reconstruction | Nothing to do: production holds the complete set. |

## Reproduce

From the worktree root, `PYTHONDONTWRITEBYTECODE=1`; all read-only on `J:`; outputs under
`D:\projects\gjesus3\mri_archive\` (regenerable, not backed up):

```
python tools/drive_staging/mri_archive/ar_01_extract.py --tiers C      # resumable; the 130 tier-C archives
python tools/drive_staging/mri_archive/ar_02_inventory.py              # out\inventory_exams.csv
python tools/drive_staging/mri_archive/ar_03_archive_check.py          # ~5 min; tasks\drive3_mri_archive_check.csv
```
