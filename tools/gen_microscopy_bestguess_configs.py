#!/usr/bin/env python3
"""Generate per-top-folder BEST-GUESS ingest configs for the legacy Zeiss
microscopy instruments (Cell Observer = CELL, Confocal LSM 900 = LSM9) that have
no naming standard. One config per source top-folder = one provisional project
(literal slugged project_hint). This keeps the source-drive copy to one folder at
a time (the drive is in daily use) and avoids any shared-pipeline change.

Does ONE shallow listing of the base dir (light on the source drive). Writes
configs only; copies nothing. Skips stray top-level files and junk.

    python tools/gen_microscopy_bestguess_configs.py --instrument LSM9 \
        --base "K:/gjesus/Ainhize/CONFOCAL LSM 900" \
        --out-dir tools/configs --skip "Claudia Uptake CCMn-doxo"
"""
import argparse
import os
import re
import unicodedata

SKIP_NAMES = {"thumbs.db", "desktop.ini", ".ds_store"}
INSTR = {"LSM9": "lsm900", "CELL": "cellobs"}


def slug(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "unnamed"


def config_text(instrument, base, folder, project_slug):
    staging = (base.rstrip("/") + "/" + folder).replace("\\", "/")
    return f"""# {instrument} — MFB best-guess ingest (legacy, no naming standard), 2026-06-15.
# *** LOW CONFIDENCE *** auto-generated per source folder. Reliable fields from the
# .czi; sample_type/anatomy/control guessed post-ingest by
# tools/backfill_microscopy_bestguess.py (source=auto-guess). One folder = one
# provisional project. Source in daily use: single-folder, single-threaded copy.

ingest:
  delete_source_after_ingest: false
  auto_create_projects: true

auto_discover:
  staging_dir: "{staging}"
  pattern: "**/*.czi"
  subject_from_db: false

registry:
  instrument:           {instrument}
  data_ecosystem:       MICROSCOPY
  instrument_model:     discovered.czi_microscope_name
  modalities_in_study:  NA
  researcher:           "NA"
  data_source:          internal
  sample_id:            "${{discovered.filename}}"
  sample_type:          "NA"
  acquisition_datetime: discovered.czi_acquisition_datetime
  project_hint:         "{project_slug}"
  notes:                "BEST-GUESS / LOW-CONFIDENCE — legacy {instrument}, no naming standard; project = source folder '{folder}', sample_id = filename; sample_type/anatomy guessed post-ingest. Verify before scientific reuse."

operator: "${{discovered.czi_user}}"

auto_create_project:
  owner:       "NA"
  description: "Auto-created BEST-GUESS project from legacy {instrument} source folder '{folder}' (no naming standard)."
  notes:       "Provisional best-guess grouping = the source folder. Re-project later if a real convention is established."

link_filename: "${{instrument}}_${{original_name}}"
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instrument", required=True, choices=sorted(INSTR))
    ap.add_argument("--base", required=True, help="instrument source dir")
    ap.add_argument("--out-dir", default="tools/configs")
    ap.add_argument("--skip", action="append", default=[], help="top-folder name to skip")
    args = ap.parse_args()

    skip = {s.lower() for s in args.skip} | SKIP_NAMES
    entries = sorted(os.listdir(args.base))          # ONE shallow listing
    written = []
    for name in entries:
        if name.lower() in skip:
            continue
        full = os.path.join(args.base, name)
        if not os.path.isdir(full):                  # skip stray files (e.g. a settings .czi)
            print(f"  skip (not a dir): {name}")
            continue
        ps = slug(name)
        fname = f"{INSTR[args.instrument]}_bestguess_{ps}.yaml"
        path = os.path.join(args.out_dir, fname)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(config_text(args.instrument, args.base, name, ps))
        written.append((name, ps, fname))
        print(f"  {name!r:55s} -> project '{ps}'  [{fname}]")
    print(f"\n{len(written)} config(s) written to {args.out_dir}")


if __name__ == "__main__":
    main()
