"""Microscopy operator ingest GUI — local Flask web-app (Phase 4).

A dead-simple, browser-based front-end for the three microscopy instruments
(ZWSI / CELL / LSM9). It is a THIN front-end over the shared operator core
(`tools/operator/{templates,config_builder,scope,preview,runner,env}.py`) — it
never reimplements ingest logic; every preview/commit goes through the validated
pipeline via the core.

Two paths (per the build plan, Phase 4):

  RECIPE-RUNNER (the common case) — pick instrument -> pick a saved recipe ->
    point at a staging folder -> /api/preview renders the "what will happen"
    table (acq_id, project, link name, resolved registry row, X new / Y already
    ingested, warnings) -> /api/ingest streams the live ingest log (SSE).

  BUILDER (define a NEW convention) — edit the override dict and re-run
    /api/preview live: (a) positional separator+fields OR regex+source, plus
    path_parse levels + filter, with a live discovered.* grid over the first N
    real files (/api/discovered); (b) map registry.* + link_filename +
    project_hint + auto_create_project via clickable discovered.* token chips,
    each field showing a live resolved example. Save as a recipe (/api/save_recipe)
    to tools/operator/recipes/.

Run (dev):
    pip install flask
    python tools/operator/gui/app.py            # opens http://127.0.0.1:5000
Freeze: see tools/operator/gui/README.md + microscopy_ingest.spec.

This module loads the operator core through its non-colliding loader
(`tools/operator/_loader.py` -> alias `gj_op_core`) because the package
directory name `operator` collides with the stdlib `operator` module
(see tools/operator/IMPORT_CONTRACT.md). NEVER `import operator` here.
"""

import importlib.util
import json
import os
import sys
import threading
import webbrowser

# --- locate + load the operator core via its loader (stdlib-collision-safe) ---
# This file lives at tools/operator/gui/app.py; the package dir is its parent.
_GUI_DIR = os.path.dirname(os.path.abspath(__file__))
_PKG_DIR = os.path.dirname(_GUI_DIR)            # tools/operator/
_TOOLS_DIR = os.path.dirname(_PKG_DIR)          # tools/


def _load_core():
    """Load the operator package under its non-colliding alias and return it."""
    spec = importlib.util.spec_from_file_location(
        "gj_operator_loader", os.path.join(_PKG_DIR, "_loader.py")
    )
    loader_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader_mod)
    return loader_mod.load()


core = _load_core()
templates = core.templates
config_builder = core.config_builder
scope = core.scope
preview = core.preview
runner = core.runner
env = core.env

# Flask is imported after the core so a missing-flask error is obvious and
# does not mask a core-import problem.
from flask import Flask, jsonify, render_template, request, Response  # noqa: E402

app = Flask(__name__)

# Microscopy instruments this GUI serves. NI/MRI have their own Linux scripts.
MICROSCOPY_KEYS = ["ZWSI", "CELL", "LSM9"]
INSTRUMENT_LABELS = {
    "ZWSI": "AxioScan 7 (whole-slide)",
    "CELL": "Cell Observer (cells mode)",
    "LSM9": "LSM 900 (confocal)",
}

# How many real files to show in the builder's live discovered.* grid.
BUILDER_GRID_LIMIT = 25

# Controlled sample_type vocabulary — 06_REGISTRIES §2.4 (DRAFT, REG-07). Operators
# pick one verbatim; a new kind is a vocab-extension decision, not an ad-hoc value.
# Keep this list in sync with that table (value + a short operator-facing gloss).
SAMPLE_TYPES = [
    {"value": "tissue",   "label": "tissue — excised material (sections, slices, biopsies)"},
    {"value": "organism", "label": "organism — whole live or post-mortem animal"},
    {"value": "cells",    "label": "cells — cultured or isolated cell preparations"},
    {"value": "material", "label": "material — non-biological (nanoparticles, contrast agents)"},
    {"value": "phantom",  "label": "phantom — imaging calibration object"},
]

# Critical fields that MUST end up populated. A recipe may set them (stable per
# convention) or leave them blank; whatever it leaves blank is "pushed to the
# runner" — shown there as a required per-batch input (token-field, or the
# sample_type dropdown). See /api/recipe_gaps. `kind`: "token" (metadata-label +
# text) or "sampletype" (controlled vocabulary).
CRITICAL_FIELDS = [
    {"key": "registry.researcher",   "label": "Researcher",  "kind": "token",      "hint": "who ran the study"},
    {"key": "operator",              "label": "Operator",    "kind": "token",      "hint": "who ran the equipment"},
    {"key": "registry.sample_id",    "label": "Sample ID",   "kind": "token",      "hint": ""},
    {"key": "registry.sample_type",  "label": "Sample type", "kind": "sampletype", "hint": "controlled vocabulary"},
]


def _effective_value(cfg, key):
    """The effective config value for a critical-field key (template+overrides)."""
    if key.startswith("registry."):
        return (cfg.get("registry") or {}).get(key.split(".", 1)[1])
    return cfg.get(key)   # top-level keys: operator, link_filename, …


def _is_gap(val):
    """True when a value is effectively unset: empty / NA / a <placeholder>.
    A ${...} reference or a real literal is NOT a gap (it resolves at ingest)."""
    if val is None:
        return True
    s = str(val).strip()
    if s == "" or s.upper() == "NA":
        return True
    if s.startswith("<") and s.endswith(">"):   # e.g. "<set per batch>"
        return True
    return False


# --------------------------------------------------------------------- recipes

def recipes_dir():
    """Absolute path to the recipes directory (repo + frozen aware).

    Mirrors templates._candidate_dirs ordering: a frozen bundle's copy first,
    then the repo checkout at tools/operator/recipes/.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        for cand in (
            os.path.join(meipass, "tools", "operator", "recipes"),
            os.path.join(meipass, "operator", "recipes"),
            os.path.join(meipass, "recipes"),
        ):
            if os.path.isdir(cand):
                return cand
    return os.path.join(_PKG_DIR, "recipes")


def _load_recipe_file(path):
    """Load a recipe (JSON or YAML) to a dict. Returns None on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        if path.lower().endswith((".yaml", ".yml")):
            import yaml
            return yaml.safe_load(text)
        return json.loads(text)
    except Exception:  # noqa: BLE001 — a bad recipe file must not crash the list
        return None


def list_recipes():
    """Return [{file, name, instrument, description}] for all valid recipes."""
    out = []
    rdir = recipes_dir()
    if not os.path.isdir(rdir):
        return out
    for fn in sorted(os.listdir(rdir)):
        if not fn.lower().endswith((".json", ".yaml", ".yml")):
            continue
        rec = _load_recipe_file(os.path.join(rdir, fn))
        if not isinstance(rec, dict):
            continue
        out.append({
            "file": fn,
            "name": rec.get("name") or fn,
            "instrument": (rec.get("instrument") or "").upper(),
            "description": rec.get("description") or "",
            "overrides": rec.get("overrides") or {},
        })
    return out


# ------------------------------------------------------------ NAS-root persist

def _state_dir():
    """Per-user dir to persist the chosen NAS root (Windows %LOCALAPPDATA%)."""
    base = (
        os.environ.get("LOCALAPPDATA")
        or os.environ.get("XDG_STATE_HOME")
        or os.path.expanduser("~")
    )
    d = os.path.join(base, "gjesus3-operator")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def _nas_state_path():
    return os.path.join(_state_dir(), "nas_root.txt")


def load_saved_nas_root():
    """Return the persisted NAS root, or the env/default resolution."""
    try:
        with open(_nas_state_path(), "r", encoding="utf-8") as f:
            val = f.read().strip()
        if val:
            return val
    except OSError:
        pass
    return env.resolve_nas_root()


def save_nas_root(value):
    try:
        with open(_nas_state_path(), "w", encoding="utf-8") as f:
            f.write((value or "").strip())
    except OSError:
        pass


# ------------------------------------------------------------- config assembly

def _build_cfg(instrument, overrides, staging_path):
    """Template + scope(staging_path) + operator overrides -> in-memory cfg.

    `overrides` is the recipe/builder override dict (config_builder whitelist
    keys). `staging_path` is the folder the operator pointed at; scope.resolve_scope
    turns it into (staging_dir, pattern) which take precedence over any
    staging_dir/pattern in `overrides` (the operator's folder pick wins).

    Returns (cfg, template_path, resolved_staging_dir, resolved_pattern).
    """
    template = templates.load_template(instrument)
    tpl_path = templates.template_path(instrument)

    eff_overrides = dict(overrides or {})

    # Resolve "point at this folder" -> (staging_dir, pattern). The template's
    # own pattern is passed so the microscopy recursive fallback keeps a
    # path_parse-friendly glob. If the override set already pinned a pattern
    # (builder mode), honour it for the recursive fallback hint.
    if staging_path:
        tpl_pattern = (
            eff_overrides.get("auto_discover.pattern")
            or (template.get("auto_discover") or {}).get("pattern")
        )
        staging_dir, pattern = scope.resolve_scope(
            instrument, staging_path, template_pattern=tpl_pattern
        )
        eff_overrides["auto_discover.staging_dir"] = staging_dir
        # Only set the pattern from scope when the builder hasn't pinned one.
        eff_overrides.setdefault("auto_discover.pattern", pattern)
    else:
        staging_dir = (
            eff_overrides.get("auto_discover.staging_dir")
            or (template.get("auto_discover") or {}).get("staging_dir")
        )
        pattern = (
            eff_overrides.get("auto_discover.pattern")
            or (template.get("auto_discover") or {}).get("pattern")
        )

    cfg = config_builder.build_config(template, eff_overrides)
    return cfg, tpl_path, staging_dir, pattern


def _case_to_dict(cp):
    """CasePreview dataclass -> JSON-serialisable dict."""
    return {
        "source": cp.source,
        "original_name": cp.original_name,
        "discovered": cp.discovered,
        "registry_resolved": cp.registry_resolved,
        "acq_date": cp.acq_date,
        "acq_id": cp.acq_id_preview,
        "project": cp.project_preview,
        "link_filename": cp.link_filename_preview,
        "warnings": cp.warnings,
    }


# --------------------------------------------------------------------- routes

@app.route("/")
def index():
    return render_template(
        "index.html",
        instruments=[
            {"key": k, "label": INSTRUMENT_LABELS[k]} for k in MICROSCOPY_KEYS
        ],
        nas_root=load_saved_nas_root(),
        sample_types=SAMPLE_TYPES,
    )


@app.route("/api/instruments")
def api_instruments():
    return jsonify([
        {"key": k, "label": INSTRUMENT_LABELS[k]} for k in MICROSCOPY_KEYS
    ])


@app.route("/api/recipes")
def api_recipes():
    inst = (request.args.get("instrument") or "").upper()
    recs = list_recipes()
    if inst:
        recs = [r for r in recs if r["instrument"] == inst]
    return jsonify(recs)


@app.route("/api/template")
def api_template():
    """Return the template's auto_discover + registry + link_filename defaults
    so the builder can seed its editor with the instrument's locked convention.
    """
    inst = (request.args.get("instrument") or "").upper()
    try:
        tpl = templates.load_template(inst)
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 400
    return jsonify({
        "instrument": inst,
        "auto_discover": tpl.get("auto_discover") or {},
        "registry": tpl.get("registry") or {},
        "operator": tpl.get("operator") or "",   # top-level acquisition operator
        "link_filename": tpl.get("link_filename") or "",
        "auto_create_project": tpl.get("auto_create_project") or {},
        "ingest": tpl.get("ingest") or {},
        # The optional condition: block (08_METADATA §4.5). Present only for
        # tissue instruments (e.g. AxioScan); absent for the cell modes. The
        # runner uses its presence to decide whether to show the per-run
        # "Study metadata" panel.
        "condition": tpl.get("condition"),
    })


@app.route("/api/nas_root", methods=["GET", "POST"])
def api_nas_root():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        value = (data.get("nas_root") or "").strip()
        valid = env.is_valid_nas_root(value)
        if valid:
            save_nas_root(value)
        return jsonify({"nas_root": value, "valid": valid})
    nas_root = load_saved_nas_root()
    return jsonify({
        "nas_root": nas_root,
        "valid": env.is_valid_nas_root(nas_root),
    })


# Names that are never an ingest target and only clutter the browser.
_BROWSE_HIDE = {"system volume information", "$recycle.bin", "$recycle.bin"}

# Cap the entries returned for one folder (a huge data dir would bloat the page).
_BROWSE_LIMIT = 3000


def _list_drives():
    """Available drive roots (Windows) or '/' (POSIX), for the browser's jump bar."""
    if os.name == "nt":
        import string
        return [f"{c}:\\" for c in string.ascii_uppercase if os.path.exists(f"{c}:\\")]
    return ["/"]


@app.route("/api/listdir", methods=["POST"])
def api_listdir():
    """List one local folder for the in-page folder browser.

    The tkinter directory chooser shows ONLY folders (so every folder looks
    empty, which confused operators). Instead we render our own browser: this
    returns the folder's subfolders AND files (files are shown greyed, for
    context only), plus the parent + drive list to navigate. Local app, so
    listing the local filesystem is fine.
    """
    data = request.get_json(silent=True) or {}
    raw = (data.get("path") or "").strip()
    path = os.path.abspath(raw) if raw else os.path.expanduser("~")

    out = {"path": path, "parent": None, "entries": [],
           "drives": _list_drives(), "error": None, "truncated": False}

    if not os.path.isdir(path):
        out["error"] = f"Not a folder: {path}"
        path = os.path.expanduser("~")
        out["path"] = path

    parent = os.path.dirname(path)
    out["parent"] = parent if parent and os.path.normpath(parent) != os.path.normpath(path) else None

    try:
        entries = []
        with os.scandir(path) as it:
            for e in it:
                if e.name.lower() in _BROWSE_HIDE:
                    continue
                try:
                    is_dir = e.is_dir()
                except OSError:
                    is_dir = False
                entries.append({"name": e.name, "is_dir": is_dir})
        # folders first, then files; case-insensitive name order
        entries.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        if len(entries) > _BROWSE_LIMIT:
            out["truncated"] = True
            entries = entries[:_BROWSE_LIMIT]
        out["entries"] = entries
    except OSError as ex:
        out["error"] = str(ex)
    return jsonify(out)


@app.route("/api/recipe_gaps", methods=["POST"])
def api_recipe_gaps():
    """Which CRITICAL_FIELDS does this recipe leave blank? The runner renders a
    required per-batch input for each one returned. Computed on the EFFECTIVE
    config (template + recipe overrides), so a value the template supplies (even
    if the recipe doesn't override it) is not reported as a gap.
    """
    data = request.get_json(silent=True) or {}
    instrument = (data.get("instrument") or "").upper()
    overrides = data.get("overrides") or {}
    if instrument not in MICROSCOPY_KEYS:
        return jsonify({"gaps": []})
    try:
        template = templates.load_template(instrument)
        cfg = config_builder.build_config(template, overrides)
    except Exception as e:  # noqa: BLE001 — a bad recipe shouldn't 500 the runner
        return jsonify({"gaps": [], "error": str(e)})
    gaps = [f for f in CRITICAL_FIELDS if _is_gap(_effective_value(cfg, f["key"]))]
    return jsonify({"gaps": gaps})


@app.route("/api/sample_layout", methods=["POST"])
def api_sample_layout():
    """Sample the example source folder for the builder preview, anchored to the
    operator's chosen `levels` count (not the deepest path — a stray deep folder
    must not hijack the example).

    Returns a representative folder chain of EXACTLY `levels` deep that actually
    contains primary (<ext>) files, plus up to 3 of those file names. Also returns
    `file_depths` — the depths where <ext> files really live — so when `levels` is
    wrong the UI can point the operator at the right number.
    """
    data = request.get_json(silent=True) or {}
    raw = (data.get("path") or "").strip()
    try:
        levels = max(0, int(data.get("levels")))
    except (TypeError, ValueError):
        levels = 0
    ext = ".czi"   # all microscopy instruments this GUI serves are .czi
    out = {"root": "", "levels": levels, "chain": [], "files": [],
           "file_depths": [], "match": False, "ext": ext, "error": None}

    if not raw or not os.path.isdir(raw):
        out["error"] = "Pick an example source folder first."
        return jsonify(out)
    src = os.path.abspath(raw)
    out["root"] = os.path.basename(src.rstrip("\\/")) or src

    # Bounded walk: find a representative folder at EXACTLY `levels` deep that
    # directly holds <ext> files, and record every depth where <ext> files live.
    depths = set()
    seen = 0
    for dirpath, dirnames, filenames in os.walk(src):
        seen += 1
        if seen > 6000:
            break
        depth = 0 if os.path.normpath(dirpath) == os.path.normpath(src) else \
            len(os.path.relpath(dirpath, src).replace("\\", "/").split("/"))
        if depth > 12:
            dirnames[:] = []
            continue
        czi = sorted(f for f in filenames if f.lower().endswith(ext))
        if czi:
            depths.add(depth)
            if depth == levels and not out["match"]:
                out["match"] = True
                out["chain"] = ([] if depth == 0 else
                                os.path.relpath(dirpath, src).replace("\\", "/").split("/"))
                out["files"] = czi[:3]
    out["file_depths"] = sorted(depths)
    if not depths:
        out["error"] = f"No {ext} files found anywhere under this folder."
    return jsonify(out)


@app.route("/api/preview", methods=["POST"])
def api_preview():
    """Build a config from instrument + overrides + staging path and return the
    read-only PreviewResult as JSON (the recipe-runner table + builder live view).
    """
    data = request.get_json(silent=True) or {}
    instrument = (data.get("instrument") or "").upper()
    overrides = data.get("overrides") or {}
    staging_path = (data.get("staging_path") or "").strip()
    nas_root = (data.get("nas_root") or "").strip() or load_saved_nas_root()

    # Plain-language guards before we touch the pipeline.
    if instrument not in MICROSCOPY_KEYS:
        return jsonify({"error": f"Pick an instrument ({', '.join(MICROSCOPY_KEYS)})."}), 400
    try:
        env.validate_nas_root(nas_root)
    except env.NasRootError as e:
        return jsonify({"error": str(e)}), 400

    try:
        cfg, tpl_path, staging_dir, pattern = _build_cfg(
            instrument, overrides, staging_path
        )
    except scope.ScopeError as e:
        return jsonify({"error": str(e)}), 400
    except config_builder.OverrideError as e:
        return jsonify({"error": f"Bad override: {e}"}), 400
    except (KeyError, FileNotFoundError) as e:
        return jsonify({"error": str(e)}), 400

    try:
        result = preview.preview_batch(cfg, nas_root)
    except Exception as e:  # noqa: BLE001 — translate to a JSON error
        return jsonify({"error": f"Preview failed: {e}"}), 500

    return jsonify({
        "instrument": instrument,
        "staging_dir": staging_dir,
        "pattern": pattern,
        "template_path": tpl_path,
        "n_matched": result.n_matched,
        "n_new": result.n_new,
        "n_skipped": result.n_skipped,
        "n_already_ingested": result.n_already_ingested,
        "n_dropped": result.n_dropped,
        "dropped": result.dropped,
        "blocking_errors": result.blocking_errors,
        "warnings": result.warnings,
        "cases": [_case_to_dict(c) for c in result.cases],
    })


@app.route("/api/discovered", methods=["POST"])
def api_discovered():
    """Builder live grid: expand the first N cases and return JUST the
    discovered.* dicts (+ original_name) so the builder can render a grid of
    parsed fields over real files as the operator edits the parse rules.

    Reuses preview_batch (read-only) and truncates client-side-friendly.
    """
    data = request.get_json(silent=True) or {}
    instrument = (data.get("instrument") or "").upper()
    overrides = data.get("overrides") or {}
    staging_path = (data.get("staging_path") or "").strip()
    nas_root = (data.get("nas_root") or "").strip() or load_saved_nas_root()
    limit = int(data.get("limit") or BUILDER_GRID_LIMIT)

    if instrument not in MICROSCOPY_KEYS:
        return jsonify({"error": f"Pick an instrument ({', '.join(MICROSCOPY_KEYS)})."}), 400
    if not env.is_valid_nas_root(nas_root):
        # Discovered-grid doesn't truly need the registry, but expand_batch
        # dedups against it; an invalid root would explode. Surface it plainly.
        return jsonify({"error": "Set a valid NAS root first (registries/ subfolder)."}), 400

    try:
        cfg, _tpl, staging_dir, pattern = _build_cfg(
            instrument, overrides, staging_path
        )
        result = preview.preview_batch(cfg, nas_root)
    except scope.ScopeError as e:
        return jsonify({"error": str(e)}), 400
    except config_builder.OverrideError as e:
        return jsonify({"error": f"Bad override: {e}"}), 400
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": f"Discovery failed: {e}"}), 500

    # Union of discovered keys across the shown cases (stable, sorted-ish:
    # preserve first-seen order so positional fields read left-to-right).
    rows = []
    seen_keys = []
    for cp in result.cases[:limit]:
        for k in cp.discovered.keys():
            if k not in seen_keys:
                seen_keys.append(k)
        rows.append({
            "original_name": cp.original_name,
            "discovered": cp.discovered,
        })
    return jsonify({
        "staging_dir": staging_dir,
        "pattern": pattern,
        "n_matched": result.n_matched,
        "n_new": result.n_new,
        "n_already_ingested": result.n_already_ingested,
        "n_dropped": result.n_dropped,
        "dropped": result.dropped,
        "keys": seen_keys,
        "rows": rows,
        "warnings": result.warnings,
    })


@app.route("/api/save_recipe", methods=["POST"])
def api_save_recipe():
    """Persist a recipe (instrument + name + override dict) to recipes_dir().

    Writes JSON. Refuses to write outside recipes_dir() (basename only).
    """
    data = request.get_json(silent=True) or {}
    instrument = (data.get("instrument") or "").upper()
    name = (data.get("name") or "").strip()
    overrides = data.get("overrides") or {}
    description = (data.get("description") or "").strip()

    if instrument not in MICROSCOPY_KEYS:
        return jsonify({"error": f"Pick an instrument ({', '.join(MICROSCOPY_KEYS)})."}), 400
    if not name:
        return jsonify({"error": "Give the recipe a name."}), 400

    # Derive a safe filename from the name.
    safe = "".join(
        c if (c.isalnum() or c in "-_") else "_" for c in name.lower()
    ).strip("_") or "recipe"
    fname = f"{safe}.json"
    rdir = recipes_dir()
    try:
        os.makedirs(rdir, exist_ok=True)
    except OSError as e:
        return jsonify({"error": f"Cannot create recipes folder: {e}"}), 500

    target = os.path.join(rdir, os.path.basename(fname))
    payload = {
        "schema": "gjesus3.operator.recipe/v1",
        "name": name,
        "instrument": instrument,
        "description": description,
        "overrides": overrides,
    }
    try:
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except OSError as e:
        return jsonify({"error": f"Cannot write recipe: {e}"}), 500

    return jsonify({"file": fname, "path": target})


@app.route("/api/ingest", methods=["POST"])
def api_ingest():
    """Commit path: stream the live ingest log via Server-Sent Events.

    Builds the same config the preview used, then calls runner.run with a
    log_callback that pushes each (msg, level) line down the SSE stream. The
    final event carries the per-acq results. dry_run honoured for a safe test.
    """
    data = request.get_json(silent=True) or {}
    instrument = (data.get("instrument") or "").upper()
    overrides = data.get("overrides") or {}
    staging_path = (data.get("staging_path") or "").strip()
    nas_root = (data.get("nas_root") or "").strip() or load_saved_nas_root()
    dry_run = bool(data.get("dry_run"))
    recipe_path = (data.get("recipe_path") or "").strip() or None

    if instrument not in MICROSCOPY_KEYS:
        return jsonify({"error": f"Pick an instrument ({', '.join(MICROSCOPY_KEYS)})."}), 400
    try:
        env.validate_nas_root(nas_root)
    except env.NasRootError as e:
        return jsonify({"error": str(e)}), 400

    try:
        cfg, tpl_path, _staging_dir, _pattern = _build_cfg(
            instrument, overrides, staging_path
        )
    except scope.ScopeError as e:
        return jsonify({"error": str(e)}), 400
    except config_builder.OverrideError as e:
        return jsonify({"error": f"Bad override: {e}"}), 400
    except (KeyError, FileNotFoundError) as e:
        return jsonify({"error": str(e)}), 400

    stamp = recipe_path or runner.default_recipe_path(tpl_path)

    def generate():
        import queue
        q = queue.Queue()
        SENTINEL = object()

        def cb(msg, level="INFO"):
            q.put(("log", level, str(msg)))

        def worker():
            try:
                results = runner.run(
                    cfg, nas_root, dry_run=dry_run,
                    log_callback=cb, recipe_path=stamp,
                )
                ok = sum(1 for _aid, good in results if good)
                q.put(("done", "INFO", json.dumps({
                    "results": [
                        {"acq_id": aid, "ok": bool(good)}
                        for aid, good in results
                    ],
                    "ok": ok,
                    "total": len(results),
                    "dry_run": dry_run,
                })))
            except Exception as e:  # noqa: BLE001 — report to the stream
                q.put(("error", "ERROR", str(e)))
            finally:
                q.put(SENTINEL)

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        while True:
            item = q.get()
            if item is SENTINEL:
                break
            kind, level, msg = item
            payload = json.dumps({"kind": kind, "level": level, "msg": msg})
            yield f"data: {payload}\n\n"

    return Response(generate(), mimetype="text/event-stream")


# --------------------------------------------------------------------- runner

def _open_browser(url):
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(
        description="Microscopy operator ingest GUI (local Flask web-app)."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Do not auto-open the default browser.",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Run Flask in debug mode (reloader off to keep the core load sane).",
    )
    args = parser.parse_args(argv)

    url = f"http://{args.host}:{args.port}/"
    if not args.no_browser:
        # Open the browser shortly after the server starts.
        threading.Timer(1.0, _open_browser, args=(url,)).start()
    # use_reloader=False: the reloader re-execs the process, which re-runs the
    # core loader and double-opens the browser; not wanted for a packaged app.
    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)


if __name__ == "__main__":
    main()
