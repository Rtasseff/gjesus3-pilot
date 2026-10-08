#!/usr/bin/env python3
"""c_prod_delta.py -- stream C (drive 3): what production gained after the coordinator's 10:30 hash index,
proved covered by this stream's checks. READ-ONLY on J:\\ (registries, checksums.json, .czi headers).

The coordinator's index (D:\\projects\\gjesus3\\drive3_analysis\\prod_raw_sha256.csv, built 2026-10-06 10:30)
predates an operator GUI ingest of 11:03-11:21 the same day. This stream never used that index: its plan,
its checks and every production batch's step 0 read a stream-built index (`catalog.py production --out
<stream>\\catalog`: every LIVE checksums.json) and the LIVE registry_raw.csv. This script proves it:

  1. the live registry now: rows and mtime; the rows the 10:30 index lacks (by instrument, config, time);
  2. the stream's index holds every one of them, and each acquisition's checksums.json, re-read now,
     equals its rows there; the index is newer than the registry;
  3. instrument: each such microscopy row's primary .czi header, read now, fingerprinted by device serial
     (tools/reference/microscopy_instruments.yaml, the catalog's rule), and the catalog's sidecar audit row;
  4. drive 3: none of their SHA-256 is any drive-3 file's (the whole manifest); none shares an (instrument,
     second) with a planned file; none shares a (second, name) with any drive-3 .czi, under any instrument.

    python tools/drive_staging/drive3/c_prod_delta.py     # -> <stream>\\plan\\prod_delta.txt (+ printed)
"""
import collections
import csv
import datetime as dt
import io
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.dirname(HERE)
sys.path.insert(0, DS)
import ingest_plan as P  # noqa: E402
import catalog  # noqa: E402

P.use_profile("drive3_2026-10")
COORD_INDEX = os.path.join(P.D3_ANALYSIS, "prod_raw_sha256.csv")
COORD_BUILT = dt.datetime(2026, 10, 6, 10, 30)


def rd(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    L = []

    def say(m=""):
        L.append(m)
        print(m, flush=True)

    reg_path = os.path.join(P.NAS, "registries", "registry_raw.csv")
    reg = rd(reg_path)
    reg_mtime = dt.datetime.fromtimestamp(os.path.getmtime(reg_path))
    say(f"1. live registry_raw.csv: {len(reg):,} rows, modified {reg_mtime:%Y-%m-%d %H:%M:%S}")
    coord_acq = {r["acq_id"] for r in rd(COORD_INDEX)}
    absent = [r for r in reg if r["acq_id"] not in coord_acq]
    hashed_absent = [r for r in absent if r["checksum_present"] == "Y" and r["file_count"] not in ("", "0")]
    say(f"   rows the 10:30 index lacks: {len(absent):,}; of them with checksummed files: {len(hashed_absent)}")
    for k, n in collections.Counter((r["instrument"], r["ingest_config"], r["registration_datetime"][:13])
                                    for r in hashed_absent).most_common():
        say(f"     {n:4d}  {k}")
    empty = collections.Counter(r["instrument"] for r in absent if r not in hashed_absent)
    say(f"   the rest hold no hashed file (empty checksums.json): {dict(empty)}")
    new = hashed_absent

    ph_path = os.path.join(P.CAT, "production_hashes.csv")
    ph = collections.defaultdict(dict)
    for r in rd(ph_path):
        ph[r["acq_id"]][r["file"]] = r["sha256"]
    ph_mtime = dt.datetime.fromtimestamp(os.path.getmtime(ph_path))
    say(f"2. the stream's index {ph_path}: built {ph_mtime:%Y-%m-%d %H:%M:%S}, "
        f"{sum(len(v) for v in ph.values()):,} hashes of {len(ph):,} acquisitions; "
        f"{'NEWER' if ph_mtime > reg_mtime else 'OLDER'} than the registry")
    missing, differ = [], []
    for r in new:
        p = os.path.join(P.NAS, r["canonical_path"].strip("/").replace("/", "\\"), "checksums.json")
        with io.open(p, encoding="utf-8") as f:
            live = json.load(f).get("files", {})
        if r["acq_id"] not in ph:
            missing.append(r["acq_id"])
        elif ph[r["acq_id"]] != live:
            differ.append(r["acq_id"])
    say(f"   of the {len(new)}: {len(new) - len(missing)} in the stream's index, {len(missing)} missing; "
        f"checksums.json re-read now differs from the index for {len(differ)}")

    ref = catalog.load_instruments()
    audit = {}
    ap = os.path.join(P.CAT, "production_instrument_audit.csv")
    if os.path.isfile(ap):
        audit = {r["acq_id"]: r for r in rd(ap)}
    fp_count = collections.Counter()
    say("3. instrument, from each primary's own .czi header (read now) and the catalog's sidecar audit:")
    for r in new:
        if r["data_ecosystem"] != "MICROSCOPY":
            fp_count[("not microscopy", r["instrument"])] += 1
            continue
        prim = os.path.join(P.NAS, r["canonical_path"].strip("/").replace("/", "\\"), r["primary_file_name"])
        xml, err = catalog.czi_read_xml(prim)
        if xml is None:
            fp_count[("unreadable header", err)] += 1
            continue
        p = catalog.parse_czi_xml(xml)
        inst, rule, _ = catalog.fingerprint(ref, p["serials"], p["keys"], p["stand"])
        a = audit.get(r["acq_id"], {})
        fp_count[(f"registry {r['instrument']}", f"header {inst} by {rule}",
                  f"audit {a.get('fingerprint_instrument', '?')} agree={a.get('agree', '?')}")] += 1
    for k, n in fp_count.most_common():
        say(f"     {n:4d}  {k}")

    man = P.load_manifest(P.MANIFEST)
    d3_sha = {m["sha256"] for m in man.values()}
    new_sha = {s for r in new for s in ph.get(r["acq_id"], {}).values()}
    plan = rd(os.path.join(P.OUT, "expected.csv"))
    plan_keys = {(e["instrument"], e["acquisition_datetime"][:19]) for e in plan}
    a1 = rd(P.A1_FILES)
    a1_keys = {(r["acq_dt"][:19], r["relpath"].split("\\")[-1].lower()) for r in a1 if r["ext"] == ".czi"}
    a1_secs = collections.Counter(r["acq_dt"][:19] for r in a1 if r["ext"] == ".czi")
    sha_hit = new_sha & d3_sha
    key_hit = [r["acq_id"] for r in new if (r["instrument"], r["acquisition_datetime"][:19]) in plan_keys]
    name_hit = [r["acq_id"] for r in new
                if (r["acquisition_datetime"][:19], P._base(r["original_name"])) in a1_keys]
    sec_hit = [r["acq_id"] for r in new if a1_secs.get(r["acquisition_datetime"][:19])]
    say(f"4. against drive 3: {len(sha_hit)} of their {len(new_sha)} SHA-256 are drive-3 files "
        f"(the {len(man):,}-file manifest); {len(key_hit)} share an (instrument, second) with the "
        f"{len(plan):,} planned files; {len(name_hit)} share a (second, name) with any of the "
        f"{sum(1 for r in a1 if r['ext'] == '.czi'):,} drive-3 .czi; {len(sec_hit)} share a second with any of them")
    ok = not missing and not differ and ph_mtime > reg_mtime and not sha_hit and not key_hit and not name_hit
    say(f"RESULT: {'PASS' if ok else 'FAIL'} -- the change is in the stream's index and touches no planned file")
    with io.open(os.path.join(P.OUT, "prod_delta.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
