"""Read LEONE.zip central directory (and nested zips' directories) -> per-folder structure.
Read-only on the staged archive. Writes structure_*.csv into the leone-ingest folder."""
import zipfile, collections, csv, io
Z = "\\\\?\\D:\\projects\\gjesus3\\staging\\drive1_FRIO-X6_2322E4A111E7\\files\\LEONE.zip"
OUT = r"D:\projects\gjesus3\staging\_analysis\leone-ingest"
z = zipfile.ZipFile(Z)
infos = z.infolist()
print("top-level entries", len(infos), "files", sum(not i.is_dir() for i in infos))
lvl = collections.defaultdict(lambda: [0, 0])
lvl3 = collections.defaultdict(lambda: [0, 0])
nested = []
with open(OUT + r"\structure_top.csv", "w", newline="", encoding="utf-8") as g:
    w = csv.writer(g); w.writerow(["path", "size", "compress_size", "is_dir"])
    for i in infos:
        w.writerow([i.filename, i.file_size, i.compress_size, i.is_dir()])
        if i.is_dir():
            continue
        p = i.filename.split("/")
        k2 = "/".join(p[:2]) if len(p) > 2 else i.filename
        k3 = "/".join(p[:3]) if len(p) > 3 else k2
        lvl[k2][0] += 1; lvl[k2][1] += i.file_size
        lvl3[k3][0] += 1; lvl3[k3][1] += i.file_size
        if i.filename.lower().endswith(".zip"):
            nested.append(i)
for k in sorted(lvl):
    print(f"{lvl[k][0]:8d} {lvl[k][1]/1e9:8.2f} GB  {k}")
print()
with open(OUT + r"\structure_level3.csv", "w", newline="", encoding="utf-8") as g:
    w = csv.writer(g); w.writerow(["path", "files", "bytes"])
    for k in sorted(lvl3):
        w.writerow([k, lvl3[k][0], lvl3[k][1]])
print("level3 groups", len(lvl3))
for n in nested:
    print("NESTED", n.filename, n.file_size)
    with z.open(n) as fh:
        data = io.BytesIO(fh.read()) if n.file_size < 4e9 else None
    if data is None:
        print("  too big to buffer"); continue
    zz = zipfile.ZipFile(data)
    ii = zz.infolist()
    c = collections.defaultdict(lambda: [0, 0])
    with open(OUT + "\\structure_nested_" + n.filename.split("/")[-1] + ".csv", "w", newline="", encoding="utf-8") as g:
        w = csv.writer(g); w.writerow(["path", "size", "is_dir"])
        for i in ii:
            w.writerow([i.filename, i.file_size, i.is_dir()])
            if i.is_dir(): continue
            p = i.filename.split("/")
            k = "/".join(p[:2]) if len(p) > 2 else i.filename
            c[k][0] += 1; c[k][1] += i.file_size
    print("  entries", len(ii))
    for k in sorted(c):
        print(f"  {c[k][0]:8d} {c[k][1]/1e9:8.2f} GB  {k}")
