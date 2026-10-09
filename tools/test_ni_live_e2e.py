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
  terminal   in-process, with stdin made to look like a real terminal: live mode
             asks no metadata question, only the final 'Proceed? [y/N]'.
  x-source   a reconstruction already registered from another source (a flat
             S:\\gnuclear-pull row, a platform-archive bundle) is not ingested again;
             a reconstruction that source never had still is.
  derived    a CT attenuation map (recon_<n>/ATTMAP.dcm) gets no ACQ-ID: it is copied to
             <project>/outputs/derived/, recorded in provenance with the scan's ACQ-IDs, and
             waits while nothing of its scan is registered; a re-sync adds nothing.

Run:  python tools/test_ni_live_e2e.py          (add -v to print every run's output)
"""
import builtins
import contextlib
import csv
import hashlib
import importlib.util
import io
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


def cross_source_flow(tmp):
    """Scans already loaded from ANOTHER source are not loaded again from the box.

    Seeds the registry with rows shaped like production's (2026-10-08): a flat
    S:\\gnuclear-pull row naming its reconstruction (`<ts>_<MOD>_<ALGO>_<n>`) and a
    platform-archive bundle row naming none. The box holds session A (recon_0,
    recon_1) and session B (recon_0).
    """
    print("cross-source: what another source already loaded is not loaded again")
    w = build_world(tmp)
    reg = os.path.join(w["nas"], "registries", "registry_raw.csv")
    seed = [
        {"acq_id": "ACQ-SEED-PULL", "acquisition_datetime": "2026-02-12T13:07:22Z",
         "instrument": "CT", "data_ecosystem": "DICOM",
         "original_name": "20260212130722_CT_ISRA_0"},           # A's recon_0, from the pull
        {"acq_id": "ACQ-SEED-ARCHIVE", "acquisition_datetime": "2026-02-13T10:15:00Z",
         "instrument": "CT", "data_ecosystem": "DICOM",
         "original_name": "irene_1207_260213_0324_m62_20260213101500_CT"},  # B, archive bundle
    ]
    with open(reg, "a", encoding="utf-8", newline="") as f:
        dw = csv.DictWriter(f, fieldnames=registry.REGISTRY_FIELDS)
        for r in seed:
            dw.writerow({k: r.get(k, "") for k in registry.REGISTRY_FIELDS})
    corr = os.path.join(tmp, "corr_xs.csv")

    rc, out = run(w, "--plan", "--corrections", corr)
    with open(corr, encoding="utf-8", newline="") as f:
        sessions = sorted(r["session_path"] for r in csv.DictReader(f))
    check(rc == 0 and sessions == ["1207/260212/0324_m61"],
          f"--plan lists only the session with something new (got {sessions})")
    rc, out = run(w, "--dry-run", "--corrections", corr)
    check(rc == 0 and "1 new acquisition(s) to ingest; 2 already ingested (skipped)" in out,
          "the preview summary counts them as already ingested (not '0 skipped')")
    rc, out = run(w, "--go", "--corrections", corr)
    new = [r for r in raw_rows(w["nas"]) if not r["acq_id"].startswith("ACQ-SEED")]
    names = sorted(r["original_name"] for r in new)
    check(rc == 0 and names == ["1207/260212/0324_m61/20260212130722_CT/recon_1"],
          f"only A's recon_1 is ingested; A's recon_0 and all of B are not (got {names})")
    check(out.count("already in registry (from another source") == 2,
          "each skip says why, in the line shape every ingest uses")


def derived_flow(tmp):
    """CT attenuation maps are derived files: project outputs/derived/, provenance, never /raw/.

    Session A's CT gains recon_2/ATTMAP.dcm (the box's layout: alone in its recon folder). A
    third session holds ONLY an attenuation map, so nothing of its scan is registered and the
    file must wait rather than be placed with no raw to point at.
    """
    print("derived files: an attenuation map goes to the project, not to /raw/")
    from ingest import ni_derived
    check(ni_derived.attenuation_map_files({"dicoms": [{"src_relpath": "recon_2/ATTMAP.dcm"}]})
          == ["recon_2/ATTMAP.dcm"], "a recon folder holding only ATTMAP.dcm is a derived file")
    check(ni_derived.attenuation_map_files({"dicoms": [
        {"src_relpath": "recon_1/20260212130722_CT_ISRA_1.dcm"}]}) == [],
        "a real reconstruction is not")
    w = build_world(tmp)
    a_ct = os.path.join(w["box"], "1207", "260212", "0324_m61", "20260212130722_CT")
    attmap = os.path.join(a_ct, "recon_2", "ATTMAP.dcm")
    write(attmap, b"ATTMAP-BYTES-" * 100)
    add_acquisition(w["box"], "1207/260214/0324_m63/20260214090000_CT", [])
    write(os.path.join(w["box"], "1207", "260214", "0324_m63", "20260214090000_CT",
                       "recon_0", "ATTMAP.dcm"), b"LONE-ATTMAP")
    box0 = snapshot(w["box"])
    corr = os.path.join(tmp, "corr_d.csv")
    run(w, "--plan", "--corrections", corr)

    rc, out = run(w, "--dry-run", "--corrections", corr)
    check(rc == 0 and "3 new acquisition(s) to ingest" in out,
          "the preview table holds the 3 reconstructions only, no attenuation map")
    check("2 derived file(s) (CT attenuation maps) to copy into" in out,
          "the preview says how many derived files will be copied")

    rc, out = run(w, "--go", "--corrections", corr)
    rows = raw_rows(w["nas"])
    check(rc == 0 and len(rows) == 3 and not any("recon_2" in r["original_name"] or
                                                 "0324_m63" in r["original_name"] for r in rows),
          f"no ACQ-ID for an attenuation map ({len(rows)} rows registered)")
    name = "CT_0324_m61_20260212_20260212130722_recon2_ATTMAP.dcm"
    placed = os.path.join(w["nas"], "projects", "AE-biomaGUNE-0324", "outputs", "derived", name)
    check(os.path.isfile(placed) and open(placed, "rb").read() == open(attmap, "rb").read(),
          f"placed byte-identical at projects/AE-biomaGUNE-0324/outputs/derived/{name}")
    a_ids = sorted(r["acq_id"] for r in rows if "0324_m61" in r["original_name"])
    with open(os.path.join(w["nas"], "projects", "AE-biomaGUNE-0324", "provenance.csv"),
              encoding="utf-8", newline="") as f:
        prov = [r for r in csv.DictReader(f) if r["output_path"] == f"outputs/derived/{name}"]
    check(len(prov) == 1 and prov[0]["input_refs"] == ";".join(a_ids),
          f"one provenance row, input_refs = the CT scan's ACQ-IDs ({prov[0]['input_refs'] if prov else None})")
    check(bool(prov) and prov[0]["parameters_ref"] ==
          "1207/260212/0324_m61/20260212130722_CT/recon_2/ATTMAP.dcm",
          "the provenance row names the exact source file on the box")
    check("derived file waiting: 1207/260214/0324_m63/20260214090000_CT/recon_0" in out,
          "an attenuation map whose scan has nothing registered waits")
    check(not os.path.exists(os.path.join(w["nas"], "projects", "AE-biomaGUNE-0324", "outputs",
                                          "derived", "CT_0324_m63_20260214_20260214090000_recon0_ATTMAP.dcm")),
          "... and is not placed")

    rc, out = run(w, "--go", "--corrections", corr)
    with open(os.path.join(w["nas"], "projects", "AE-biomaGUNE-0324", "provenance.csv"),
              encoding="utf-8", newline="") as f:
        n_prov = sum(1 for r in csv.DictReader(f) if r["output_path"] == f"outputs/derived/{name}")
    check(rc == 0 and len(raw_rows(w["nas"])) == 3 and n_prov == 1,
          "a re-sync adds nothing: no row, no second copy, no second provenance entry")
    check(snapshot(w["box"]) == box0, "the box was never written")


def project_rule_flow(tmp):
    """Ryan, 2026-10-08: the code position names the project (protocol-or-project)."""
    print("project names: 4 digits = protocol, any other code = Project-<code>")
    w = build_world(tmp)
    shutil.rmtree(w["box"])
    add_acquisition(w["box"], "1207/260212/FDG_m3/20260212100000_CT", [0])
    add_acquisition(w["box"], "1207/260212/324_m61/20260212110000_CT", [0])
    corr = os.path.join(tmp, "corr_p.csv")
    run(w, "--plan", "--corrections", corr)
    with open(corr, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    check({r["session_path"]: r["project"] for r in rows} ==
          {"1207/260212/FDG_m3": "FDG", "1207/260212/324_m61": "324"},
          "the corrections file shows the code as typed (FDG, 324), not the series 1207")
    for r in rows:                                   # the operator fixes one of them
        if r["session_path"] == "1207/260212/324_m61":
            r["project"] = "0525"
    with open(corr, "w", encoding="utf-8", newline="") as f:
        dw = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        dw.writeheader()
        dw.writerows(rows)
    rc, out = run(w, "--go", "--corrections", corr)
    names = sorted(project_name(w["nas"], r) for r in raw_rows(w["nas"]))
    check(rc == 0 and names == ["AE-biomaGUNE-0525", "Project-FDG"],
          f"FDG_m3 -> Project-FDG (new); 324 corrected to 0525 -> AE-biomaGUNE-0525 (got {names})")
    check(not any("1207" in n for n in names), "nothing filed under the series/funding number 1207")


class _FakeTerminal(io.StringIO):
    def isatty(self):
        return True


def terminal_flow(tmp):
    """A person at a real terminal (every subprocess run above is non-interactive).

    Live mode must ask NOTHING but the final 'Proceed? [y/N]': no batch-wide
    is_control question (Ryan, 2026-10-08 -- the scripted runs above could never
    show it, which is how it survived the 2026-10-06 on-box gates). Answers 'n'
    at Proceed, so nothing is written.
    """
    print("a person at a terminal: live mode asks nothing but 'Proceed?'")
    w = build_world(tmp)
    spec = importlib.util.spec_from_file_location(
        "ni_ingest_under_test", os.path.join(_HERE, "operator", "ni_ingest.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    seen_interactive = []
    real_collect = mod.metadata_prompt.collect_overrides

    def recording_collect(cli, **kw):
        seen_interactive.append(kw.get("interactive"))
        return real_collect(cli, **kw)

    asked = []

    def fake_input(prompt=""):
        asked.append(prompt)
        return "n"

    nas0 = snapshot(w["nas"])
    old = (builtins.input, sys.stdin, mod.metadata_prompt.collect_overrides)
    builtins.input, sys.stdin = fake_input, _FakeTerminal()
    mod.metadata_prompt.collect_overrides = recording_collect
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = mod.main([w["box"], "--live", "--nas-root", w["nas"],
                           "--corrections", os.path.join(tmp, "corr_tty.csv")])
    finally:
        builtins.input, sys.stdin, mod.metadata_prompt.collect_overrides = old
    check(rc == 0, "the terminal run exits 0 after answering 'n'")
    check(seen_interactive == [False], f"no metadata questions in live mode (interactive={seen_interactive})")
    check(len(asked) == 1 and asked[0].startswith("Proceed?"),
          f"the only question is the final confirmation (asked: {asked!r})")
    check(snapshot(w["nas"]) == nas0, "declining at Proceed wrote nothing")


def main():
    with tempfile.TemporaryDirectory(prefix="ni_live_e2e_") as tmp:
        main_flow(os.path.join(tmp, "a"))
    with tempfile.TemporaryDirectory(prefix="ni_live_e2e_") as tmp:
        enotsup_flow(os.path.join(tmp, "b"))
    with tempfile.TemporaryDirectory(prefix="ni_live_e2e_") as tmp:
        terminal_flow(os.path.join(tmp, "c"))
    with tempfile.TemporaryDirectory(prefix="ni_live_e2e_") as tmp:
        cross_source_flow(os.path.join(tmp, "d"))
    with tempfile.TemporaryDirectory(prefix="ni_live_e2e_") as tmp:
        derived_flow(os.path.join(tmp, "e"))
    with tempfile.TemporaryDirectory(prefix="ni_live_e2e_") as tmp:
        project_rule_flow(os.path.join(tmp, "f"))
    if FAILED:
        print(f"\n{len(FAILED)} CHECK(S) FAILED")
        sys.exit(1)
    print("\nALL NI LIVE E2E CHECKS PASSED")


if __name__ == "__main__":
    main()
