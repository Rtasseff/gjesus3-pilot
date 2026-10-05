#!/usr/bin/env python3
"""test_unparsed_report.py — every study folder whose name matches no filename_parse
rule is reported, once, with its exam count (STATUS §0 D3, Ryan 2026-10-05).

Before this, `expand_batch` dropped such a study with one `[expand_batch] SKIP <exam>`
line per exam on stdout and nothing else: no count, nothing durable, nothing in the
BATCH SUMMARY, and on the MRI page the drops read as "housekeeping". That is how
`jrc250526_145_0522` (the operator omitted the `m`) went missing for two months.

Builds, in temp dirs only, a staging tree of <study>/<exam> folders (each exam holds
`acqp` + `method`; each study has a `subject` file):

    jrc251016_m17_0424     animal-first: parses                      2 exams
    jrc221003_0721_m45     project-first only                        3 exams
    jrc250526_145_0522     the real G1 case: no `m`                  4 exams, plus an
                           empty numbered folder 99/ (an aborted exam) and AdjResult/
    jrc260709_phantom      a phantom                                 2 exams
    jl260707_1225_m26      another group's study                     1 exam

and checks, under the PRODUCTION animal-first regex and pattern (read from
tools/configs/mri_jrc_animalfirst.yaml):

  1. expand_batch(unparsed=[]) reports exactly the 4 non-matching study folders, each
     once, with the right exam-folder counts (99/ is a dropped match, not an exam),
     and rule / reason / path filled in;
  2. the matched study's cases are unchanged, and the return value is the same plain
     list whether or not the collector is passed (non-breaking);
  3. every dropped match still prints its "[expand_batch] SKIP <exam>: <reason>" line
     (the GUI preview parses that format), plus one NOT PARSED line that contains
     neither "SKIP" nor "WARN" (drive_staging/ingest_check.py counts those words);
  4. preview: _categorize_skips still finds the per-exam drops, and preview_batch
     groups them into one `unparsed` entry per study and tags each drop;
  5. the CLI, in --dry-run: the BATCH SUMMARY has the NOT PARSED section with one
     line per study, --unparsed-report writes the CSV (one row per study), and
     nothing is written under the (temporary) NAS root;
  6. the production animal-first CONFIG FILE itself (embedded metadata on) reports the
     same 4 study folders; the GUI's "*/*" pattern (which also globs subject /
     AdjResult) still reports 10 exam folders;
  7. a positional (fields) rule failure is reported per name (source: name).

Run:  python tools/test_unparsed_report.py      (exit 0 = pass)
"""

import contextlib
import csv
import importlib.util
import io
import os
import subprocess
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import yaml  # noqa: E402

from ingest import config, unparsed  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


ANIMALFIRST_CFG = os.path.join(TOOLS, "configs", "mri_jrc_animalfirst.yaml")
_AF = config.load_config(ANIMALFIRST_CFG)["auto_discover"]
ANIMALFIRST_RX = _AF["filename_parse"]["regex"]
PROD_PATTERN = _AF["pattern"]            # "*/[0-9]*"

STUDIES = {                      # study folder -> number of exam folders
    "jrc251016_m17_0424": 2,     # animal-first: parses
    "jrc221003_0721_m45": 3,     # project-first only
    "jrc250526_145_0522": 4,     # G1: no `m`
    "jrc260709_phantom": 2,      # phantom
    "jl260707_1225_m26": 1,      # another group
}
MATCHED = "jrc251016_m17_0424"
G1 = "jrc250526_145_0522"
UNMATCHED = {k: v for k, v in STUDIES.items() if k != MATCHED}
N_UNMATCHED_EXAMS = sum(UNMATCHED.values())          # 10


def build_staging(root):
    staging = os.path.join(root, "staging")
    for study, n in STUDIES.items():
        sdir = os.path.join(staging, study)
        os.makedirs(sdir)
        with open(os.path.join(sdir, "subject"), "w") as f:
            f.write("##$SUBJECT_id=( 60 )\n<%s>\n" % study)
        for i in range(1, n + 1):
            edir = os.path.join(sdir, str(i))
            os.makedirs(edir)
            for name in ("acqp", "method"):
                with open(os.path.join(edir, name), "w") as f:
                    f.write("##TITLE=fake %s\n" % name)
    # Under G1: an aborted exam (numbered, so "*/[0-9]*" globs it, but no acqp /
    # method) and a ParaVision housekeeping sibling (globbed only by "*/*").
    os.makedirs(os.path.join(staging, G1, "99"))
    os.makedirs(os.path.join(staging, G1, "AdjResult"))
    return staging


def make_nas(root):
    nas = os.path.join(root, "nas")
    os.makedirs(os.path.join(nas, "registries"))
    return nas


def mri_cfg(staging, pattern=PROD_PATTERN):
    """A minimal MRI batch config with the production animal-first regex and
    pattern. Embedded metadata off, so the matched study resolves from the regex."""
    return {
        "ingest": {"acquisition_layout": "folder", "copy_strategy": "mri_paravision_v2",
                   "auto_create_projects": False},
        "auto_discover": {
            "staging_dir": staging, "pattern": pattern, "embedded_metadata": False,
            "filename_parse": {"source": "parent_name", "regex": ANIMALFIRST_RX},
        },
        "registry": {
            "instrument": "MRI", "data_ecosystem": "DICOM", "data_source": "internal",
            "researcher": "NA",
            "sample_id": "m${discovered.animal_num}_${discovered.project_code}",
            "session_id": "discovered.jrc_id", "acquisition_datetime": "2025-10-16",
        },
    }


def expand(cfg, nas=None, collector=None):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        if collector is None:
            cases = config.expand_batch(cfg, nas_root=nas)
        else:
            cases = config.expand_batch(cfg, nas_root=nas, unparsed=collector)
    return cases, out.getvalue()


def snapshot(path):
    snap = {}
    for dp, _dn, fn in os.walk(path):
        snap[dp] = "dir"
        for name in fn:
            p = os.path.join(dp, name)
            st = os.stat(p)
            snap[p] = (st.st_size, st.st_mtime_ns)
    return snap


def load_preview():
    spec = importlib.util.spec_from_file_location(
        "gj_operator_loader", os.path.join(TOOLS, "operator", "_loader.py"))
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)
    return loader.load().preview


def test_expand_batch(staging):
    print("1-3. expand_batch: records, matched cases, SKIP lines")
    cfg = mri_cfg(staging)
    recs = []
    cases, log = expand(cfg, collector=recs)
    by_target = {r["target"]: r for r in recs}

    check(sorted(by_target) == sorted(UNMATCHED),
          f"exactly the 4 non-matching study folders are reported (got {sorted(by_target)})")
    check(len(recs) == len(by_target), "each study folder is reported once")
    for study, n in UNMATCHED.items():
        r = by_target.get(study, {})
        check(r.get("n_exam_folders") == n,
              f"{study}: {n} exam folder(s) (got {r.get('n_exam_folders')})")
    g1 = by_target.get(G1, {})
    check(g1.get("n_matches") == 5 and g1.get("n_exam_folders") == 4,
          "G1: the empty 99/ is a dropped match, not an exam folder")
    check(g1.get("target_path") == os.path.join(staging, G1), "target_path is the study folder")
    check(g1.get("source") == "parent_name" and g1.get("rule") == "regex"
          and g1.get("pattern") == ANIMALFIRST_RX,
          "source / rule / pattern are recorded")
    check(G1 in g1.get("reason", "") and "did not match" in g1.get("reason", ""),
          "reason is the parser's own message")
    check(sorted(g1.get("matches", [])) == sorted(["%s/%s" % (G1, x) for x in ("1", "2", "3", "4", "99")]),
          "matches are the dropped original_names")
    check(unparsed.count_label(g1) == "4 exam folders + 1 other entry", "per-study count wording")

    names = sorted(c["original_name"] for c in cases)
    check(names == ["%s/%d" % (MATCHED, i) for i in (1, 2)],
          f"the matched study's exams are the cases, unchanged (got {names})")
    check(all(c["discovered"].get("animal_num") == "17" and c["discovered"].get("project_code") == "0424"
              for c in cases), "matched cases keep their parsed values")
    check(type(cases) is list, "the return value is still a plain list")

    plain_cases, plain_log = expand(cfg)
    check([c["original_name"] for c in plain_cases] == [c["original_name"] for c in cases]
          and [c["discovered"] for c in plain_cases] == [c["discovered"] for c in cases],
          "without the collector: the same cases (non-breaking)")
    check(plain_log == log, "without the collector: the same stdout")

    skip_lines = [ln for ln in log.splitlines() if ln.startswith("[expand_batch] SKIP ")]
    n_dropped = sum(r["n_matches"] for r in recs)
    check(n_dropped == 11 and len(skip_lines) == n_dropped,
          f"one SKIP line per dropped match is still printed ({len(skip_lines)} == {n_dropped} == 11)")
    np_lines = [ln for ln in log.splitlines() if "NOT PARSED" in ln]
    check(len(np_lines) == 1 and np_lines[0].startswith(
              f"[expand_batch] NOT PARSED: 4 study folder(s) ({N_UNMATCHED_EXAMS} exam folders)"),
          f"one NOT PARSED line with the totals (got {np_lines})")
    check(bool(np_lines) and "SKIP" not in np_lines[0] and "WARN" not in np_lines[0],
          "the NOT PARSED line avoids the words ingest_check.py counts")
    return log


def test_preview(td, staging, log):
    print("4. preview: categorisation still works; one entry per study")
    preview = load_preview()
    lines = [ln for ln in log.splitlines() if ln.strip()]
    already, dropped = preview._categorize_skips(lines)
    check(already == 0 and len(dropped) == 11,
          f"_categorize_skips: 0 already-ingested, 11 drops (got {already}, {len(dropped)})")
    check({d["name"] for d in dropped} == {"1", "2", "3", "4", "99"},
          "drops keep the exam basenames as names")

    nas = make_nas(os.path.join(td, "preview"))
    res = preview.preview_batch(mri_cfg(staging), nas)
    check(res.n_new == 2, f"preview: 2 new cases (got {res.n_new})")
    check(res.n_dropped == 11, f"preview: n_dropped unchanged at 11 (got {res.n_dropped})")
    tg = {u["target"]: u for u in res.unparsed}
    check(sorted(tg) == sorted(UNMATCHED), "preview: one unparsed entry per study folder")
    check(all(tg.get(s, {}).get("n_exam_folders") == n for s, n in UNMATCHED.items()),
          "preview: each entry carries its exam-folder count")
    check(all("matches" not in u for u in res.unparsed), "preview: entries are compact (no match list)")
    check(len(res.dropped) == 11 and all(d.get("unparsed") is True for d in res.dropped),
          "preview: every per-exam drop is tagged as belonging to an unparsed study")

    # A housekeeping drop (a non-scan sibling) must NOT be tagged as unparsed.
    hk = preview._categorize_skips(
        ["[expand_batch] SKIP AdjResult: not a scan folder (no acquisition metadata; "
         "a sibling/housekeeping folder)"])[1]
    check(len(hk) == 1 and "unparsed" not in hk[0],
          "a housekeeping drop stays untagged at categorisation")


def test_gui(td, staging):
    print("4b. GUI: /api/mri/preview returns the grouped list; the page renders it")
    js_path = os.path.join(TOOLS, "operator", "gui", "static", "mri.js")
    with open(js_path, encoding="utf-8") as f:
        js = f.read()
    check("renderDropped(d.dropped, d.unparsed)" in js,
          "mri.js: the preview passes the grouped list to the drop box")
    check("filter((d) => !d.unparsed)" in js,
          "mri.js: only untagged drops are called housekeeping")
    check("NOT PARSED" in js, "mri.js: the page says NOT PARSED")
    if importlib.util.find_spec("flask") is None:
        print("  skip: Flask not installed - endpoint check skipped")
        return
    gui_dir = os.path.join(TOOLS, "operator", "gui")
    if gui_dir not in sys.path:
        sys.path.insert(0, gui_dir)
    import app as gui  # noqa: E402
    nas = make_nas(os.path.join(td, "gui"))
    before = snapshot(nas)
    resp = gui.app.test_client().post(
        "/api/mri/preview", json={"staging_path": staging, "nas_root": nas})
    data = resp.get_json() or {}
    check(resp.status_code == 200, f"/api/mri/preview answers 200 (got {resp.status_code}: "
                                   f"{data.get('error', '')})")
    tg = {u["target"]: u["n_exam_folders"] for u in data.get("unparsed") or []}
    check(tg == UNMATCHED, f"/api/mri/preview: one entry per unparsed study with its exam count (got {tg})")
    tagged = [d for d in data.get("dropped") or [] if d.get("unparsed")]
    # "*/*" globs every entry of each unparsed study: its exams, its `subject`
    # file, and (G1) 99/ and AdjResult/: 10 + 4 + 2.
    want = N_UNMATCHED_EXAMS + len(UNMATCHED) + 2
    check(len(tagged) == want,
          f"/api/mri/preview: all {want} per-match drops under them are tagged (got {len(tagged)})")
    check(snapshot(nas) == before, "/api/mri/preview wrote nothing under the NAS root")


def test_cli(td, staging):
    print("5. CLI --dry-run: BATCH SUMMARY section, --unparsed-report CSV, nothing on the NAS")
    nas = make_nas(os.path.join(td, "cli"))
    cfg_path = os.path.join(td, "cli", "mri_test.yaml")
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(mri_cfg(staging), f)
    csv_path = os.path.join(td, "reports", "unparsed.csv")
    before = snapshot(nas)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [sys.executable, os.path.join(TOOLS, "ingest_raw.py"), "--config", cfg_path,
         "--nas-root", nas, "--dry-run", "--unparsed-report", csv_path],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
        cwd=os.path.dirname(TOOLS))
    out = proc.stdout + proc.stderr
    check(proc.returncode == 0, f"ingest_raw.py --dry-run exits 0 (got {proc.returncode})")
    summary = out.split("BATCH SUMMARY", 1)[-1] if "BATCH SUMMARY" in out else ""
    check("Success:  2" in summary and "Failed:   0" in summary,
          "the 2 matched exams dry-run fine")
    check(f"NOT PARSED: 4 study folder(s) ({N_UNMATCHED_EXAMS} exam folders) matched no "
          f"filename_parse rule" in summary, "BATCH SUMMARY: the NOT PARSED headline")
    for study, n in UNMATCHED.items():
        want = "%d exam folder%s" % (n, "s" if n != 1 else "")
        check(any(study in ln and want in ln for ln in summary.splitlines()),
              f"BATCH SUMMARY: one line for {study} ({want})")
    check(csv_path in summary, "BATCH SUMMARY: points at the CSV")
    check("NOT PARSED" in out.split("BATCH SUMMARY", 1)[0] and "WARN" in out.split("BATCH SUMMARY", 1)[0],
          "a WARN line before the cases, too")
    check(os.path.isfile(csv_path), "the --unparsed-report CSV is written in --dry-run")
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8"))) if os.path.isfile(csv_path) else []
    check(sorted(r["target"] for r in rows) == sorted(UNMATCHED), "CSV: one row per unparsed study")
    check(all(int(r["n_exam_folders"]) == UNMATCHED[r["target"]] for r in rows), "CSV: exam counts")
    check(bool(rows) and list(rows[0].keys()) == unparsed.CSV_FIELDS, "CSV: the documented columns")
    check(all(r["config"] and r["reported_at"] for r in rows), "CSV: config and timestamp filled in")
    check(snapshot(nas) == before, "nothing was written under the NAS root")


def test_patterns(staging):
    print("6. the production config file, and the GUI's */* pattern")
    cfg = config.load_config(ANIMALFIRST_CFG)
    cfg["auto_discover"]["staging_dir"] = staging
    cfg["auto_discover"]["subject_from_db"] = False
    recs = []
    expand(cfg, collector=recs)
    got = {r["target"]: r["n_exam_folders"] for r in recs}
    check(got == UNMATCHED, f"production config: the same 4 study folders and exam counts (got {got})")

    recs = []
    expand(mri_cfg(staging, pattern="*/*"), collector=recs)
    g1 = {r["target"]: r for r in recs}.get(G1, {})
    check(unparsed.totals(recs)[:2] == (4, N_UNMATCHED_EXAMS),
          "*/*: still 4 study folders and 10 exam folders (siblings are not exams)")
    check(g1.get("n_matches") == 7, "*/*: G1 also dropped 99/, AdjResult/ and subject (7 matches)")


def test_positional(td):
    print("7. a positional rule failure is reported per name")
    staging = os.path.join(td, "positional")
    os.makedirs(staging)
    for name in ("MFB_AUA_1123_ID12.czi", "short.czi"):
        with open(os.path.join(staging, name), "wb") as f:
            f.write(b"x")
    cfg = {
        "auto_discover": {"staging_dir": staging, "pattern": "*.czi", "embedded_metadata": False,
                          "filename_parse": {"separator": "_", "fields": ["group", "op", "proj", "sample"]}},
        "registry": {"instrument": "CELL", "data_ecosystem": "MICROSCOPY", "data_source": "internal",
                     "researcher": "NA", "sample_id": "discovered.sample",
                     "acquisition_datetime": "2024-01-02"},
    }
    recs = []
    cases, _log = expand(cfg, collector=recs)
    check([c["original_name"] for c in cases] == ["MFB_AUA_1123_ID12.czi"], "the parseable file is a case")
    check(len(recs) == 1 and recs[0]["target"] == "short.czi" and recs[0]["rule"] == "positional"
          and recs[0]["source"] == "name" and recs[0]["n_exam_folders"] == 0 and recs[0]["n_matches"] == 1,
          "the unparseable file is one record: rule positional, source name, 1 match")
    check(unparsed.headline(recs) == "NOT PARSED: 1 name(s) (1 match) matched no filename_parse rule",
          "headline wording for a non-ParaVision batch")


def main():
    with tempfile.TemporaryDirectory(prefix="gj3_unparsed_") as td:
        staging = build_staging(td)
        log = test_expand_batch(staging)
        test_preview(td, staging, log)
        test_gui(td, staging)
        test_cli(td, staging)
        test_patterns(staging)
        test_positional(td)
    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s)")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
