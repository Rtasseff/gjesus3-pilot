"""Privacy grep: count occurrences of any PatientName / PatientBirthDate value (from the scan's
identifier file) in the given text files. Prints COUNTS ONLY -- never a value.

  python s13_privacy_grep.py <file> [<file> ...]
"""
import csv, io, re, sys

IDS = r"D:\projects\gjesus3\staging\_analysis\leone-ingest\scan\leone_identifiers.csv"
# Measured 2026-10-04: every PatientName in LEONE and DTS24 is the cohort label ("LEONE", or a
# LEONE/HPIC case-style label), not a person's name. Such labels are not needles (they are also the
# pseudonymous case ids we deliberately write); anything else would be.
LABEL = re.compile(r"(?i)(leone|hpic)[ _.\-^]*[0-9.,]*( ?s?[0-9]*)?\^?")


def needles():
    names, dobs = set(), set()
    with io.open(IDS, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            n = (r.get("PatientName") or "").strip()
            if n and not LABEL.fullmatch(n):
                names.add(n.lower())
                for part in re.split(r"[\^ ]+", n):          # DICOM PN components, each >= 4 chars
                    if len(part) >= 4:
                        names.add(part.lower())
            d = (r.get("PatientBirthDate") or "").strip()
            if len(d) == 8 and d.isdigit():
                dobs.update({d, f"{d[:4]}-{d[4:6]}-{d[6:]}", f"{d[6:]}/{d[4:6]}/{d[:4]}"})
    return names, dobs


def main(paths):
    names, dobs = needles()
    print(f"needles: {len(names)} name strings, {len(dobs)} DOB strings")
    total = 0
    for p in paths:
        text = io.open(p, encoding="utf-8-sig", errors="replace").read().lower()
        hn = sum(1 for n in names if n in text)
        hd = sum(1 for d in dobs if d in text)
        total += hn + hd
        print(f"{p}: name hits {hn}, DOB hits {hd}")
    print("PRIVACY GREP", "CLEAN" if total == 0 else f"HITS={total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
