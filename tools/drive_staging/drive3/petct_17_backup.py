"""Stream N: the dated, off-NAS backup taken immediately before a write (also the verifier's baseline).

    python petct_17_backup.py <nas_root> <dest_dir> [--empty-raw-linked]

<dest_dir> (must not exist) receives:
  <every file of <nas_root>\\registries\\>      byte copies, each re-hashed against its source
  provenance\\<project>.csv                     the five target projects' provenance.csv
  raw_linked\\<project>.txt                     the names in each target project's raw_linked\\
  BACKUP.txt                                   source, time, size and SHA-256 of every copy
Read-only on <nas_root>. --empty-raw-linked writes empty listings (the rehearsal root started empty).
"""
import datetime
import hashlib
import os
import shutil
import sys

sys.dont_write_bytecode = True
PROJECTS = ["AE-biomaGUNE-0619", "AE-biomaGUNE-0320", "AE-biomaGUNE-1019", "AE-biomaGUNE-1123",
            "AE-biomaGUNE-1422"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    root, dest = sys.argv[1], sys.argv[2]
    empty = "--empty-raw-linked" in sys.argv
    if os.path.exists(dest):
        raise SystemExit(f"{dest} exists: use a fresh, dated directory per write")
    os.makedirs(os.path.join(dest, "provenance"))
    os.makedirs(os.path.join(dest, "raw_linked"))
    lines = [f"backup of {root} taken {datetime.datetime.now().isoformat(timespec='seconds')}"]
    reg = os.path.join(root, "registries")
    for n in sorted(os.listdir(reg)):
        s = os.path.join(reg, n)
        if not os.path.isfile(s) or n == "index.html":
            continue
        d = os.path.join(dest, n)
        h0 = sha(s)
        shutil.copyfile(s, d)
        h1, h2 = sha(d), sha(s)
        if not h0 == h1 == h2:
            raise SystemExit(f"COPY MISMATCH or source changed during copy: {n}")
        lines.append(f"registries/{n} {os.path.getsize(d)} {h1}")
    for p in PROJECTS:
        s = os.path.join(root, "projects", p, "provenance.csv")
        d = os.path.join(dest, "provenance", p + ".csv")
        shutil.copyfile(s, d)
        if sha(s) != sha(d):
            raise SystemExit(f"COPY MISMATCH {s}")
        lines.append(f"provenance/{p}.csv {os.path.getsize(d)} {sha(d)}")
        names = [] if empty else sorted(os.listdir(os.path.join(root, "projects", p, "raw_linked")))
        with open(os.path.join(dest, "raw_linked", p + ".txt"), "w", encoding="utf-8") as f:
            f.write("".join(n + "\n" for n in names))
        lines.append(f"raw_linked/{p}.txt {len(names)} entries")
    with open(os.path.join(dest, "BACKUP.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
