#!/usr/bin/env python3
"""test_manager.py — the Project Manager, end to end against a scratch NAS.

Drives the real Flask app through `app.test_client()` over a throwaway NAS root
built here (registries + a handful of real `/raw/` acquisitions on disk), so
every flow exercises the actual endpoints, the actual engines and the actual
registry writers — not stand-ins.

NEVER point this at `J:`. It creates, edits and links; a bug in a locked
read-modify-write on `registry_projects.csv` would take the live 52 rows with
it. Everything happens under a temp dir that is removed at the end.

Covered:
  * update a project    — registry + `_project.yaml` both written, and
                          `last_activity` NOT stamped (it means the newest
                          acquisition, not the last edit)
  * create a project    — id, folder == name, the four subfolders, live name
                          normalization + case-insensitive uniqueness
  * import from raw     — hard link (file primary AND folder primary), the
                          provenance row, the project recorded as a `;`-list,
                          idempotent re-import, collision reported not
                          overwritten, and an acquisition in TWO projects
                          appearing in BOTH per-project indexes
  * hard-link failure   — queued to pending_links.csv, `.PENDING-LINK.txt`
                          stand-in written, the association still recorded, and
                          the summary says the data IS registered
  * import from local   — copy (never move), provenance, and the 409-style
                          refusal to overwrite without an explicit confirm

Run:  python tools/test_manager.py
"""
import csv
import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ingest import project_ids as pids       # noqa: E402
from ingest import provenance, registry      # noqa: E402

FAILED = []


def check(cond, msg):
    print(f"  {'ok' if cond else 'FAIL'}:   {msg}")
    if not cond:
        FAILED.append(msg)


# ------------------------------------------------------------------ fixture

PROJECT_COLS = ["project_id", "name", "description", "owner", "start_date",
                "status", "last_activity", "folder_location", "notes"]

YAML_TEMPLATE = """project_id: {pid}
name: {name}
description: "{desc}"
status: active  # active | paused | closed
owner: {owner}

# Timeline
start_date: 2026-01-01
last_activity: 2026-01-01
closed_date: null

# Notes
notes: |
  Created by the fixture
"""


def build_nas(root):
    """A miniature but structurally real NAS: registries + raw acquisitions."""
    reg = os.path.join(root, "registries")
    os.makedirs(reg)
    os.makedirs(os.path.join(root, "raw"))

    projects = [
        ("PROJ-0001", "alpha", "Alpha study", "AA", "active", "/projects/alpha/"),
        ("PROJ-0002", "beta", "Beta study", "BB", "active", "/projects/beta/"),
        # closed with the folder deleted — the normal post-close-out state
        ("PROJ-0003", "gone", "Closed study", "CC", "closed", "/projects/gone/"),
    ]
    with open(os.path.join(reg, "registry_projects.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(PROJECT_COLS)
        for pid, name, desc, owner, status, loc in projects:
            w.writerow([pid, name, desc, owner, "2026-01-01", status,
                        "2026-01-01", loc, ""])
    for pid, name, desc, owner, status, loc in projects:
        if status == "closed":
            continue
        d = os.path.join(root, "projects", name)
        os.makedirs(os.path.join(d, "raw_linked"))
        with open(os.path.join(d, "_project.yaml"), "w", encoding="utf-8") as f:
            f.write(YAML_TEMPLATE.format(pid=pid, name=name, desc=desc, owner=owner))
        provenance.write_empty(os.path.join(d, "provenance.csv"))

    # Three acquisitions with real bytes on disk: a FILE primary (microscopy
    # .czi), a FOLDER primary (the NI/MRI `<ACQ-ID>.data` bundle), and a second
    # file primary whose original_name collides with the first.
    acqs = [
        dict(acq_id="ACQ-20260101-ZWSI-001", instrument="ZWSI",
             primary_kind="file", primary_file_name="slide-a.czi",
             original_name="slide-a.czi", eco="MICROSCOPY"),
        dict(acq_id="ACQ-20260102-MRI-001", instrument="MRI",
             primary_kind="folder", primary_file_name="ACQ-20260102-MRI-001.data",
             original_name="exam_42", eco="DICOM"),
        dict(acq_id="ACQ-20260103-ZWSI-002", instrument="ZWSI",
             primary_kind="file", primary_file_name="slide-a.czi",
             original_name="slide-a.czi", eco="MICROSCOPY"),
    ]
    rows = []
    for a in acqs:
        canonical = f"/raw/{a['eco']}/2026/2026-01/{a['acq_id']}/"
        acq_dir = os.path.join(root, canonical.strip("/").replace("/", os.sep))
        os.makedirs(acq_dir)
        if a["primary_kind"] == "file":
            with open(os.path.join(acq_dir, a["primary_file_name"]), "wb") as f:
                f.write(b"raw bytes for " + a["acq_id"].encode())
        else:
            bundle = os.path.join(acq_dir, a["primary_file_name"])
            os.makedirs(bundle)
            for i in range(3):
                with open(os.path.join(bundle, f"slice{i}.dcm"), "wb") as f:
                    f.write(b"dicom " + str(i).encode())
        rows.append({
            "acq_id": a["acq_id"],
            "acquisition_datetime": f"2026-01-0{acqs.index(a) + 1}T09:00:00",
            "instrument": a["instrument"],
            "data_ecosystem": a["eco"],
            "primary_kind": a["primary_kind"],
            "primary_file_name": a["primary_file_name"],
            "original_name": a["original_name"],
            "canonical_path": canonical,
            "sample_id": f"s{acqs.index(a)}",
            "project_id": "",
        })
    with open(os.path.join(reg, "registry_raw.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=registry.REGISTRY_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in registry.REGISTRY_FIELDS})
    return root


# ------------------------------------------------------------------- helpers

def post(client, url, body):
    r = client.post(url, json=body)
    try:
        return r.status_code, r.get_json()
    except Exception:  # noqa: BLE001
        return r.status_code, None


def stream(client, url, body):
    """POST an SSE endpoint and return (log_lines, done_payload_or_None)."""
    r = client.post(url, json=body)
    if r.status_code != 200:
        return [], {"error": (r.get_json() or {}).get("error", r.status_code)}
    lines, done = [], None
    for chunk in r.get_data(as_text=True).split("\n\n"):
        chunk = chunk.strip()
        if not chunk.startswith("data: "):
            continue
        ev = json.loads(chunk[len("data: "):])
        if ev["kind"] == "log":
            lines.append(ev["msg"])
        elif ev["kind"] == "done":
            done = json.loads(ev["msg"])
        elif ev["kind"] == "error":
            done = {"error": ev["msg"]}
    return lines, done


def read_raw_registry(nas):
    return {r["acq_id"]: r for r in registry.read_registry(
        os.path.join(nas, "registries", "registry_raw.csv"))}


def prov_rows(project_dir):
    p = os.path.join(project_dir, "provenance.csv")
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------------- tests

def test_projects(client, nas):
    print("\n-- my projects: list + edit --")
    code, d = post(client, "/api/projects", {"nas_root": nas})
    check(code == 200 and d["counts"]["total"] == 3, "lists all three rows")
    by_id = {p["project_id"]: p for p in d["projects"]}
    check(by_id["PROJ-0003"]["folder_exists"] is False,
          "closed project with no folder is reported, not treated as an error")
    check(by_id["PROJ-0001"]["missing_subfolders"] == ["working", "outputs", "metadata"],
          "an old project's missing subfolders are surfaced")

    code, d = post(client, "/api/update_project", {
        "nas_root": nas, "project_id": "PROJ-0001",
        "updates": {"description": "Edited by the test", "status": "paused",
                    "owner": "ZZ", "notes": "note\nsecond line"}})
    check(code == 200 and len(d["applied"]) == 4, "four editable fields saved")
    check(sorted(d["yaml_changed"]) == ["description", "notes", "owner", "status"],
          "_project.yaml kept in step with the registry")

    row = {r["project_id"]: r for r in _read_projects(nas)}["PROJ-0001"]
    check(row["description"] == "Edited by the test", "registry row updated")
    check(row["last_activity"] == "2026-01-01",
          "last_activity NOT stamped by an edit (it means the newest acquisition)")
    check(row["start_date"] == "2026-01-01", "start_date untouched")

    yml = open(os.path.join(nas, "projects", "alpha", "_project.yaml"),
               encoding="utf-8").read()
    check("# Timeline" in yml, "_project.yaml keeps its section comments")
    check("status: paused  # active | paused | closed" in yml,
          "a trailing vocabulary comment survives the edit")
    check("  second line" in yml, "a multi-line note becomes a block scalar")

    code, d = post(client, "/api/update_project", {
        "nas_root": nas, "project_id": "PROJ-0001",
        "updates": {"status": "archived"}})
    check(code == 400 and "active" in d["error"],
          "a status outside the decided vocabulary is refused")

    code, d = post(client, "/api/update_project", {
        "nas_root": nas, "project_id": "PROJ-0001",
        "updates": {"folder_location": "/projects/elsewhere/"}})
    check(code == 400, "folder_location cannot be edited here")

    code, d = post(client, "/api/update_project", {
        "nas_root": nas, "project_id": "PROJ-0003",
        "updates": {"notes": "still editable"}})
    check(code == 200 and d["warnings"],
          "a folderless closed project is still editable, with a warning")


def _read_projects(nas):
    from ingest import projects_registry
    return projects_registry.read_projects(
        projects_registry.projects_registry_path(nas))


def test_create(client, nas):
    print("\n-- new project --")
    code, d = post(client, "/api/check_project_name",
                   {"nas_root": nas, "name": "  My New Study  "})
    check(code == 200 and d["name"] == "My-New-Study",
          "spaces become hyphens, live, before submission")
    code, d = post(client, "/api/check_project_name",
                   {"nas_root": nas, "name": "ALPHA"})
    check(d["errors"], "an existing name is rejected regardless of case")
    code, d = post(client, "/api/check_project_name",
                   {"nas_root": nas, "name": "bad/name"})
    check(d["errors"], "a name that is not a legal folder is rejected")

    code, d = post(client, "/api/create_project", {
        "nas_root": nas, "name": "My New Study",
        "description": "made by the test", "owner": "RT", "notes": "n"})
    check(code == 200 and d["project_id"] == "PROJ-0004",
          "next id continues the sequence")
    pdir = os.path.join(nas, "projects", "My-New-Study")
    check(os.path.isdir(pdir), "folder == name, verbatim")
    check(sorted(os.listdir(pdir)) ==
          ["_project.yaml", "metadata", "outputs", "provenance.csv",
           "raw_linked", "working"],
          "the four recommended subfolders + yaml + provenance")

    code, d = post(client, "/api/create_project", {
        "nas_root": nas, "name": "my new study",
        "description": "dup", "owner": "RT"})
    check(code == 400, "a case-only-different duplicate is refused")


def test_import_raw(client, nas):
    print("\n-- add data from the RDM System --")
    code, d = post(client, "/api/search_acqs", {"nas_root": nas, "query": ""})
    check(code == 200 and d["total"] == 3, "search returns all acquisitions")
    code, d = post(client, "/api/search_acqs",
                   {"nas_root": nas, "instrument": "MRI"})
    check(d["total"] == 1, "the instrument filter narrows, via find_acq")

    both = ["ACQ-20260101-ZWSI-001", "ACQ-20260102-MRI-001"]
    code, d = post(client, "/api/import_raw_plan", {
        "nas_root": nas, "project": "PROJ-0001", "acq_ids": both})
    check(code == 200 and d["n_new"] == 2, "plan says both will be added")
    names = {i["acq_id"]: i["link_name"] for i in d["items"]}
    check(names["ACQ-20260101-ZWSI-001"] == "slide-a.czi",
          "link name defaults to the row's original_name")

    code, d = post(client, "/api/import_raw", {
        "nas_root": nas, "project": "PROJ-0001", "acq_ids": both})
    check(code == 400, "a commit with no creator is refused (provenance needs it)")

    lines, done = stream(client, "/api/import_raw", {
        "nas_root": nas, "project": "PROJ-0001", "acq_ids": both,
        "creator": "Tester"})
    check(done and done.get("linked") == 2, "both acquisitions linked")

    alpha = os.path.join(nas, "projects", "alpha")
    link_file = os.path.join(alpha, "raw_linked", "slide-a.czi")
    link_dir = os.path.join(alpha, "raw_linked", "exam_42")
    check(os.path.isfile(link_file), "file primary -> a single hard link")
    check(os.path.isdir(link_dir), "folder primary -> a real folder of links")
    check(len(os.listdir(link_dir)) == 3, "every file in the bundle is linked")
    src = os.path.join(nas, "raw", "MICROSCOPY", "2026", "2026-01",
                       "ACQ-20260101-ZWSI-001", "slide-a.czi")
    # SMB reports st_nlink == 1 on this share, so identity is checked by file
    # index / inode, the way relink_projects.py does it.
    a, b = os.stat(src), os.stat(link_file)
    check((a.st_ino, a.st_dev) == (b.st_ino, b.st_dev),
          "the link IS the raw file (same inode) — no extra storage")

    reg = read_raw_registry(nas)
    check(reg["ACQ-20260101-ZWSI-001"]["project_id"] == "PROJ-0001",
          "the project is recorded on the registry row")
    rows = prov_rows(alpha)
    check(len(rows) == 2, "one provenance row per link")
    p = {r["output_name"]: r for r in rows}
    check(p["exam_42"]["file_type"] == "hardlink-folder"
          and p["slide-a.czi"]["file_type"] == "hardlink",
          "provenance records which kind of link was made")
    check(p["slide-a.czi"]["creator"] == "Tester", "creator recorded as given")
    check(p["slide-a.czi"]["input_refs"] == "ACQ-20260101-ZWSI-001",
          "provenance points back at the acquisition")

    # Re-import: idempotent, and must never produce PROJ-0001;PROJ-0001.
    lines, done = stream(client, "/api/import_raw", {
        "nas_root": nas, "project": "PROJ-0001", "acq_ids": both,
        "creator": "Tester"})
    check(done.get("skipped") == 2 and done.get("linked") == 0,
          "re-importing the same acquisitions does nothing")
    reg = read_raw_registry(nas)
    check(reg["ACQ-20260101-ZWSI-001"]["project_id"] == "PROJ-0001",
          "no duplicated project id on the row")
    check(len(prov_rows(alpha)) == 2, "no duplicated provenance rows")

    # Collision: a second acquisition whose original_name is already taken.
    code, d = post(client, "/api/import_raw_plan", {
        "nas_root": nas, "project": "PROJ-0001",
        "acq_ids": ["ACQ-20260103-ZWSI-002"]})
    check(d["n_new"] == 0 and d["items"][0]["status"] == "collision",
          "a link-name collision is reported, not overwritten")
    code, d = post(client, "/api/import_raw_plan", {
        "nas_root": nas, "project": "PROJ-0001",
        "acq_ids": ["ACQ-20260103-ZWSI-002"],
        "link_names": {"ACQ-20260103-ZWSI-002": "slide-a-second.czi"}})
    check(d["n_new"] == 1, "renaming the link resolves the collision")

    # The acquisition now goes into a SECOND project. Sharing works at the
    # FILESYSTEM level; the registry keeps the original association (write-once,
    # 06_REGISTRIES §2.3b — DECIDED 2026-08-12, superseding the one-day-old
    # semicolon-list decision).
    lines, done = stream(client, "/api/import_raw", {
        "nas_root": nas, "project": "PROJ-0002",
        "acq_ids": ["ACQ-20260101-ZWSI-001"], "creator": "Tester"})
    check(done.get("linked") == 1, "the same acquisition adds to a second project")

    reg = read_raw_registry(nas)
    cell = reg["ACQ-20260101-ZWSI-001"]["project_id"]
    check(cell == "PROJ-0001",
          "the registry still names ONLY the original project (write-once)")
    check(done.get("registered") == 0 and done.get("shared") == 1,
          "the summary reports it as shared, not newly registered")

    # The link and the provenance row ARE written — sharing is real, it is just
    # not registered. This is the half that must keep working.
    check(os.path.exists(os.path.join(nas, "projects", "beta", "raw_linked",
                                      "slide-a.czi")),
          "the second project gets a real hard link")
    prov = open(os.path.join(nas, "projects", "beta", "provenance.csv"),
                encoding="utf-8").read()
    check("ACQ-20260101-ZWSI-001" in prov,
          "the second project's provenance records the acquisition — the only "
          "place the sharing is recorded")

    # The per-project index follows the registry, so the shared acquisition shows
    # in its ORIGINAL project only. Deliberate: 05_PROJECTS §3a — what a project
    # holds now is answered from the project folder, not the registry.
    idx_a = os.path.join(nas, "projects", "alpha", "index.html")
    html_a = open(idx_a, encoding="utf-8").read() if os.path.isfile(idx_a) else ""
    check("ACQ-20260101-ZWSI-001" in html_a,
          "the acquisition stays in its original project's index.html")

    code, d = post(client, "/api/search_acqs",
                   {"nas_root": nas, "exclude_project": "PROJ-0001"})
    check(d["already_in_project"] >= 2,
          "the picker hides (and counts) what is already in the project")


def test_link_failure(client, nas, monkey):
    print("\n-- when the machine cannot make hard links --")
    from ingest import linker

    def boom(*a, **k):
        raise OSError(45, "Operation not supported")

    real = linker.create_hardlink
    linker.create_hardlink = boom
    try:
        lines, done = stream(client, "/api/import_raw", {
            "nas_root": nas, "project": "PROJ-0002",
            "acq_ids": ["ACQ-20260102-MRI-001"], "creator": "Tester"})
    finally:
        linker.create_hardlink = real

    check(done.get("queued") == 1 and done.get("failed") == 0,
          "an unsupported-link mount QUEUES rather than failing")
    check("your data is safe" in (done.get("summary") or ""),
          "the summary reassures the researcher nothing was lost")

    q = os.path.join(nas, "registries", "pending_links.csv")
    check(os.path.isfile(q), "the deferred-link worklist is written")
    with open(q, encoding="utf-8-sig", newline="") as f:
        qrows = list(csv.DictReader(f))
    check(len(qrows) == 1 and qrows[0]["acq_id"] == "ACQ-20260102-MRI-001",
          "the acquisition is on the worklist")
    check(qrows[0]["project_id"] == "PROJ-0002" and qrows[0]["status"] == "pending",
          "the worklist carries the recovery payload")
    check(qrows[0]["raw_primary_canonical"].startswith("/raw/"),
          "the raw primary is recorded share-relative, for the relink pass")

    standin = os.path.join(nas, "projects", "beta", "raw_linked",
                           "exam_42.PENDING-LINK.txt")
    check(os.path.isfile(standin),
          "a visible stand-in marks the spot so the folder isn't silently empty")

    # This acquisition was already registered to PROJ-0001 earlier in the run, so
    # write-once leaves it there. The queue — not the registry — is what carries
    # PROJ-0002 through to the relink pass (asserted above).
    reg = read_raw_registry(nas)
    check(reg["ACQ-20260102-MRI-001"]["project_id"] == "PROJ-0001",
          "a deferred link does not re-register the acquisition either")


def test_import_local(client, nas, tmp):
    print("\n-- add files from my computer --")
    src = os.path.join(tmp, "mydata")
    os.makedirs(src)
    for name, blob in (("figure.png", b"png-bytes"), ("notes.txt", b"hello")):
        with open(os.path.join(src, name), "wb") as f:
            f.write(blob)
    sources = [os.path.join(src, "figure.png"), os.path.join(src, "notes.txt")]

    code, d = post(client, "/api/import_local_plan", {
        "nas_root": nas, "project": "PROJ-0002", "sources": sources})
    check(code == 200 and d["totals"]["count"] == 2, "plan counts both files")
    check(d["totals"]["subfolder"] == "working",
          "the default destination is working/")

    lines, done = stream(client, "/api/import_local", {
        "nas_root": nas, "project": "PROJ-0002", "sources": sources,
        "creator": "Tester"})
    check(done.get("copied") == 2, "both files copied")
    beta = os.path.join(nas, "projects", "beta")
    check(os.path.isfile(os.path.join(beta, "working", "figure.png")),
          "the file lands in working/")
    check(os.path.isfile(os.path.join(src, "figure.png")),
          "the researcher's own copy stays put (copy, never move)")
    rows = {r["output_name"]: r for r in prov_rows(beta)}
    check(rows["figure.png"]["file_type"] == "png",
          "provenance records the file type from the extension")
    check(rows["figure.png"]["input_refs"] == sources[0],
          "provenance records where it came from")
    check(rows["figure.png"]["process_description"] == "Copied from local storage",
          "provenance says what happened")

    # Second time round: the destination exists.
    code, d = post(client, "/api/import_local_plan", {
        "nas_root": nas, "project": "PROJ-0002", "sources": sources})
    check(all(i["status"] == "exists" for i in d["items"]),
          "an existing destination is refused, not silently clobbered")
    check(d["totals"]["count"] == 0, "nothing is copyable without a confirm")
    code, d = post(client, "/api/import_local_plan", {
        "nas_root": nas, "project": "PROJ-0002", "sources": sources,
        "overwrite": ["figure.png"]})
    check(d["totals"]["count"] == 1,
          "an explicit per-file confirm unlocks exactly that file")

    code, d = post(client, "/api/import_local_plan", {
        "nas_root": nas, "project": "PROJ-0002", "sources": [src]})
    check(d["items"][0]["status"] == "source-missing",
          "a folder is reported, not silently walked")

    code, d = post(client, "/api/import_local_plan", {
        "nas_root": nas, "project": "PROJ-0002", "sources": sources,
        "subfolder": "raw_linked"})
    check(code == 400, "raw_linked/ is tool-managed and not an allowed target")

    code, d = post(client, "/api/import_local_plan", {
        "nas_root": nas, "project": "PROJ-0003", "sources": sources})
    check(code == 400 and "no folder" in d["error"],
          "a closed project with no folder cannot receive files")


def main():
    tmp = tempfile.mkdtemp(prefix="gj3_manager_")
    try:
        nas = build_nas(os.path.join(tmp, "nas"))
        sys.path.insert(0, os.path.join(_HERE, "manager", "gui"))
        import app as manager_app                       # noqa: E402
        manager_app.app.config["TESTING"] = True
        client = manager_app.app.test_client()

        test_projects(client, nas)
        test_create(client, nas)
        test_import_raw(client, nas)
        test_link_failure(client, nas, None)
        test_import_local(client, nas, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILED:
        print(f"{len(FAILED)} CHECK(S) FAILED")
        for m in FAILED:
            print(f"  - {m}")
        return 1
    print("ALL PROJECT-MANAGER CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
