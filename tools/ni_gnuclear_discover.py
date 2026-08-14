#!/usr/bin/env python3
"""ni_gnuclear_discover.py — READ-ONLY review table for the S:\\gnuclear historical pull.

The sibling of `ni_live_discover.py` (which reads the live Molecubes box). This one
reads the *researcher working space*, whose shape is much messier: the depth between
a researcher folder and a DICOM varies from 0 to 8 levels, and the meaningful
"subject" folder can be buried under frame folders, timepoint folders, modality
folders and Spanish-language working folders.

It writes NOTHING anywhere. Its whole job is to let a human see, before any ingest,
what would be derived for each acquisition — and to make anything ambiguous show up
as a FLAG rather than a silent guess.

HOW THE SUBJECT FOLDER IS FOUND (the only real intelligence here)
----------------------------------------------------------------
Positional parsing cannot work on this tree, so we walk UP from the DICOM and take
the first ancestor that isn't structural noise:

  * frame/recon plumbing  — `recon_3/`, `frame_7/`, `iter_30/`, `Frames/`, `6 Frames/`,
    and a bare number directly under a `Frames/` level (that's a frame index);
  * a modality folder     — `PET/`, `CT/`;
  * rework folders        — `new recon/`, `reconstructed/`, `Nuevas reconstrucciones/`;
  * a timepoint           — `0h/`, `4h/`, `2h30min/`, `30min/`, `d7/` — NOT discarded,
    it is *recorded* as the timepoint, because for a dynamic/longitudinal study that
    is real metadata;
  * a `YYMMDD` date folder — recorded as the folder date and cross-checked against
    the machine timestamp.

Whatever we stop on is the subject folder, and the level above it is the "series"
(often the animal-protocol code). Both are then handed to the SAME validated grammar
the live box uses — `ni_live_discover.parse_subject` — so a subject folder means the
same thing whichever source it came from.

`2022/Jesus/MOLECUBES/<user>/…` carries one extra level; the real researcher is
below `MOLECUBES`, and that is handled explicitly.

USAGE
-----
    # against the plan produced by pull_ni_gnuclear.py --plan (no NAS needed):
    python tools/ni_gnuclear_discover.py --from-plan <dest>/_plan.csv

    # against the staged snapshot on gjesus3:
    python tools/ni_gnuclear_discover.py --root J:/gjesus3-data/staging/ni_gnuclear_20260812

    # write the full table for review:
    python tools/ni_gnuclear_discover.py --from-plan ... --csv review_gnuclear.csv
"""
import argparse
import collections
import csv
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ni_live_discover  # noqa: E402  (parse_subject / facility_id — the shared grammar)

DCM_RE = re.compile(
    r"^(?P<ts>\d{14})_(?P<modality>PET|CT|SPECT|OI)_(?P<algo>[A-Za-z]+)_(?P<recon>\d+)"
    r"(?:_frame(?P<frame>MULTI|\d+))?(?:_iter(?P<iter>\d+))?(?:_(?P<extra>[^.]+))?\.dcm$",
    re.IGNORECASE,
)

# --- structural noise between the subject folder and the DICOM ---------------
NOISE_RE = re.compile(
    # `<14digit>_<MODALITY>` is the machine-issued ACQUISITION folder — it appears
    # in the 13 box-shaped trees in 2022-23 and is never a subject. Without it the
    # walk-up stopped on the anchor and reported it as the subject folder.
    r"^(\d{14}_(pet|ct|spect|oi)"
    r"|recon_?\d+|frame_?\d+|iter_?\d+|frames?|\d+\s*frames?"
    r"|pet|ct|spect|oi|pet[_ -]?ct|ct[_ -]?pet|spect[_ -]?ct"
    r"|new[ _]?recon.*|reconstruct(ed|ions?).*|nuevas?[ _]reconstrucciones?"
    r"|dicom|dicoms|images?|data)$",
    re.I,
)
# `RAT63` / `Rat65` / `mouse12` spell the species out; the shared grammar
# (ni_live_discover.ANIMAL_RE) only accepts the single-letter `r`/`m` forms.
# We normalise HERE rather than widening that regex, because it is shared with
# the live-box sync currently sitting at its merge gate — this pull must not
# change how the live path parses anything.
SPECIES_WORD_RE = re.compile(r"\b(rat|rata|mouse|raton|ratón|mice)\s*[_-]?\s*(\d+)", re.I)
# a timepoint level: 0h, 4h, 24h, 30min, 2h30min, d7, day3
TIMEPOINT_RE = re.compile(r"^(\d+\s*h(\s*\d+\s*min)?|\d+\s*min|d\d+|day\s*\d+)$", re.I)
DATE6_RE = re.compile(r"^\d{6}$")
BARE_NUM_RE = re.compile(r"^\d+$")

# --- animal-protocol code validation (tasks/REVIEW_FINDINGS_2026-08-13.md) ---
# An AE code is a regulatory identifier, so it is validated against the facility
# DB rather than trusted from the path. Without this, 114 acquisitions filed
# themselves under an INVENTED code: `2302` is the date folder `230217`, `245`
# and `100` are animal numbers. That contradicted this pull's own rule — 673
# acquisitions are held back precisely because a protocol code must never be
# guessed.
#
# AE_CODE_RE is ANCHORED on the `AE-biomaGUNE-` segment: the project_code
# `AE-biomaGUNE-1317/PRO-AE-SS-101` must yield 1317 and NOT 101. An unanchored
# suffix match is exactly the animal_db bug in §5.4 of the review.
AE_CODE_RE = re.compile(r"AE-biomaGUNE-(\d{3,4})(?![0-9])")
# A candidate must be the WHOLE segment (or its `<code>_…` / `<code>-…` head).
# Matching any digit run inside a segment re-introduces the guessing: it pulls
# `1217` out of the date folder `211217`.
SEG_CODE_RE = re.compile(r"^(\d{3,4})(?:[_-]|$)")

_VALID_CODES = None


def valid_protocol_codes(conn=None):
    """The authoritative set of animal-protocol codes, from the facility DB.

    One query, cached for the process. Raises rather than returning an empty
    set: for a one-time bulk write, refusing to run beats silently reverting to
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


def find_subject(segs_below_researcher):
    """Given the directory names between the researcher folder and the DICOM
    (outermost first), return (subject, series, timepoint, folder_date, notes).

    `subject` is the first non-noise level walking UP from the file.
    """
    notes = []
    timepoint = None
    folder_date = None
    dirs = list(segs_below_researcher)

    # Collect metadata carried by levels we're going to walk past.
    for d in dirs:
        if DATE6_RE.match(d) and folder_date is None:
            folder_date = d

    i = len(dirs) - 1
    while i >= 0:
        d = dirs[i]
        parent = dirs[i - 1] if i >= 1 else ""
        if TIMEPOINT_RE.match(d):
            if timepoint is None:
                timepoint = d
            i -= 1
            continue
        if NOISE_RE.match(d):
            i -= 1
            continue
        # a bare number sitting under a Frames-like level is a frame index
        if BARE_NUM_RE.match(d) and re.match(r"^(frames?|\d+\s*frames?)$", parent or "", re.I):
            i -= 1
            continue
        if DATE6_RE.match(d):
            i -= 1
            continue
        break

    if i < 0:
        notes.append("no-subject-folder")
        return "", None, timepoint, folder_date, notes

    subject = dirs[i]
    # The series is the next level up that is not itself a date/noise level.
    series = None
    j = i - 1
    while j >= 0:
        d = dirs[j]
        if NOISE_RE.match(d) or DATE6_RE.match(d) or TIMEPOINT_RE.match(d):
            j -= 1
            continue
        series = d
        break
    return subject, series, timepoint, folder_date, notes


def _as_date(six, order):
    """Interpret a 6-digit folder name as a date under the given field order."""
    try:
        if order == "YMD":
            y, m, d = 2000 + int(six[0:2]), int(six[2:4]), int(six[4:6])
        else:  # DMY — e.g. `140224` = 14 Feb 2024
            d, m, y = int(six[0:2]), int(six[2:4]), 2000 + int(six[4:6])
        return datetime.date(y, m, d)
    except ValueError:
        return None


def date_flag(machine_ymd, folder_six):
    """Compare the machine timestamp to the typed date folder.

    Both `YYMMDD` and `DDMMYY` are in use here (`140224` is 14 Feb 2024, not
    2014-02-24). Reading everything as YYMMDD produced 19 bogus "10 years off"
    flags, so try both orders and keep the reading that actually agrees — only
    flag when NEITHER does.
    """
    if not folder_six:
        return ""
    try:
        md = datetime.date(int(machine_ymd[:4]), int(machine_ymd[4:6]), int(machine_ymd[6:8]))
    except ValueError:
        return "baddate"
    best = None
    for order in ("YMD", "DMY"):
        fd = _as_date(folder_six, order)
        if fd is None:
            continue
        d = abs((md - fd).days)
        best = d if best is None else min(best, d)
    if best is None:
        return "baddate"
    return "" if best <= 1 else f"date-off-{best}d"


def analyse(rel, size=0, valid_codes=None):
    """One relative path (`<year>/<group>/<researcher>/.../file.dcm`) -> a row dict.

    `valid_codes` is the facility DB's protocol-code set. Pass it for any path
    that writes: without it the project code is whatever the walk-up happened to
    stop on, which on this source is frequently a date or an animal number.
    """
    segs = rel.split("/")
    fn = segs[-1]
    m = DCM_RE.match(fn)
    if not m:
        return None
    g = m.groupdict()
    year = segs[0] if segs else ""
    # <year>/<group>/<researcher>/...   plus the 2022 MOLECUBES extra level
    researcher_idx = 2
    if len(segs) > 3 and segs[2].upper() == "MOLECUBES":
        researcher_idx = 3
    # A DICOM sitting loose at the `<year>/Jesus/` root has no researcher folder
    # at all; without this guard segs[2] IS the filename and the file reports
    # itself as a researcher (three bogus rows in 2023).
    if len(segs) <= researcher_idx + 1:
        researcher, mid, orphan = "", [], True
    else:
        researcher, mid, orphan = segs[researcher_idx], segs[researcher_idx + 1:-1], False

    subject, series, timepoint, folder_date, notes = find_subject(mid)
    if orphan:
        notes.append("loose-at-group-root")
    # Normalise spelled-out species before handing the folder to the shared
    # grammar: `RAT63` -> `r63`, `mouse12` -> `m12`.
    subject_norm = SPECIES_WORD_RE.sub(
        lambda m: ("r" if m.group(1).lower().startswith(("rat", "rata")) else "m") + m.group(2),
        subject,
    )
    p = ni_live_discover.parse_subject(subject_norm, series) if subject else {
        "phantom": False, "project": None, "animals": [], "timepoint": None,
        "flags": ["no-subject-folder"]}

    ts = g["ts"]
    flags = list(p.get("flags") or []) + notes
    df = date_flag(ts[:8], folder_date)
    if df:
        flags.append(df)
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

    keys = [ni_live_discover.facility_id(a["number"], project) for a in p["animals"]]
    keys = [k for k in keys if k]
    return {
        "acq_key": f"{ts}_{g['modality'].upper()}_{g['algo'].upper()}_{int(g['recon'])}",
        "acq_datetime": f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}T{ts[8:10]}:{ts[10:12]}:{ts[12:14]}Z",
        "year_folder": year,
        "researcher": researcher,
        "modality": g["modality"].upper(),
        "algo": g["algo"].upper(),
        "recon": int(g["recon"]),
        "subject_folder": subject,
        "series": series or "",
        "project": project,
        "n_animals": len(p["animals"]),
        "animals": ",".join(a["raw"] for a in p["animals"]),
        "facility_keys": ";".join(keys),
        "timepoint": p.get("timepoint") or timepoint or "",
        "folder_date": folder_date or "",
        "phantom": "yes" if p.get("phantom") else "",
        "flags": ",".join(flags),
        "rel": rel,
        "size_bytes": size,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-plan", help="_plan.csv written by pull_ni_gnuclear.py --plan")
    src.add_argument("--root", help="a staged snapshot directory to walk")
    ap.add_argument("--csv", help="write the full review table here")
    ap.add_argument("--researcher", help="restrict to one researcher folder")
    ap.add_argument("--no-db", action="store_true",
                    help="skip facility-DB validation of protocol codes (offline "
                         "use only — the table then shows PATH-DERIVED codes, "
                         "some of which are dates or animal numbers)")
    args = ap.parse_args(argv)

    valid = None if args.no_db else valid_protocol_codes()

    files = []
    if args.from_plan:
        for r in csv.DictReader(open(args.from_plan, encoding="utf-8")):
            files.append((r["rel"], int(r.get("size_bytes") or 0)))
    else:
        for dirpath, _d, fns in os.walk(args.root):
            for fn in fns:
                if fn.lower().endswith(".dcm"):
                    full = os.path.join(dirpath, fn)
                    rel = os.path.relpath(full, args.root).replace(os.sep, "/")
                    try:
                        files.append((rel, os.path.getsize(full)))
                    except OSError:
                        files.append((rel, 0))

    # One row per ACQUISITION (a reconstruction), not per file.
    acqs = {}
    for rel, size in files:
        row = analyse(rel, size, valid_codes=valid)
        if not row:
            continue
        if args.researcher and row["researcher"].lower() != args.researcher.lower():
            continue
        k = row["acq_key"]
        if k in acqs:
            acqs[k]["n_files"] += 1
            acqs[k]["size_bytes"] += size
        else:
            row["n_files"] = 1
            acqs[k] = row

    rows = [acqs[k] for k in sorted(acqs)]
    print(f"acquisitions (one per reconstruction): {len(rows)}")
    print(f"files                                : {len(files)}")
    print()

    clean = [r for r in rows if not r["flags"]]
    print(f"  parse CLEAN (no flags)  : {len(clean)}  ({100*len(clean)/max(len(rows),1):.0f}%)")
    print(f"  carrying >=1 flag       : {len(rows)-len(clean)}")
    print()
    print("flag histogram (an acquisition can carry several):")
    fc = collections.Counter()
    for r in rows:
        for f in (r["flags"].split(",") if r["flags"] else []):
            fc[f.split(":")[0]] += 1
    for f, c in fc.most_common():
        print(f"  {c:5d}  {f}")

    print()
    print("project resolution:")
    withp = sum(1 for r in rows if r["project"])
    print(f"  {withp} of {len(rows)} acquisitions resolved a project code "
          f"({100*withp/max(len(rows),1):.0f}%)")
    print()
    print("per researcher (acqs / clean / with-project):")
    per = collections.defaultdict(lambda: [0, 0, 0])
    for r in rows:
        k = f"{r['year_folder']}/{r['researcher']}"
        per[k][0] += 1
        if not r["flags"]:
            per[k][1] += 1
        if r["project"]:
            per[k][2] += 1
    for k in sorted(per):
        n, c, p = per[k]
        print(f"  {k:28s} {n:5d} {c:5d} {p:5d}")

    if args.csv:
        cols = ["acq_key", "acq_datetime", "year_folder", "researcher", "modality",
                "algo", "recon", "subject_folder", "series", "project", "n_animals",
                "animals", "facility_keys", "timepoint", "folder_date", "phantom",
                "flags", "n_files", "size_bytes", "rel"]
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow({c: r.get(c, "") for c in cols})
        print(f"\nwrote {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
