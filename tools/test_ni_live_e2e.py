#!/usr/bin/env python3
"""test_ni_live_e2e.py -- the NI live sync end to end, off the box (2026-10-06).

Runs the real operator command (`tools/operator/ni_ingest.py --live`) as a
subprocess, the way an operator runs it on the Molecubes Mac, against throwaway
copies of everything it touches -- NEVER the production NAS:

  <tmp>/box/irene/<series>/<date>/<subject>/<ts>_<MOD>/   a synthetic Mac tree
  <tmp>/gnuclear/2026/Jesus/Ryan/ni-live-test/tools/      the code, staged the
                                                           way it is on gnuclear
  <tmp>/nas/                                               a scratch gjesus3
  <tmp>/home, <tmp>/systemp                                HOME and TEMP for the
                                                           child process

Production guard: GJESUS3_ROOT is overridden for the child, --nas-root is
always passed, and every run refuses to start unless both sit inside <tmp>.
(A 2026-06-29 "throwaway" verification wrote into production because the
shell's GJESUS3_ROOT pointed there.)

Checks the four on-box merge gates as far as Windows allows, plus the rules for
working on the Mac (RESUME_ni_live.md, top):

  --plan     appends one corrections row per session to the file resolve_path
             finds from the staged code's own path; writes nothing else.
  --dry-run  writes nothing anywhere.
  --go       gate 1: one registry row per reconstruction (`.../recon_N`);
             gate 2: the corrected session routes to the corrected project
                     with a `session_extra` block, original_name uncorrected;
  re-sync    gate 4: 0 new; a late recon_2 registers into the corrected session
                     with the correction applied and nothing re-entered; the
                     corrections file is never modified by --go.
  ENOTSUP    gate 3 (simulated): with os.link raising ENOTSUP, as on macOS over
             SMB, every acquisition is still registered and its project link is
             queued to registries/pending_links.csv.
  always     the source tree is never written; nothing lands in HOME or TEMP;
             nothing is written next to the staged code.

Run:  python tools/test_ni_live_e2e.py          (add -v to print every run's output)
"""
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ingest import projects_registry, registry  # noqa: E402

VERBOSE = "-v" in sys.argv
FAILED = []


def check(cond, msg):
    print(f"  {'ok' if cond else 'FAIL'}:   {msg}")
    if not cond:
        FAILED.append(msg)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def snapshot(root, skip=()):
    """{relpath: sha256} for every file under root (skipping the given top-level paths)."""
    out = {}
    if not os.path.isdir(root):
        return out
    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if os.path.join(r, d) not in skip]
        for fn in files:
            p = os.path.join(r, fn)
            if p in skip:
                continue
            with open(p, "rb") as f:
                out[os.path.relpath(p, root)] = hashlib.sha256(f.read()).hexdigest()
    return out


# ------------------------------------------------------------------ fixtures

PROTOCOL = "Scan bed position from 0 to 100\n"


def add_acquisition(box, rel, recons):
    """<box>/<rel>/ with protocol.txt and one DICOM per recon_<idx>/ (CT layout)."""
    acq = os.path.join(box, *rel.split("/"))
    write(os.path.join(acq, "protocol.txt"), PROTOCOL)
    for idx in recons:
        write(os.path.join(acq, f"recon_{idx}", f"img_{idx}.dcm"), f"DCM-{rel}-{idx}")
    return acq


def build_world(tmp):
    w = {
        "tmp": tmp,
        "box": os.path.join(tmp, "box", "irene"),
        "staged": os.path.join(tmp, "gnuclear", "2026", "Jesus", "Ryan", "ni-live-test"),
        "nas": os.path.join(tmp, "nas"),
        "home": os.path.join(tmp, "home"),
        "systemp": os.path.join(tmp, "systemp"),
    }
    # The code, staged the way it is on gnuclear (no caches).
    shutil.copytree(_HERE, os.path.join(w["staged"], "tools"),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # gnuclear spells the researcher folder its own way; resolve_path must find it.
    os.makedirs(os.path.join(tmp, "gnuclear", "2026", "Jesus", "Irene"))
    # Session A: CT with two recons, REMI says project 0324 (wrong; really 0325).
    add_acquisition(w["box"], "1207/260212/0324_m61/20260212130722_CT", [0, 1])
    # Session B: CT, one recon, no correction.
    add_acquisition(w["box"], "1207/260213/0324_m62/20260213101500_CT", [0])
    # A scratch NAS: just the two registries with their headers.
    reg = os.path.join(w["nas"], "registries")
    os.makedirs(reg)
    os.makedirs(os.path.join(w["nas"], "raw"))
    with open(os.path.join(reg, "registry_raw.csv"), "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(registry.REGISTRY_FIELDS)
    with open(os.path.join(reg, "registry_projects.csv"), "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(projects_registry.PROJECT_REGISTRY_FIELDS)
    os.makedirs(w["home"])
    os.makedirs(w["systemp"])
    return w


ENOTSUP_SHIM = '''\
import errno, os
def _no_hardlinks(src, dst, *a, **k):
    raise OSError(errno.ENOTSUP, "Operation not supported (simulated macOS SMB)", dst)
os.link = _no_hardlinks
'''


def run(w, *args, shim=None):
    """Run ni_ingest.py from the staged copy, like an operator on the Mac."""
    nas = w["nas"]
    tmp = os.path.abspath(w["tmp"])
    assert os.path.abspath(nas).startswith(tmp), "refusing: NAS root outside the scratch dir"
    env = dict(os.environ)
    env.update({
        "GJESUS3_ROOT": nas,                      # never the shell's (production) value
        "GJESUS3_MYCNF": os.path.join(tmp, "no-such.cnf"),  # no animal-DB lookups
        "HOME": w["home"], "USERPROFILE": w["home"],
        "TMPDIR": w["systemp"], "TEMP": w["systemp"], "TMP": w["systemp"],
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    tools = os.path.join(w["staged"], "tools")
    env["PYTHONPATH"] = os.pathsep.join(([shim] if shim else []) + [tools])
    assert os.path.abspath(env["GJESUS3_ROOT"]).startswith(tmp)
    cmd = [sys.executable, os.path.join(tools, "operator", "ni_ingest.py"), w["box"],
           "--live", "--nas-root", nas, "--no-prompt", *args]
    p = subprocess.run(cmd, cwd=w["staged"], env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    out = p.stdout + p.stderr
    if VERBOSE or p.returncode != 0:
        print(f"    --- ni-ingest {' '.join(args)} (exit {p.returncode}) ---")
        for line in out.splitlines():
            print("    | " + line)
    return p.returncode, out


def raw_rows(nas):
    with open(os.path.join(nas, "registries", "registry_raw.csv"), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def project_name(nas, row):
    """The project NAME a registry row points at (the row holds a PROJ-NNNN id)."""
    with open(os.path.join(nas, "registries", "registry_projects.csv"), encoding="utf-8",
              newline="") as f:
        names = {r["project_id"]: r["name"] for r in csv.DictReader(f)}
    return names.get(row["project_id"], row["project_id"])


def sidecar(nas, row):
    hits = []
    for r, _d, files in os.walk(os.path.join(nas, "raw")):
        if os.path.basename(r) == row["acq_id"] and "metadata.json" in files:
            hits.append(os.path.join(r, "metadata.json"))
    if len(hits) != 1:
        return {}
    with open(hits[0], encoding="utf-8") as f:
        return json.load(f)


def outside_writes(w, before, corr_path):
    """Files that appeared or changed anywhere except the NAS and the corrections file."""
    skip = {w["nas"], corr_path}
    after = snapshot(w["tmp"], skip=skip)
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


# ------------------------------------------------------------------ scenario

def main_flow(tmp):
    w = build_world(tmp)
    corr_path = os.path.join(tmp, "gnuclear", "2026", "Jesus", "Irene", "ni_corrections_irene.csv")
    box0 = snapshot(w["box"])

    print("--plan: one corrections row per session, nothing else written")
    before = snapshot(tmp, skip={w["nas"], corr_path})
    nas0 = snapshot(w["nas"])
    rc, out = run(w, "--plan")
    check(rc == 0, "--plan exits 0")
    check(corr_path in out or corr_path.replace("\\", "/") in out.replace("\\", "/"),
          "the resolved corrections path is printed (gnuclear/2026/Jesus/Irene, found case-insensitively)")
    check(os.path.isfile(corr_path), "corrections file created under the researcher's gnuclear folder")
    with open(corr_path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    check(sorted(r["session_path"] for r in rows) ==
          ["1207/260212/0324_m61", "1207/260213/0324_m62"], "one row per session, keyed by the raw path")
    check(snapshot(w["nas"]) == nas0, "--plan wrote nothing to the NAS")
    check(outside_writes(w, before, corr_path) == [], "--plan wrote nothing else (box, code dir, HOME, TEMP)")

    print("--dry-run: nothing written anywhere")
    before = snapshot(tmp)
    rc, out = run(w, "--dry-run")
    check(rc == 0, "--dry-run exits 0")
    check(snapshot(tmp) == before, "--dry-run changed no file anywhere")

    # The operator fixes session A: REMI said 0324, the animals are on 0325; adds the tracer.
    for r in rows:
        if r["session_path"] == "1207/260212/0324_m61":
            r["project"] = "0325"
            r["extra_metadata"] = "tracer=FDG;dose=10 MBq"
    with open(corr_path, "w", encoding="utf-8", newline="") as f:
        dw = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        dw.writeheader()
        dw.writerows(rows)
    corr_hash = snapshot(os.path.dirname(corr_path))

    print("--go: gate 1 (one row per recon) and gate 2 (correction + session_extra)")
    before = snapshot(tmp, skip={w["nas"], corr_path})
    rc, out = run(w, "--go")
    check(rc == 0, "--go exits 0")
    reg = raw_rows(w["nas"])
    names = sorted(r["original_name"] for r in reg)
    check(len(reg) == 3, f"3 acquisitions registered (got {len(reg)})")
    check(all(n.rsplit("/", 1)[-1].startswith("recon_") for n in names),
          "every original_name ends in /recon_<idx>")
    a_rows = [r for r in reg if "0324_m61" in r["original_name"]]
    b_rows = [r for r in reg if "0324_m62" in r["original_name"]]
    check(len(a_rows) == 2 and len(b_rows) == 1, "session A: 2 recons, session B: 1")
    check(all(project_name(w["nas"], r) == "AE-biomaGUNE-0325" for r in a_rows),
          "session A routed to the CORRECTED project AE-biomaGUNE-0325")
    check(all(project_name(w["nas"], r) == "AE-biomaGUNE-0324" for r in b_rows),
          "session B kept its own project AE-biomaGUNE-0324")
    check(all("0324_m61" in r["original_name"] for r in a_rows),
          "original_name keeps the UNCORRECTED REMI path (the sync key)")
    sa = sidecar(w["nas"], a_rows[0]) if a_rows else {}
    sb = sidecar(w["nas"], b_rows[0]) if b_rows else {}
    check(sa.get("session_extra") == {"tracer": "FDG", "dose": "10 MBq"},
          f"session A sidecar has session_extra (got {sa.get('session_extra')!r})")
    check("session_extra" not in sb, "session B sidecar has no session_extra")
    check(outside_writes(w, before, corr_path) == [], "--go wrote nothing outside the NAS")
    check(snapshot(os.path.dirname(corr_path)) == corr_hash, "--go did not modify the corrections file")

    print("re-sync: gate 4 (idempotent; a late recon inherits the correction)")
    rc, out = run(w, "--go")
    check(rc == 0, "second --go exits 0")
    check(len(raw_rows(w["nas"])) == 3, "second --go registered 0 new acquisitions")
    late = os.path.join(w["box"], "1207", "260212", "0324_m61", "20260212130722_CT")
    write(os.path.join(late, "recon_2", "img_2.dcm"), "DCM-late-2")   # the scanner writes recon_2 later
    box0 = snapshot(w["box"])
    rc, out = run(w, "--go")
    reg = raw_rows(w["nas"])
    new = [r for r in reg if r["original_name"].endswith("/recon_2")]
    check(rc == 0 and len(reg) == 4 and len(new) == 1, "the late recon_2 registered as one new acquisition")
    check(bool(new) and project_name(w["nas"], new[0]) == "AE-biomaGUNE-0325",
          "the late recon landed in the CORRECTED project, nothing re-entered")
    check(bool(new) and sidecar(w["nas"], new[0]).get("session_extra") == {"tracer": "FDG", "dose": "10 MBq"},
          "the late recon carries the session's tracer metadata")
    check(snapshot(os.path.dirname(corr_path)) == corr_hash, "the corrections file is still untouched")
    check(snapshot(w["box"]) == box0, "the source (box) tree was never written")
    check(os.listdir(w["home"]) == [] and os.listdir(w["systemp"]) == [], "HOME and TEMP are still empty")


def enotsup_flow(tmp):
    print("gate 3 (simulated): os.link -> ENOTSUP, as on macOS over SMB")
    w = build_world(tmp)
    shim = os.path.join(tmp, "shim")
    write(os.path.join(shim, "sitecustomize.py"), ENOTSUP_SHIM)
    corr = os.path.join(tmp, "corr_test.csv")      # the --corrections override a test run uses
    rc, out = run(w, "--go", "--corrections", corr, shim=shim)
    check(rc == 0, "--go exits 0 with hard links unavailable")
    check(len(raw_rows(w["nas"])) == 3, "all 3 acquisitions still registered")
    pl = os.path.join(w["nas"], "registries", "pending_links.csv")
    check(os.path.isfile(pl), "registries/pending_links.csv written")
    if os.path.isfile(pl):
        with open(pl, encoding="utf-8", newline="") as f:
            prow = list(csv.DictReader(f))
        check(len(prow) == 3, f"one queued link per acquisition (got {len(prow)})")
        check(all("ENOTSUP" in json.dumps(r) or "not supported" in json.dumps(r).lower() for r in prow),
              "each queued row records the ENOTSUP reason")
    check(not os.path.exists(corr), "--go without --plan did not create the corrections file")
    check(os.listdir(w["home"]) == [] and os.listdir(w["systemp"]) == [], "HOME and TEMP are still empty")


def main():
    with tempfile.TemporaryDirectory(prefix="ni_live_e2e_") as tmp:
        main_flow(os.path.join(tmp, "a"))
    with tempfile.TemporaryDirectory(prefix="ni_live_e2e_") as tmp:
        enotsup_flow(os.path.join(tmp, "b"))
    if FAILED:
        print(f"\n{len(FAILED)} CHECK(S) FAILED")
        sys.exit(1)
    print("\nALL NI LIVE E2E CHECKS PASSED")


if __name__ == "__main__":
    main()
