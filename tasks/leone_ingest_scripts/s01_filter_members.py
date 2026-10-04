"""Filter the catalog's archive_members.csv to LEONE.zip members (read-only on the catalog)."""
import csv, collections, sys
SRC = r"D:\projects\gjesus3\staging\_analysis\catalog\archive_members.csv"
DST = r"D:\projects\gjesus3\staging\_analysis\leone-ingest\leone_members.csv"
csv.field_size_limit(10**8)
n = 0
arch = collections.Counter()
with open(SRC, encoding="utf-8", newline="") as f, open(DST, "w", encoding="utf-8", newline="") as g:
    r = csv.reader(f)
    w = csv.writer(g)
    hdr = next(r)
    w.writerow(hdr)
    for row in r:
        if "leone" in row[1].lower():
            w.writerow(row); n += 1; arch[(row[0], row[1])] += 1
print("members", n)
for k, v in arch.most_common():
    print(v, k)
with open(r"D:\projects\gjesus3\staging\_analysis\catalog\archives.csv", encoding="utf-8") as f:
    for line in f:
        if "leone" in line.lower() or line.startswith("drive"):
            print(line.rstrip())
