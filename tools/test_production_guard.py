#!/usr/bin/env python3
"""test_production_guard.py -- a real CLI run against the production root needs --production (#14, decision 16).

Against throwaway folders (never the NAS):
  * marker present, real run, no flag: refused with exit 2, nothing registered;
  * marker present, --dry-run: not refused;
  * marker present, --production: the case is registered;
  * no marker: an ordinary real run works without the flag;
  * run_batch called directly (the path the GUIs, mri-ingest and ni-ingest use) is unaffected by the marker.
"""
import contextlib
import csv
import io
import os
import subprocess
import sys
import tempfile

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ingest import projects_registry, provenance, registry  # noqa: E402

FAILED = []


def check(cond, msg):
    print(f"  {'ok:  ' if cond else 'FAIL:'} {msg}")
    if not cond:
        FAILED.append(msg)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def build_nas(root, marker):
    reg = os.path.join(root, "registries")
    os.makedirs(reg)
    os.makedirs(os.path.join(root, "raw"))
    with open(os.path.join(reg, "registry_raw.csv"), "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(registry.REGISTRY_FIELDS)
    with open(os.path.join(reg, "registry_projects.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(projects_registry.PROJECT_REGISTRY_FIELDS)
        w.writerow(["PROJ-0001", "alpha", "", "RT", "2026-05-01", "active", "2026-05-01", "/projects/alpha/", ""])
    os.makedirs(os.path.join(root, "projects", "alpha", "raw_linked"))
    provenance.write_empty(os.path.join(root, "projects", "alpha", "provenance.csv"))
    if marker:
        write(os.path.join(reg, ".production"), b"production\n")


def batch_cfg(staging, name):
    write(os.path.join(staging, name), name.encode())
    return {
        "ingest": {"delete_source_after_ingest": False, "auto_create_projects": False},
        "auto_discover": {"staging_dir": staging, "pattern": "*.tif"},
        "registry": {
            "instrument": "ZWSI", "data_ecosystem": "MICROSCOPY", "instrument_model": "NA",
            "modalities_in_study": "NA", "researcher": "RT", "data_source": "internal",
            "sample_id": "S1", "sample_type": "NA", "acquisition_datetime": "2026-03-03",
            "project_name": "alpha", "notes": "NA",
        },
        "operator": "RT",
        "link_filename": name,
    }


def rows(root):
    return registry.read_registry(os.path.join(root, "registries", "registry_raw.csv"))


def cli(root, cfg, *flags):
    path = os.path.join(root, "_cfg.yaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, os.path.join(_HERE, "ingest_raw.py"), "--config", path,
                        "--nas-root", root, *flags],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=_HERE, timeout=300)
    return p.returncode, p.stdout + p.stderr


def main():
    print("[the production guard]")
    with tempfile.TemporaryDirectory() as d:
        root = os.path.join(d, "nas")
        build_nas(root, marker=True)
        rc, out = cli(root, batch_cfg(os.path.join(d, "st1"), "a.tif"))
        check(rc == 2 and "PRODUCTION data root" in out, f"marker, real run, no flag: refused, exit 2 (got {rc})")
        check(rows(root) == [], "...and nothing is registered")
        check(not os.listdir(os.path.join(root, "raw")), "...and nothing is copied")

        rc, out = cli(root, batch_cfg(os.path.join(d, "st2"), "b.tif"), "--dry-run")
        check(rc == 0 and "PRODUCTION data root" not in out, f"marker, --dry-run: not refused (got {rc})")
        check(rows(root) == [], "...and a dry run registers nothing")

        rc, out = cli(root, batch_cfg(os.path.join(d, "st3"), "c.tif"), "--production")
        check(rc == 0 and len(rows(root)) == 1, f"marker, --production: one case registered (rc {rc}, "
                                                 f"rows {len(rows(root))})")

    with tempfile.TemporaryDirectory() as d:
        root = os.path.join(d, "nas")
        build_nas(root, marker=False)
        rc, out = cli(root, batch_cfg(os.path.join(d, "st"), "d.tif"))
        check(rc == 0 and len(rows(root)) == 1, f"no marker: an ordinary real run works (rc {rc})")
        rc, out = cli(root, batch_cfg(os.path.join(d, "st2"), "e.tif"), "--production")
        check(rc == 0 and "no registries/.production marker" in out, "no marker, --production: a WARN, then it runs")

    print("[run_batch directly: the GUI / mri-ingest / ni-ingest path]")
    import ingest_raw
    with tempfile.TemporaryDirectory() as d:
        root = os.path.join(d, "nas")
        build_nas(root, marker=True)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            res = ingest_raw.run_batch(batch_cfg(os.path.join(d, "st"), "f.tif"), root)
        check([ok for _a, ok in res] == [True] and len(rows(root)) == 1,
              "run_batch on a marked root registers as before")
    check(ingest_raw.is_production_root(root) is False, "is_production_root is False once the folder is gone")

    print()
    if FAILED:
        print(f"FAILED ({len(FAILED)}):")
        for m in FAILED:
            print(f"  - {m}")
        return 1
    print("ALL PASS (production guard)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
