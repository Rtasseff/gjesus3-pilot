"""Stream M: the dated, off-NAS backup taken immediately before a write (also the verifier's baseline).

    python mri_09_backup.py <nas_root> <dest_dir> [<project> ...]

<dest_dir> (must not exist) receives:
  <every file of <nas_root>\\registries\\>      byte copies, each re-hashed against its source (before and after)
  provenance\\<project>.csv                     each target project's provenance.csv (if it has one)
  raw_linked\\<project>.txt                     the names in each target project's raw_linked\\ (empty if no folder yet)
  BACKUP.txt                                   source, time, size and SHA-256 of every copy
Projects default to the six of part 1. Read-only on <nas_root>.
"""
import datetime
import hashlib
import os
import shutil
import sys

PROJECTS = ["AE-biomaGUNE-0118", "AE-biomaGUNE-0619", "AE-biomaGUNE-1019", "AE-biomaGUNE-0320",
            "AE-biomaGUNE-1116", "AE-biomaGUNE-0522"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    root, dest = sys.argv[1], sys.argv[2]
    projects = sys.argv[3:] or PROJECTS
    if os.path.exists(dest):
        raise SystemExit(f"{dest} exists: use a fresh, dated directory per write")
    os.makedirs(os.path.join(dest, "provenance"))
    os.makedirs(os.path.join(dest, "raw_linked"))
    lines = [f"backup of {root} taken {datetime.datetime.now().isoformat(timespec='seconds')}"]
    reg = os.path.join(root, "registries")
    for n in sorted(os.listdir(reg)):
        s = os.path.join(reg, n)
        if not os.path.isfile(s):
            continue
        d = os.path.join(dest, n)
        h0 = sha(s)
        shutil.copyfile(s, d)
        h1, h2 = sha(d), sha(s)
        if not h0 == h1 == h2:
            raise SystemExit(f"COPY MISMATCH or source changed during copy: {n} (another writer? stop)")
        lines.append(f"registries/{n} {os.path.getsize(d)} {h1}")
    for p in projects:
        s = os.path.join(root, "projects", p, "provenance.csv")
        if os.path.exists(s):
            d = os.path.join(dest, "provenance", p + ".csv")
            shutil.copyfile(s, d)
            if sha(s) != sha(d):
                raise SystemExit(f"COPY MISMATCH {s}")
            lines.append(f"provenance/{p}.csv {os.path.getsize(d)} {sha(d)}")
        rl = os.path.join(root, "projects", p, "raw_linked")
        names = sorted(os.listdir(rl)) if os.path.isdir(rl) else []
        with open(os.path.join(dest, "raw_linked", p + ".txt"), "w", encoding="utf-8") as f:
            f.write("".join(n + "\n" for n in names))
        lines.append(f"raw_linked/{p}.txt {len(names)} entries")
    with open(os.path.join(dest, "BACKUP.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
