"""A1 step 4b: why are 100 of this drive's PET/CT reconstructions in the S:\\gnuclear snapshot but not
in production? Re-runs the pull's own path analysis on their snapshot paths.

tools/ni_gnuclear_discover.py analyse(rel, size, valid_codes) is a pure function of the path (the
valid protocol list comes from one SELECT on the facility DB's `projects` table). Nothing is
written anywhere but a1\\pet_heldback_reanalysis.csv.

    python a1_41_gnuclear_heldback.py
"""
import collections
import os
import sys

from a1_common import OUT, TOOLS, read_csv_dicts, write_csv

sys.path.insert(0, TOOLS)
import animal_db  # noqa: E402
import ni_gnuclear_discover as g  # noqa: E402


def main():
    conn = animal_db.get_connection()
    try:
        valid = g.valid_protocol_codes(conn)
    finally:
        conn.close()
    pet = read_csv_dicts(os.path.join(OUT, "pet_files.csv"))
    held = {}
    for r in pet:
        if r["coverage"].startswith("only in the S") and r["gnuclear_sha_rel"]:
            held.setdefault(r["gnuclear_sha_rel"], r["relpath"])
    rows = []
    for rel, drive_rp in sorted(held.items()):
        a = g.analyse(rel, 0, valid)
        segs = rel.split("/")[:-1]
        codes_in_path = [s for s in segs if g.SEG_CODE_RE.match(s) and g.SEG_CODE_RE.match(s).group(1) in valid]
        rows.append({"snapshot_rel": rel, "drive_relpath": drive_rp, "acq_key": a["acq_key"],
                     "pull_project": a["project"] or "(none)", "pull_flags": a["flags"],
                     "subject_folder": a["subject_folder"], "series": a["series"],
                     "valid_codes_in_snapshot_path": ";".join(codes_in_path)})
    write_csv("pet_heldback_reanalysis.csv", rows, list(rows[0].keys()))
    print(f"held-back reconstructions on this drive: {len(rows)}")
    print("pull's project:", collections.Counter(r["pull_project"] for r in rows))
    print("valid codes present in the snapshot path:", collections.Counter(r["valid_codes_in_snapshot_path"] for r in rows))


if __name__ == "__main__":
    main()
