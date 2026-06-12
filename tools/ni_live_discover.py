#!/usr/bin/env python3
"""ni_live_discover.py — Step-1 discovery DRY-RUN for the live-machine NI sync.

READ-ONLY. Writes nothing to the NAS, the box, or the registry. Given an MFB
researcher's folder on the Molecubes live data tree (or an offline recursive
path listing of it), it:

  * finds every acquisition anchor  <YYYYMMDDhhmmss>_<MODALITY>  — the one
    reliable machine-issued unit (everything above it is hand-typed);
  * parses the messy parent "subject" folder into (project, 1-4 animals,
    timepoint) per the validated grammar;
  * derives the machine date and flags any disagreement with the typed date
    folder;
  * prints a REVIEW TABLE (one row per acquisition) so a human can eyeball the
    parse BEFORE anything is ingested.

It does NOT touch the animal-facility DB — it prints the (project, animal) key
and the would-be facility id so you can see exactly what WOULD be looked up.
Flagging, never silent guessing: anything ambiguous gets a FLAG, not a decision.

Design: equipment/nuclear-imaging/live_machine_data_layout_and_sync_rules.md
(§2A roster, §3A subject grammar, §3B one-entry-per-scan, §7 plan).

Usage:
  # offline, against the recursive path dump already captured:
  python tools/ni_live_discover.py --from-listing S:/gnuclear/2026/Jesus/Ryan/datapath.txt irene
  # against a real mounted tree (when run on the box):
  python tools/ni_live_discover.py --root /Users/molecubes/Documents/volumes/remiW11/data irene
  python tools/ni_live_discover.py --from-listing FILE --all          # every MFB folder
  python tools/ni_live_discover.py --from-listing FILE irene --csv review_irene.csv
"""
import argparse
import csv
import datetime
import os
import re
import sys

DEFAULT_PREFIX = "/Users/molecubes/Documents/volumes/remiW11/data"

# MFB (Jesus Ruiz-Cabello, "Molecular and Functional Biomarkers") group folders
# confirmed present on the box. Edit as people join/leave. Most group members do
# NOT do NI, so a short list is expected. Ambiguous candidates are NOT enabled
# here — confirm before adding (NI-LIVE-06): ely=Elena? jrc/mjesus=Jesus?
MFB_FOLDERS = {"irene", "claudia", "ermal", "aitor", "itziar", "carlotta", "laura"}

MACHINE_CAP = 4  # the scanner physically holds <= 4 mice

ANCHOR_RE = re.compile(r"^(\d{14})_(PET|CT|SPECT|OI)$")
DATE6_RE = re.compile(r"^\d{6}$")
PROJECT_PREFIX_RE = re.compile(r"^(\d{3,4})[_-](.+)$")
PROJECT_LEAD_RE = re.compile(r"^(\d{3,4})")
TIMEPOINT_TAIL_RE = re.compile(r"^(.*)[_-](\d+h|d\d+|day\d+)$", re.I)
ANIMAL_RE = re.compile(r"^([mr]?)0*(\d+)$", re.I)
# hand-made levels that sometimes sit between the subject folder and the anchor
INTERMEDIATE_NOISE_RE = re.compile(r"^(new[ _]?recon.*|reconstructed.*|recon_\d+)$", re.I)

SPECIES = {"m": "mouse", "r": "rat", None: "?"}


def parse_subject(subject, parent_series):
    """subject folder -> {phantom, project, animals[], timepoint, flags[]}.

    Grammar (validated against real MFB folders):
      [<3-4 digit project> <sep>] <animal-list> [<sep> <timepoint>] | phantom...
      sep = "_" or "-" (varies by person); animal prefix m/r/none (inconsistent);
      project often omitted -> recovered from the parent series folder's lead digits.
    """
    flags = []
    s = subject.strip()
    if "phantom" in s.lower():
        return {"phantom": True, "project": None, "animals": [], "timepoint": None,
                "flags": ["phantom"]}

    project, rest = None, s
    m = PROJECT_PREFIX_RE.match(s)
    if m:
        project, rest = m.group(1), m.group(2)
    else:
        if parent_series:
            pm = PROJECT_LEAD_RE.match(parent_series)
            if pm:
                project = pm.group(1)
                flags.append("project<-parent")
        if project is None:
            flags.append("no-project")

    timepoint = None
    tm = TIMEPOINT_TAIL_RE.match(rest)
    if tm:
        rest, timepoint = tm.group(1), tm.group(2)

    animals = []
    last_species = None
    for tok in [t for t in re.split(r"[_-]", rest) if t]:
        am = ANIMAL_RE.match(tok)
        if not am:
            flags.append(f"unparsed:{tok}")
            continue
        sp = (am.group(1).lower() or None)
        if sp:
            last_species = sp
        animals.append({"raw": tok, "species": sp or last_species, "number": int(am.group(2))})

    if not animals and not timepoint:
        flags.append("no-animals")
    if any(a["species"] is None for a in animals):
        flags.append("species-unknown")
    if len(animals) > MACHINE_CAP:
        flags.append(f"gt-{MACHINE_CAP}-animals")
    if len(animals) == 2 and abs(animals[1]["number"] - animals[0]["number"]) > 1:
        flags.append("possible-range")
    return {"phantom": False, "project": project, "animals": animals,
            "timepoint": timepoint, "flags": flags}


def facility_id(number, project):
    """The would-be canonical facility id (animal_db.compose_subject_id form)."""
    return f"{number}-AE-biomaGUNE-{project}" if project else None


def _date_flag(machine_ymd, folder_yymmdd):
    if not folder_yymmdd:
        return ""
    try:
        md = datetime.date(int(machine_ymd[:4]), int(machine_ymd[4:6]), int(machine_ymd[6:8]))
        fd = datetime.date(2000 + int(folder_yymmdd[:2]), int(folder_yymmdd[2:4]), int(folder_yymmdd[4:6]))
    except ValueError:
        return "baddate"
    d = abs((md - fd).days)
    return "" if d <= 1 else f"d{d}!"


def build_row(segs):
    """One path (split into segments after the data prefix) -> a review row dict."""
    researcher, anchor = segs[0], segs[-1]
    ts, modality = ANCHOR_RE.match(anchor).groups()
    # subject = parent of the anchor, stepping over hand-made intermediate levels
    i = len(segs) - 2
    while i > 1 and INTERMEDIATE_NOISE_RE.match(segs[i]):
        i -= 1
    subject = segs[i] if i >= 1 else ""
    parent_series = segs[1] if len(segs) >= 3 else None
    p = parse_subject(subject, parent_series)

    machine_ymd = ts[:8]
    folder_yymmdd = next((s for s in segs[1:-1] if DATE6_RE.match(s)), None)
    animals_str = ",".join(a["raw"] + f"({SPECIES[a['species']]})" for a in p["animals"])
    keys = [facility_id(a["number"], p["project"]) for a in p["animals"]]
    keys = [k for k in keys if k]
    return {
        "researcher": researcher,
        "relpath": "/".join(segs),
        "subject_folder": subject,
        "modality": modality,
        "machine_date": machine_ymd,
        "folder_date": folder_yymmdd or "",
        "date_flag": _date_flag(machine_ymd, folder_yymmdd),
        "project": p["project"] or "",
        "n_animals": len(p["animals"]),
        "animals": animals_str,
        "timepoint": p["timepoint"] or "",
        "phantom": "yes" if p["phantom"] else "",
        "facility_keys": ";".join(keys),
        "flags": ",".join(p["flags"]),
    }


def iter_from_listing(path, prefix, folders):
    pref = prefix.rstrip("/") + "/"
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.rstrip("\n").rstrip("/")
            if not p.startswith(pref):
                continue
            segs = p[len(pref):].split("/")
            if len(segs) >= 2 and segs[0] in folders and ANCHOR_RE.match(segs[-1]):
                yield segs


def iter_from_root(root, folders):
    for folder in sorted(folders):
        base = os.path.join(root, folder)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, _files in os.walk(base):
            if ANCHOR_RE.match(os.path.basename(dirpath)):
                rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
                yield rel.split("/")
                dirnames[:] = []  # an anchor's children are recon_N/... — don't descend


def main(argv):
    ap = argparse.ArgumentParser(description="Step-1 discovery dry-run for live-machine NI sync (read-only).")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-listing", metavar="FILE", help="a recursive path dump of the data tree")
    src.add_argument("--root", metavar="DIR", help="a real mounted data root (os.walk it)")
    ap.add_argument("who", nargs="?", help="MFB researcher folder (e.g. irene); omit with --all")
    ap.add_argument("--all", action="store_true", help="every confirmed MFB folder")
    ap.add_argument("--prefix", default=DEFAULT_PREFIX, help="data-root prefix in the listing")
    ap.add_argument("--limit", type=int, default=60, help="max rows to print (full count in summary)")
    ap.add_argument("--csv", metavar="OUT", help="write the full review table to CSV")
    args = ap.parse_args(argv[1:])

    if args.all:
        folders = set(MFB_FOLDERS)
    elif args.who:
        if args.who not in MFB_FOLDERS:
            print(f"'{args.who}' is not a confirmed MFB folder. Known: {', '.join(sorted(MFB_FOLDERS))}")
            print("(Not all group members do NI; add a confirmed folder to MFB_FOLDERS if needed.)")
            return 2
        folders = {args.who}
    else:
        ap.error("give a researcher folder or --all")

    src_iter = (iter_from_listing(args.from_listing, args.prefix, folders) if args.from_listing
                else iter_from_root(args.root, folders))
    rows = [build_row(segs) for segs in src_iter]
    rows.sort(key=lambda r: (r["researcher"], r["machine_date"], r["modality"]))

    cols = [("subject_folder", 22), ("modality", 6), ("machine_date", 10), ("folder_date", 7),
            ("date_flag", 6), ("project", 6), ("n_animals", 3), ("animals", 26),
            ("facility_keys", 30), ("flags", 24)]
    hdr = "  ".join(name.upper()[:w].ljust(w) for name, w in cols)
    print("\n" + hdr)
    print("  ".join("-" * w for _, w in cols))
    for r in rows[:args.limit]:
        print("  ".join(str(r[name])[:w].ljust(w) for name, w in cols))
    if len(rows) > args.limit:
        print(f"... {len(rows) - args.limit} more (use --csv to get the full table)")

    # summary
    from collections import Counter
    mod = Counter(r["modality"] for r in rows)
    n_animals = sum(r["n_animals"] for r in rows)
    multi = sum(1 for r in rows if r["n_animals"] > 1)
    phantoms = sum(1 for r in rows if r["phantom"])
    flagged = [r for r in rows if r["flags"]]
    flag_counts = Counter(f for r in rows for f in r["flags"].split(",") if f)
    db_ready = sum(1 for r in rows if r["facility_keys"])
    mismatches = sum(1 for r in rows if r["date_flag"] and r["date_flag"] != "baddate")

    print(f"\n=== SUMMARY ({', '.join(sorted(folders))}) ===")
    print(f"acquisitions      : {len(rows)}   ({', '.join(f'{m} {c}' for m, c in mod.most_common())})")
    print(f"animals (summed)  : {n_animals}    | multi-animal scans (>1): {multi}    | phantoms: {phantoms}")
    print(f"DB-keyable scans  : {db_ready}/{len(rows)} (project+animal parsed -> a facility lookup would fire)")
    print(f"date mismatches   : {mismatches} (>1 day machine-vs-folder)")
    print(f"flagged for review: {len(flagged)}")
    for flag, c in flag_counts.most_common():
        print(f"    {flag:<22} {c}")
    print("\n(READ-ONLY: nothing was written. This is a parse preview for human review.)")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["relpath"])
            w.writeheader()
            w.writerows(rows)
        print(f"full table -> {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
