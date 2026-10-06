"""Project Manager GUI — local Flask web-app for researchers.

The researcher-facing counterpart to the operator ingest GUI. Four things:

  UPDATE   list every project from `registry_projects.csv`, show the whole row,
           edit `description` / `owner` / `status` / `notes`.
  CREATE   a new project — the registry row, the folder, `_project.yaml`, the
           empty `provenance.csv` and the recommended subfolders.
  ADD FROM THE RDM SYSTEM   search `/raw/` like the Finder, tick acquisitions,
           add them to a project as hard links + provenance.
  ADD FROM MY COMPUTER      browse local or mounted storage, tick files, copy
           them into a chosen subfolder + provenance.

A THIN front-end. Everything it does lives in `tools/manager/` and
`tools/ingest/`, so nothing here reimplements a rule and a script can perform
the same operations. New projects go through `create_project.create_project`;
imports go through `manager.raw_import` / `manager.local_import`.

SEPARATE APP, SEPARATE EXE — and deliberately as similar to the ingest GUI as
possible. Different audience (researchers vs. operators) and, decisively, a
different release cadence: folding this into `gjesus3_ingest.exe` would make
every project-manager tweak force a redeploy of the production ingest exe. But
a dedicated RDM server is expected around Oct 2026, after which both become one
web app; so this shares the ingest GUI's stylesheet, its folder browser, its
`/api/*` JSON shape, its SSE commit streams and its saved-state mechanism,
rather than inventing better versions of any of them. Where the choice was
"clever and different" vs. "boring and identical", it is identical.

Run (dev), from the repo root:
    pip install flask pyyaml
    python tools/manager/gui/app.py       # opens http://127.0.0.1:5001
Freeze: see gjesus3_manager.spec.

NEVER `import operator` anywhere in this tree — the package dir
`tools/operator/` collides with the stdlib module (tools/operator/IMPORT_CONTRACT.md).
This app does not need the operator core at all; it only borrows its static
assets, which are served as files (see `/shared/<path>` below).
"""

import json
import os
import queue
import sys
import threading
import webbrowser

# --- locate the repo `tools/` dir in BOTH source and frozen runs -------------
# Source layout: this file is tools/manager/gui/app.py. Frozen (PyInstaller):
# __file__ points at the exe dir, NOT under tools/manager/gui/, so the
# source-relative derivation would look beside the exe and fail. The spec maps
# the whole tree under sys._MEIPASS/tools/..., so derive from _MEIPASS when
# frozen — the same pattern the operator GUI uses.
if getattr(sys, "frozen", False):
    _TOOLS_DIR = os.path.join(sys._MEIPASS, "tools")
    _PKG_DIR = os.path.join(_TOOLS_DIR, "manager")
    _GUI_DIR = os.path.join(_PKG_DIR, "gui")
    _SHARED_STATIC = os.path.join(_TOOLS_DIR, "operator", "gui", "static")
else:
    _GUI_DIR = os.path.dirname(os.path.abspath(__file__))
    _PKG_DIR = os.path.dirname(_GUI_DIR)            # tools/manager/
    _TOOLS_DIR = os.path.dirname(_PKG_DIR)          # tools/
    _SHARED_STATIC = os.path.join(_TOOLS_DIR, "operator", "gui", "static")

if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import filebrowse                                          # noqa: E402
import create_project as create_project_mod                 # noqa: E402
from ingest import project_layout, projects_registry        # noqa: E402
from manager import acq_search, local_import, projects, raw_import  # noqa: E402

# Flask last, so a missing-flask error is obvious and does not mask a core
# import problem.
from flask import (Flask, jsonify, render_template, request,  # noqa: E402
                   send_from_directory, Response)

app = Flask(
    __name__,
    template_folder=os.path.join(_GUI_DIR, "templates"),
    static_folder=os.path.join(_GUI_DIR, "static"),
)

# Default RDM System root pre-filled when nothing has been chosen. Researchers
# run this on Windows machines that reach the NAS over SMB at this UNC — the
# shared `/mnt/gjesus3` default is the WSL/Linux data-office path and wrong here.
GUI_DEFAULT_NAS_ROOT = r"\\gjesus3\gjesus3\gjesus3-data"

STATE_DIR_NAME = "gjesus3-manager"
# The ingest GUI's state dir. Read ONLY as a seed: on a machine that already
# runs the ingest tools the RDM System root is already chosen, and asking for it
# again would be a pointless first-run step. The manager saves to its own file,
# so the two never fight.
OPERATOR_STATE_DIR_NAME = "gjesus3-operator"

TOOL_NAME = "project_manager"


# ------------------------------------------------------------ saved NAS root

def _state_dir(name=STATE_DIR_NAME):
    base = (os.environ.get("LOCALAPPDATA")
            or os.environ.get("XDG_STATE_HOME")
            or os.path.expanduser("~"))
    d = os.path.join(base, name)
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def _nas_state_path():
    return os.path.join(_state_dir(), "nas_root.txt")


def _read_state_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def load_saved_nas_root():
    """Saved choice > $GJESUS3_ROOT > the ingest GUI's saved choice > default."""
    return (_read_state_file(_nas_state_path())
            or os.environ.get("GJESUS3_ROOT")
            or _read_state_file(os.path.join(_state_dir(OPERATOR_STATE_DIR_NAME),
                                             "nas_root.txt"))
            or GUI_DEFAULT_NAS_ROOT)


def save_nas_root(value):
    try:
        with open(_nas_state_path(), "w", encoding="utf-8") as f:
            f.write((value or "").strip())
    except OSError:
        pass


def is_valid_nas_root(nas_root):
    """A real RDM System root is a dir containing `registries/`.

    Same rule as `operator/env.py::is_valid_nas_root`, restated rather than
    imported so this app needs no loader shim for the stdlib-colliding
    `operator` package. Without the check, a typo'd path is silently CREATED by
    native Python and the tool writes into a phantom tree.
    """
    return bool(nas_root) and os.path.isdir(nas_root) and os.path.isdir(
        os.path.join(nas_root, "registries"))


def _require_nas(data):
    """(nas_root, error_response_or_None) for a request body."""
    nas_root = (data.get("nas_root") or "").strip() or load_saved_nas_root()
    if not is_valid_nas_root(nas_root):
        return nas_root, (jsonify({"error": (
            f"That is not the RDM System: {nas_root!r}. Pick the folder that "
            f"contains 'registries' (usually \\\\gjesus3\\gjesus3\\gjesus3-data "
            f"or J:\\gjesus3-data)."
        )}), 400)
    return nas_root, None


# --------------------------------------------------------------------- pages

@app.route("/")
def index():
    return render_template(
        "index.html",
        nas_root=load_saved_nas_root(),
        statuses=projects_registry.STATUS_VALUES,
        editable=projects_registry.EDITABLE_FIELDS,
        subfolders=project_layout.PROJECT_SUBFOLDERS,
        dest_choices=local_import.DEST_CHOICES,
        default_dest=local_import.DEFAULT_DEST,
    )


@app.route("/shared/<path:filename>")
def shared_static(filename):
    """Serve the ingest GUI's static assets (style.css, folder_browser.js, …).

    §2.1: do NOT copy `folder_browser.js`. The branch that just landed existed
    partly to delete exactly that duplication between the ingest app's two
    pages, so this app serves the same files from the same directory instead of
    forking them. One stylesheet, one folder-browser component, both apps.
    """
    return send_from_directory(_SHARED_STATIC, filename)


# ----------------------------------------------------------------- RDM System

@app.route("/api/nas_root", methods=["GET", "POST"])
def api_nas_root():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        value = (data.get("nas_root") or "").strip()
        valid = is_valid_nas_root(value)
        if valid:
            save_nas_root(value)
            acq_search.invalidate(value)
        return jsonify({"nas_root": value, "valid": valid})
    nas_root = load_saved_nas_root()
    return jsonify({"nas_root": nas_root, "valid": is_valid_nas_root(nas_root)})


@app.route("/api/listdir", methods=["POST"])
def api_listdir():
    """The in-page folder/file browser's listing — shared with the ingest GUI."""
    data = request.get_json(silent=True) or {}
    return jsonify(filebrowse.list_folder(
        data.get("path"), desc=bool(data.get("desc")),
        with_size=bool(data.get("with_size")),
    ))


# ------------------------------------------------------------------- projects

@app.route("/api/projects", methods=["POST"])
def api_projects():
    data = request.get_json(silent=True) or {}
    nas_root, err = _require_nas(data)
    if err:
        return err
    rows = projects.list_projects(nas_root)
    return jsonify({
        "projects": rows,
        "counts": {
            "total": len(rows),
            "with_folder": sum(1 for r in rows if r["folder_exists"]),
            "no_folder": sum(1 for r in rows if not r["folder_exists"]),
        },
    })


@app.route("/api/project", methods=["POST"])
def api_project():
    """One project: its registry row, folder facts and `_project.yaml`."""
    data = request.get_json(silent=True) or {}
    nas_root, err = _require_nas(data)
    if err:
        return err
    rec = projects.get_project(nas_root, (data.get("project") or "").strip())
    if not rec:
        return jsonify({"error": "No such project."}), 404
    rec = dict(rec)
    rec["yaml"] = (project_layout.read_project_yaml(rec["folder_path"])
                   if rec.get("folder_exists") else None)
    return jsonify(rec)


@app.route("/api/update_project", methods=["POST"])
def api_update_project():
    data = request.get_json(silent=True) or {}
    nas_root, err = _require_nas(data)
    if err:
        return err
    project_id = (data.get("project_id") or "").strip()
    updates = {k: (data.get("updates") or {}).get(k)
               for k in projects_registry.EDITABLE_FIELDS
               if k in (data.get("updates") or {})}
    if not project_id:
        return jsonify({"error": "Pick a project first."}), 400
    if not updates:
        return jsonify({"error": "Nothing to save."}), 400
    try:
        applied, yaml_changed, warnings = projects.update_project(
            nas_root, project_id, updates)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except (OSError, RuntimeError) as e:
        return jsonify({"error": f"Could not save: {e}"}), 500
    return jsonify({"applied": applied, "yaml_changed": yaml_changed,
                    "warnings": warnings})


@app.route("/api/check_project_name", methods=["POST"])
def api_check_project_name():
    """Live name check as the researcher types — normalization + uniqueness.

    Surfaced BEFORE submission (the space -> hyphen rule especially), because
    the ingest GUI already does this for its "Project name" field and someone
    who has seen that will expect the same behaviour here.
    """
    data = request.get_json(silent=True) or {}
    nas_root, err = _require_nas(data)
    if err:
        return err
    name, errors = projects.validate_new_name(nas_root, data.get("name"))
    return jsonify({"name": name, "errors": errors,
                    "folder": f"projects/{name}" if name and not errors else ""})


@app.route("/api/create_project", methods=["POST"])
def api_create_project():
    """Create a project — a front-end over `create_project.create_project`.

    Anyone with access may create a project; what stays central is the
    MECHANISM, not the permission (2026-08-11). Going through this endpoint is
    what guarantees the registry row, the folder name, the subfolders and
    `_project.yaml` are all consistent — which hand-making a folder in
    `projects/` does not.
    """
    data = request.get_json(silent=True) or {}
    nas_root, err = _require_nas(data)
    if err:
        return err
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()
    owner = (data.get("owner") or "").strip()
    notes = (data.get("notes") or "").strip()
    if not name or not description or not owner:
        return jsonify({"error": "Name, description and owner are all "
                                 "required."}), 400

    norm, errors = projects.validate_new_name(nas_root, name)
    if errors:
        return jsonify({"error": "\n".join(errors), "name": norm}), 400

    lines = []
    _orig_log = create_project_mod.log
    create_project_mod.log = lambda m, level="INFO": lines.append(f"{level}: {m}")
    try:
        project_id, ok = create_project_mod.create_project(
            norm, description, owner, nas_root, notes=notes)
    except (OSError, RuntimeError) as e:
        return jsonify({"error": f"Could not create the project: {e}",
                        "log": lines}), 500
    finally:
        create_project_mod.log = _orig_log

    if not ok:
        return jsonify({"error": "\n".join(lines) or "Could not create the "
                                 "project.", "log": lines}), 400
    acq_search.invalidate(nas_root)
    return jsonify({"project_id": project_id, "name": norm, "log": lines,
                    "subfolders": project_layout.SUBFOLDER_NAMES})


# ----------------------------------------------------------- import from raw

@app.route("/api/search_acqs", methods=["POST"])
def api_search_acqs():
    """The acquisition picker — the Finder's filters, served, not re-rendered."""
    data = request.get_json(silent=True) or {}
    nas_root, err = _require_nas(data)
    if err:
        return err
    try:
        out = acq_search.search(
            nas_root,
            query=(data.get("query") or "").strip(),
            instrument=(data.get("instrument") or "").strip(),
            researcher=(data.get("researcher") or "").strip(),
            subject=(data.get("subject") or "").strip(),
            anatomy=(data.get("anatomy") or "").strip(),
            project=(data.get("project") or "").strip(),
            since=(data.get("since") or "").strip(),
            until=(data.get("until") or "").strip(),
            exclude_project=(data.get("exclude_project") or "").strip(),
            offset=data.get("offset") or 0,
        )
    except Exception as e:  # noqa: BLE001 — translate to a JSON error
        return jsonify({"error": f"Search failed: {e}"}), 500
    return jsonify(out)


def _raw_target(data):
    """(nas_root, project_row, acq_rows, error_response_or_None)."""
    nas_root, err = _require_nas(data)
    if err:
        return None, None, None, err
    project = projects.get_project(nas_root, (data.get("project") or "").strip())
    if not project:
        return None, None, None, (jsonify({"error": "Pick a project."}), 400)
    if not project.get("folder_exists"):
        return None, None, None, (jsonify({"error": (
            f"{project['project_id']} has no folder on the share — it was "
            f"closed and its folder deleted, so data cannot be added to it."
        )}), 400)
    acq_ids = [a for a in (data.get("acq_ids") or []) if isinstance(a, str)]
    if not acq_ids:
        return None, None, None, (jsonify({"error": "Tick at least one "
                                                    "acquisition."}), 400)
    rows = acq_search.rows_for(nas_root, acq_ids)
    return nas_root, project, rows, None


@app.route("/api/import_raw_plan", methods=["POST"])
def api_import_raw_plan():
    """What WOULD happen — the confirm step, with editable link names."""
    data = request.get_json(silent=True) or {}
    nas_root, project, rows, err = _raw_target(data)
    if err:
        return err
    items = raw_import.plan(nas_root, project, rows,
                            link_names=data.get("link_names") or {})
    return jsonify({
        "project": {k: project.get(k) for k in
                    ("project_id", "name", "folder_location", "status")},
        "items": items,
        "n_new": sum(1 for i in items if i["status"] == raw_import.ST_NEW),
    })


@app.route("/api/import_raw", methods=["POST"])
def api_import_raw():
    """Commit: link the ticked acquisitions, streaming the log as SSE."""
    data = request.get_json(silent=True) or {}
    nas_root, project, rows, err = _raw_target(data)
    if err:
        return err
    creator = (data.get("creator") or "").strip()
    if not creator:
        return jsonify({"error": "Say who is adding this data — it is recorded "
                                 "in the project's provenance."}), 400
    link_names = data.get("link_names") or {}

    def work(emit):
        result = raw_import.import_acquisitions(
            nas_root, project, rows, creator, link_names=link_names,
            log=emit, tool_name=TOOL_NAME)
        acq_search.invalidate(nas_root)
        _refresh_index(nas_root, [result["project_id"]], emit)
        return {**{k: v for k, v in result.items() if k != "results"},
                "summary": raw_import.summary_sentence(result),
                "results": result["results"]}

    return _sse(work)


# --------------------------------------------------------- import from local

def _local_target(data):
    """(project_row, sources, subfolder, overwrite, error_response_or_None)."""
    nas_root, err = _require_nas(data)
    if err:
        return None, None, None, None, None, err
    project = projects.get_project(nas_root, (data.get("project") or "").strip())
    if not project:
        return None, None, None, None, None, (jsonify({"error": "Pick a project."}), 400)
    if not project.get("folder_exists"):
        return None, None, None, None, None, (jsonify({"error": (
            f"{project['project_id']} has no folder on the share — it was "
            f"closed and its folder deleted, so files cannot be copied into it."
        )}), 400)
    sources = [s for s in (data.get("sources") or []) if isinstance(s, str)]
    if not sources:
        return None, None, None, None, None, (jsonify({"error": "Choose at "
                                                       "least one file."}), 400)
    subfolder = data.get("subfolder")
    if subfolder is None:
        subfolder = local_import.DEFAULT_DEST
    overwrite = [o for o in (data.get("overwrite") or []) if isinstance(o, str)]
    return nas_root, project, sources, subfolder, overwrite, None


@app.route("/api/import_local_plan", methods=["POST"])
def api_import_local_plan():
    data = request.get_json(silent=True) or {}
    nas_root, project, sources, subfolder, overwrite, err = _local_target(data)
    if err:
        return err
    try:
        items, totals = local_import.plan(project["folder_path"], sources,
                                          subfolder, overwrite)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"items": items, "totals": totals})


@app.route("/api/import_local", methods=["POST"])
def api_import_local():
    data = request.get_json(silent=True) or {}
    nas_root, project, sources, subfolder, overwrite, err = _local_target(data)
    if err:
        return err
    creator = (data.get("creator") or "").strip()
    if not creator:
        return jsonify({"error": "Say who is adding these files — it is "
                                 "recorded in the project's provenance."}), 400

    def work(emit):
        result = local_import.copy_files(
            project["folder_path"], sources, creator, subfolder=subfolder,
            overwrite=overwrite, log=emit, tool_name=TOOL_NAME)
        return result

    return _sse(work)


# --------------------------------------------------------------------- plumbing

def _refresh_index(nas_root, project_ids, emit):
    """Regenerate just the touched project(s) `index.html`.

    The cheap targeted path (`generate_index --project`) the ingest GUI already
    uses — NEVER the ~19 MB global index, which is the scheduled job's job.
    Best-effort: a refresh failure must never make a completed import look like
    it failed.
    """
    try:
        import generate_index
        for pid in project_ids:
            if pid:
                generate_index.main(["--nas-root", nas_root, "--project", pid])
        if project_ids:
            emit(f"Refreshed the project's Finder page ({', '.join(project_ids)}).")
    except Exception as e:  # noqa: BLE001 — never fail over a refresh
        emit(f"Could not refresh the project's Finder page (non-fatal): {e}",
             "WARN")


def _sse(work):
    """Run `work(emit)` in a thread and stream its log as Server-Sent Events.

    The same shape as the ingest GUI's commit stream: each log line becomes a
    `data: {...}` event and the final `done` event carries the result payload.
    Identical on purpose — one idiom for "a long thing is happening", so the two
    apps feel like one tool and fold together cheaply when the server lands.
    """
    def generate():
        q = queue.Queue()
        SENTINEL = object()

        def emit(msg, level="INFO"):
            q.put(("log", level, str(msg)))

        def worker():
            try:
                payload = work(emit)
                q.put(("done", "INFO", json.dumps(payload, default=str)))
            except Exception as e:  # noqa: BLE001 — report to the stream
                q.put(("error", "ERROR", str(e)))
            finally:
                q.put(SENTINEL)

        threading.Thread(target=worker, daemon=True).start()
        while True:
            item = q.get()
            if item is SENTINEL:
                break
            kind, level, msg = item
            yield f"data: {json.dumps({'kind': kind, 'level': level, 'msg': msg})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


def _open_browser(url):
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(
        description="Project Manager GUI (local Flask web-app).")
    parser.add_argument("--host", default="127.0.0.1")
    # 5001, not 5000: a researcher may have the ingest GUI open at the same time.
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--no-browser", action="store_true",
                        help="Do not auto-open the default browser.")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    url = f"http://{args.host}:{args.port}/"
    if not args.no_browser:
        threading.Timer(1.0, _open_browser, args=(url,)).start()
    # use_reloader=False: the reloader re-execs the process, which double-opens
    # the browser; not wanted for a packaged app.
    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)


if __name__ == "__main__":
    main()
