"""Sequential member scan of one big zip: one reader (members in on-disk order,
so the disk streams instead of seeking) feeding a process pool that hashes and
parses DICOM headers. Recurses into nested .zip members. Same output columns as
scan_zip_members.py. Read-only on the archive.

usage: python scan_zip_sequential.py <zip> <out_prefix> --label L [--procs N]
"""
import argparse, csv, hashlib, io, sys, time, zipfile
from multiprocessing import Pool
from scan_zip_members import parse, TAGS, ID_TAGS


def work(item):
    name, data, note = item
    if data is None:
        return name, 0, "", None, note
    sha = hashlib.sha256(data).hexdigest()
    d = None if note else parse(data)
    return name, len(data), sha, d, note


def gen(zpath, nested_sink):
    zf = zipfile.ZipFile(zpath)
    infos = sorted((i for i in zf.infolist() if not i.is_dir()), key=lambda i: i.header_offset)
    for zi in infos:
        try:
            with zf.open(zi) as fh:
                data = fh.read()
        except Exception as e:
            yield zi.filename, None, "READ_ERROR:" + repr(e)[:200]
            continue
        if zi.filename.lower().endswith(".zip"):
            yield zi.filename, data, "NESTED_ZIP"
            try:
                nz = zipfile.ZipFile(io.BytesIO(data))
                for ni in nz.infolist():
                    if ni.is_dir():
                        continue
                    try:
                        yield zi.filename + "!/" + ni.filename, nz.read(ni), ""
                    except Exception as e:
                        yield zi.filename + "!/" + ni.filename, None, "READ_ERROR:" + repr(e)[:200]
            except Exception as e:
                yield zi.filename, None, "NESTED_OPEN_ERROR:" + repr(e)[:200]
            continue
        yield zi.filename, data, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zip"); ap.add_argument("out_prefix")
    ap.add_argument("--label", default=""); ap.add_argument("--procs", type=int, default=6)
    a = ap.parse_args()
    t0 = time.time()
    f = open(a.out_prefix + ".csv", "w", newline="", encoding="utf-8")
    g = open(a.out_prefix + "_identifiers.csv", "w", newline="", encoding="utf-8")
    w = csv.writer(f); wi = csv.writer(g)
    w.writerow(["container", "member", "size", "sha256", "is_dicom", "note"] + TAGS)
    wi.writerow(["container", "member", "SOPInstanceUID"] + ID_TAGS)
    n = [0, 0, 0]; nbytes = 0
    with Pool(a.procs) as pool:
        for name, size, sha, d, note in pool.imap(work, gen(a.zip, None), chunksize=16):
            n[0] += 1; nbytes += size
            if d:
                n[1] += 1
                w.writerow([a.label, name, size, sha, 1, note] + [d.get(t, "") for t in TAGS])
                wi.writerow([a.label, name, d["SOPInstanceUID"]] + [d.get(t, "") for t in ID_TAGS])
            else:
                if note.startswith(("READ_ERROR", "NESTED_OPEN_ERROR")):
                    n[2] += 1
                w.writerow([a.label, name, size, sha, 0, note] + [""] * len(TAGS))
            if n[0] % 20000 == 0:
                f.flush(); g.flush()
                print(f"{a.label}: {n[0]} members, {n[1]} dicom, {n[2]} errors, "
                      f"{nbytes/1e9:.1f} GB, {time.time()-t0:.0f}s", flush=True)
    f.close(); g.close()
    print(f"DONE {a.label}: {n[0]} members, {n[1]} dicom, {n[2]} errors, {nbytes/1e9:.1f} GB, {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
