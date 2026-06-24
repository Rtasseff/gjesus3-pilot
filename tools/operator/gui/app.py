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
Freeze: see tools/operator/gui/README.md + gjesus3_ingest.spec.

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
# Source layout: this file lives at tools/operator/gui/app.py, so the package
# dir is its parent's parent. Frozen (PyInstaller): __file__ points at the exe
# dir, NOT under tools/operator/gui/, so the source-relative derivation would
# look for _loader.py beside the exe and fail. The spec maps the whole tree
# under sys._MEIPASS/tools/..., so derive the dirs from _MEIPASS when frozen.
if getattr(sys, "frozen", False):
    _TOOLS_DIR = os.path.join(sys._MEIPASS, "tools")          # <bundle>/tools
    _PKG_DIR = os.path.join(_TOOLS_DIR, "operator")           # tools/operator/
    _GUI_DIR = os.path.join(_PKG_DIR, "gui")                  # tools/operator/gui/
else:
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
# Sibling operator module: project-link collision detection for the MRI page.
# Imported under the package alias so it shares the loader's import footing
# (never `import collisions` bare — keep all operator imports package-qualified).
collisions = importlib.import_module(f"{core.__name__}.collisions")

# Flask is imported after the core so a missing-flask error is obvious and
# does not mask a core-import problem.
from flask import Flask, jsonify, render_template, request, Response  # noqa: E402

# Point Flask at the bundled templates/static explicitly so render_template /
# url_for resolve in BOTH source and frozen runs (in the frozen bundle they
# live under <_MEIPASS>/tools/operator/gui/, not beside the exe). In source mode
# _GUI_DIR is the real gui dir, so this matches Flask's default.
app = Flask(
    __name__,
    template_folder=os.path.join(_GUI_DIR, "templates"),
    static_folder=os.path.join(_GUI_DIR, "static"),
)

# Microscopy instruments this GUI serves. NI/MRI have their own Linux scripts.
MICROSCOPY_KEYS = ["ZWSI", "CELL", "LSM9"]
INSTRUMENT_LABELS = {
    "ZWSI": "AxioScan 7 (whole-slide)",
    "CELL": "Cell Observer (cells mode)",
    "LSM9": "LSM 900 (confocal)",
}

# How many real files to show in the builder's live discovered.* grid.
BUILDER_GRID_LIMIT = 25

# Default NAS root pre-filled in the GUI when the operator hasn't saved one. The
# GUI runs on the microscopy operators' Windows machines, which reach the NAS
# over SMB at this UNC — the shared env default (`/mnt/gjesus3`) is the WSL/Linux
# data-office path and wrong here. The operator's saved choice and an explicit
# $GJESUS3_ROOT both still win (see load_saved_nas_root).
GUI_DEFAULT_NAS_ROOT = r"\\gjesus3\gjesus3\gjesus3-data"

# --- MRI (Bruker ParaVision) mode -------------------------------------------
# A SEPARATE, deliberately-simple page (/mri) over the SAME shared core. Unlike
# the microscopy recipe/builder UI, MRI has one locked convention (the
# mri_bruker template); the operator only chooses a destination project and (if
# linking) edits the project-link name. NOT a recipe system.
MRI_KEY = "MRI"
MRI_LABEL = "Internal MRI (Bruker ParaVision)"
# --model -> registry.instrument_model (same map as tools/operator/mri_ingest.py).
_MRI_MODEL_MAP = {"7T": "Bruker BioSpec 7T", "11.7T": "Bruker BioSpec 11.7T"}
# discovered.* fields offered as link-name palette chips (the scan-name +
# protocol fields the mri_bruker template exposes), plus resolver-supplied extras.
MRI_LINK_PALETTE_KEYS = [
    "mri_exam_number", "mri_recon_indices", "mri_sequence_name",
    "animal_num", "project_code", "mri_study_name",
]
MRI_LINK_PALETTE_EXTRAS = ["${sample_id}", "${acq_date}", "${acq_id}",
                           "${original_name}"]

# --- MRI remote-pull (SFTP) source ------------------------------------------
# Pull ParaVision study folders off the acquisition console over SFTP, then
# ingest the local copy through the same MRI path. READ-ONLY on the remote
# (list + download only — never writes there). Host + creds + source roots are
# documented in equipment/historical_data_archives.md §MRI; creds resolve via
# env.ftp_creds() (GJESUS3_FTP_* env vars > ~/.ssh/gjesus3_mri.cred). The two
# roots are the concurrent ParaVision versions on the box.
MRI_SFTP_ROOTS = [
    {"path": "/opt/PV-7.0.0/data/nmr", "label": "ParaVision 7.0.0"},
    {"path": "/opt/PV6.0.1/data/nmr",  "label": "ParaVision 6.0.1"},
]
# MFB naming convention: every MFB study folder carries the PI initials "jrc"
# (Jesus Ruiz-Cabello). This is also what the mri_bruker ingest regex keys on,
# so non-jrc folders wouldn't ingest anyway. Default the remote list to jrc-only.
MRI_SFTP_FILTER = "jrc"
# Where pulled study folders land locally (one batch subfolder per pull). The
# operator can override per pull; this is the documented MRI staging root.
MRI_PULL_STAGING_ROOT = r"D:\projects\mri"
# Safety cap: never mirror more than this many studies in one pull request.
MRI_PULL_MAX_STUDIES = 50

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
    {"key": "registry.researcher",   "label": "Researcher",       "kind": "token",      "hint": "who ran the study",        "required": True},
    {"key": "registry.sample_id",    "label": "Sample ID",        "kind": "token",      "hint": "",                         "required": True},
    {"key": "registry.sample_type",  "label": "Sample type",      "kind": "sampletype", "hint": "controlled vocabulary",    "required": True},
    {"key": "operator",              "label": "Operator",         "kind": "token",      "hint": "who ran the equipment",    "required": False},
    {"key": "registry.project_hint", "label": "Project hint",     "kind": "token",      "hint": "link to a project",        "required": False},
    {"key": "link_filename",         "label": "Project link name", "kind": "token",     "hint": "the file name if left blank", "required": False},
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

def _legacy_recipes_dir():
    """The original bundled/repo recipes location — kept as a read-only SEED
    source so recipes that shipped with the tool still appear after the default
    moved to the NAS. (frozen _MEIPASS-aware; else the repo tools/operator/recipes.)
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


def default_recipes_dir():
    """Default recipes location: <nas_root>/recipes on shared primary storage, so
    every operator (who no longer has the repo checkout) reads + writes the same
    shared, self-documenting set. Falls back to a per-user local dir when no NAS
    is set yet, so Save never hard-fails.
    """
    nas = load_saved_nas_root()
    if nas and os.path.isdir(nas):
        return os.path.normpath(os.path.join(nas, "recipes"))
    return os.path.normpath(os.path.join(_state_dir(), "recipes"))


def recipes_dir():
    """Where recipes are SAVED (and primarily listed): the operator's persisted
    choice, else the NAS default (<nas_root>/recipes)."""
    return load_saved_recipes_dir() or default_recipes_dir()


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
    """Return [{file, path, name, instrument, description, overrides}] for all
    valid recipes — from the configured (NAS) dir first, then the bundled seed
    dir (de-duped by filename; the configured dir wins)."""
    out = []
    seen = set()
    dirs = [recipes_dir(), _legacy_recipes_dir()]
    for rdir in dirs:
        if not rdir or not os.path.isdir(rdir):
            continue
        for fn in sorted(os.listdir(rdir)):
            if not fn.lower().endswith((".json", ".yaml", ".yml")):
                continue
            if fn in seen:
                continue
            rec = _load_recipe_file(os.path.join(rdir, fn))
            if not isinstance(rec, dict):
                continue
            seen.add(fn)
            out.append({
                "file": fn,
                "path": os.path.join(rdir, fn),
                "name": rec.get("name") or fn,
                "instrument": (rec.get("instrument") or "").upper(),
                "description": rec.get("description") or "",
                "overrides": rec.get("overrides") or {},
            })
    out.sort(key=lambda r: r["name"].lower())
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
    """Return the persisted NAS root, or the GUI default.

    Precedence: the operator's saved choice > $GJESUS3_ROOT > GUI_DEFAULT_NAS_ROOT
    (the Windows-SMB UNC). We do NOT fall back to env.resolve_nas_root()'s
    `/mnt/gjesus3` default, which is the WSL/Linux data-office path — wrong for a
    Windows GUI operator who has never set one.
    """
    try:
        with open(_nas_state_path(), "r", encoding="utf-8") as f:
            val = f.read().strip()
        if val:
            return val
    except OSError:
        pass
    return os.environ.get("GJESUS3_ROOT") or GUI_DEFAULT_NAS_ROOT


def save_nas_root(value):
    try:
        with open(_nas_state_path(), "w", encoding="utf-8") as f:
            f.write((value or "").strip())
    except OSError:
        pass


def _recipes_dir_state_path():
    return os.path.join(_state_dir(), "recipes_dir.txt")


def load_saved_recipes_dir():
    """The operator's persisted recipes folder, or "" (use the NAS default)."""
    try:
        with open(_recipes_dir_state_path(), "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def save_recipes_dir(value):
    v = (value or "").strip()
    if v:
        v = os.path.normpath(v)   # consistent separators (J:\… not J:/…)
    try:
        with open(_recipes_dir_state_path(), "w", encoding="utf-8") as f:
            f.write(v)
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


@app.route("/api/recipes_dir", methods=["GET", "POST"])
def api_recipes_dir():
    """View / set the recipes folder. POST with empty value resets to the NAS
    default. The effective folder is where recipes are saved + primarily listed.
    """
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        save_recipes_dir((data.get("recipes_dir") or "").strip())
    rdir = recipes_dir()
    return jsonify({
        "recipes_dir": rdir,
        "default": default_recipes_dir(),
        "is_default": not load_saved_recipes_dir(),
        "exists": os.path.isdir(rdir),
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
    """Persist a recipe to recipes_dir() as a human-readable YAML file (so it
    doubles as documentation of how a batch was loaded). Basename-only target.
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

    # Derive a safe filename from the name. Reject names with no usable
    # filename characters — they would all collapse to a single fallback and
    # silently clobber one another.
    safe = "".join(
        c if (c.isalnum() or c in "-_") else "_" for c in name.lower()
    ).strip("_")
    if not safe:
        return jsonify({"error": "Give the recipe a name with letters or numbers."}), 400
    fname = f"{safe}.yaml"
    rdir = recipes_dir()
    try:
        os.makedirs(rdir, exist_ok=True)
    except OSError as e:
        return jsonify({"error": f"Cannot create recipes folder ({rdir}): {e}"}), 500

    target = os.path.join(rdir, os.path.basename(fname))
    # Guard against silently overwriting an existing recipe: distinct names can
    # sanitise to the same filename (e.g. "Study A" and "Study/A" both ->
    # study_a.yaml), and a recipe often encodes an instrument's locked
    # convention. Require an explicit overwrite to replace one.
    if os.path.exists(target) and not bool(data.get("overwrite")):
        return jsonify({
            "error": (
                f"A recipe already exists as {fname!r}. Saving would overwrite "
                f"it — choose a different name, or resend with overwrite=true "
                f"to replace it."
            ),
            "exists": True,
            "file": fname,
        }), 409
    payload = {
        "schema": "gjesus3.operator.recipe/v1",
        "name": name,
        "instrument": instrument,
        "description": description,
        "overrides": overrides,
    }
    try:
        import yaml
        with open(target, "w", encoding="utf-8") as f:
            f.write(f"# gjesus3 operator recipe — {name}\n")
            f.write(f"# instrument: {instrument}\n")
            if description:
                f.write(f"# {description}\n")
            f.write("#\n# How a batch of this convention is read into the registry."
                    " Saved by the microscopy GUI; edit by hand if you know YAML.\n")
            yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True,
                           default_flow_style=False)
    except OSError as e:
        return jsonify({"error": f"Cannot write recipe: {e}"}), 500

    return jsonify({"file": fname, "path": target})


# NAS top-level dir names that must NEVER be deleted as "staging" (defence for
# the auto-cleanup below — a batch dir is always a SUBfolder of one of these).
_PROTECTED_DIR_NAMES = {
    "raw", "projects", "registries", "recipes", "publications",
    "curated_datasets", "staging", "tmp",
}


def _safe_to_delete_staging(path):
    """True only for a real, non-top-level batch dir — safe to rmtree.

    Guards the MRI post-ingest staging cleanup: refuses a drive root, a NAS
    top-level dir (raw/projects/staging/…), or anything that isn't an existing
    directory. A pulled batch is always `<staging>/<batch>/`, so this passes it
    while rejecting every dangerous path.
    """
    if not path:
        return False
    p = os.path.normpath(os.path.abspath(path))
    if not os.path.isdir(p):
        return False
    if os.path.dirname(p) == p:                       # a drive / filesystem root
        return False
    if os.path.basename(p).lower() in _PROTECTED_DIR_NAMES:
        return False
    return True


def _ingest_sse_response(cfg, nas_root, dry_run, stamp, cleanup_dir=None):
    """Run runner.run in a worker thread and stream its log as SSE.

    Shared by the microscopy (/api/ingest) and MRI (/api/mri/ingest) commit
    paths -- identical streaming behaviour; only the config assembly upstream
    differs. Each (msg, level) the pipeline logs becomes a `data: {...}` event;
    the final `done` event carries the per-acq results + the dry_run flag.

    `cleanup_dir` (MRI remote-pull only): a local staging batch dir to delete
    after a SUCCESSFUL, non-dry-run ingest (every acq ok). The operator never
    manages staging, so a clean real ingest removes the pulled copy. A partial
    or failed ingest keeps it for a retry. Microscopy passes None (no cleanup).
    """
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
                total = len(results)
                # Auto-remove the pulled staging only on a fully-successful real
                # ingest. Best-effort: a cleanup failure must not fail the run.
                if (cleanup_dir and not dry_run and total > 0 and ok == total
                        and _safe_to_delete_staging(cleanup_dir)):
                    try:
                        import shutil
                        shutil.rmtree(cleanup_dir)
                        cb(f"Removed local staging copy: {cleanup_dir}")
                    except OSError as e:
                        cb(f"Could not remove staging {cleanup_dir}: {e}", "WARN")
                q.put(("done", "INFO", json.dumps({
                    "results": [
                        {"acq_id": aid, "ok": bool(good)}
                        for aid, good in results
                    ],
                    "ok": ok,
                    "total": total,
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
    return _ingest_sse_response(cfg, nas_root, dry_run, stamp)


# ====================================================================== MRI
# A separate, deliberately-simple page over the SHARED core (see the MRI_*
# constants above). Reuses _build_cfg / preview / runner / _ingest_sse_response;
# adds only (a) the two operator-editable fields (project + link name), (b) the
# link-collision check, and (c) the Dicomifier-availability hint. The SFTP
# remote-pull source is layered on after the local-source path is proven.

def _dicomifier_status():
    """(available, version) for at-ingest DICOM regen on THIS machine.

    Best-effort: importing the regen module needs pydicom and the `dicomifier`
    binary on PATH (the dicomifier-pilot conda env; on Windows it lives in WSL).
    Any failure -> (False, None). Mirrors what mri_ingest.py prints in the CLI.
    """
    try:
        from ingest import paravision_regen
        return paravision_regen.check_dicomifier_available()
    except Exception:  # noqa: BLE001 — a probe must never break preview
        return False, None


def _mri_overrides(data):
    """Assemble the config_builder override dict from the MRI page inputs.

    Keys honoured (all optional for preview; operator is enforced at ingest):
      operator      -> registry.researcher + sidecar operator (MRI: same person)
      model         -> registry.instrument_model ("7T" / "11.7T")
      project_mode  -> "auto" (template default, per animal-protocol code) |
                       "fixed" (one specific project) | "none" (no project/links)
      project_hint  -> the fixed hint, when project_mode == "fixed"
      link_filename -> the project-link-name template, when project_mode != "none"
      regenerate    -> bool; False sets ingest.auto_regenerate_dicom: false
    """
    ov = {}
    operator = (data.get("operator") or "").strip()
    if operator:
        ov["registry.researcher"] = operator
        ov["operator"] = operator
    model = (data.get("model") or "").strip()
    if model in _MRI_MODEL_MAP:
        ov["registry.instrument_model"] = _MRI_MODEL_MAP[model]
    mode = (data.get("project_mode") or "auto").strip().lower()
    if mode == "none":
        ov["registry.project_hint"] = ""              # -> no project, no links
    elif mode == "fixed":
        ov["registry.project_hint"] = (data.get("project_hint") or "").strip()
    # mode == "auto": leave the template's ae-biomegune-${discovered.project_code}
    if mode != "none":
        link = (data.get("link_filename") or "").strip()
        if link:
            ov["link_filename"] = link
    if data.get("regenerate") is False:
        ov["ingest.auto_regenerate_dicom"] = False
    return ov


@app.route("/mri")
def mri_index():
    """The simple MRI ingest page (separate from the microscopy index)."""
    tpl = templates.load_template(MRI_KEY)
    return render_template(
        "mri.html",
        nas_root=load_saved_nas_root(),
        link_default=tpl.get("link_filename") or "",
        project_default=(tpl.get("registry") or {}).get("project_hint") or "",
        models=sorted(_MRI_MODEL_MAP),
        palette_keys=MRI_LINK_PALETTE_KEYS,
        palette_extras=MRI_LINK_PALETTE_EXTRAS,
    )


@app.route("/api/mri/preview", methods=["POST"])
def api_mri_preview():
    """Read-only MRI preview + link-collision check (local source folder)."""
    data = request.get_json(silent=True) or {}
    staging_path = (data.get("staging_path") or "").strip()
    nas_root = (data.get("nas_root") or "").strip() or load_saved_nas_root()

    if not staging_path:
        return jsonify({"error": "Pick a source folder (a ParaVision exam, a "
                                 "study folder, or a batch root)."}), 400
    try:
        env.validate_nas_root(nas_root)
    except env.NasRootError as e:
        return jsonify({"error": str(e)}), 400

    try:
        cfg, tpl_path, staging_dir, pattern = _build_cfg(
            MRI_KEY, _mri_overrides(data), staging_path
        )
    except scope.ScopeError as e:
        return jsonify({"error": str(e)}), 400
    except config_builder.OverrideError as e:
        return jsonify({"error": f"Bad setting: {e}"}), 400
    except (KeyError, FileNotFoundError) as e:
        return jsonify({"error": str(e)}), 400

    try:
        result = preview.preview_batch(cfg, nas_root)
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": f"Preview failed: {e}"}), 500

    cases = [_case_to_dict(c) for c in result.cases]
    available, version = _dicomifier_status()
    return jsonify({
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
        "cases": cases,
        "collisions": collisions.find_link_collisions(cases),
        "existing_targets": collisions.find_existing_link_targets(cases, nas_root),
        "dicomifier_available": available,
        "dicomifier_version": version,
    })


@app.route("/api/mri/ingest", methods=["POST"])
def api_mri_ingest():
    """Commit path for the MRI page: SSE-streamed ingest (operator REQUIRED).

    `cleanup_staging` (set by the remote-pull flow): delete the local staging
    batch after a fully-successful real ingest, so the operator never manages
    staging by hand.
    """
    data = request.get_json(silent=True) or {}
    staging_path = (data.get("staging_path") or "").strip()
    nas_root = (data.get("nas_root") or "").strip() or load_saved_nas_root()
    dry_run = bool(data.get("dry_run"))
    operator = (data.get("operator") or "").strip()
    cleanup_staging = bool(data.get("cleanup_staging"))

    if not staging_path:
        return jsonify({"error": "Pull at least one study from the scanner "
                                 "first."}), 400
    if not operator:
        return jsonify({"error": "Operator is required for MRI (the person who "
                                 "ran the scanner)."}), 400
    try:
        env.validate_nas_root(nas_root)
    except env.NasRootError as e:
        return jsonify({"error": str(e)}), 400

    try:
        cfg, tpl_path, _sd, _pat = _build_cfg(
            MRI_KEY, _mri_overrides(data), staging_path
        )
    except scope.ScopeError as e:
        return jsonify({"error": str(e)}), 400
    except config_builder.OverrideError as e:
        return jsonify({"error": f"Bad setting: {e}"}), 400
    except (KeyError, FileNotFoundError) as e:
        return jsonify({"error": str(e)}), 400

    stamp = runner.default_recipe_path(tpl_path)
    cleanup_dir = staging_path if cleanup_staging else None
    return _ingest_sse_response(cfg, nas_root, dry_run, stamp,
                                cleanup_dir=cleanup_dir)


# ============================================================ MRI SFTP remote-pull
# Layer 2: pull ParaVision study folders off the acquisition console, then feed
# the local copy to the SAME MRI preview/ingest path above. Read-only on the
# remote. Two endpoints: /api/sftp_listdir (browse MFB exams) + /api/sftp_pull
# (SSE-streamed mirror, like the ingest stream). Creds via env.ftp_creds().

def _load_ftp_mirror():
    """Load tools/ftp_mirror.py (SFTP mirror engine) under a private alias.

    Lives at tools/ftp_mirror.py (one level above the operator package), so it
    is loaded by path, not import. _MEIPASS-aware for the frozen bundle.
    """
    path = os.path.join(_TOOLS_DIR, "ftp_mirror.py")
    spec = importlib.util.spec_from_file_location("gj_ftp_mirror", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sftp_connect():
    """Open an SFTP client to the MRI host using env.ftp_creds().

    Returns (transport, sftp). Raises RuntimeError with a plain-language message
    when creds are missing or paramiko is not installed — the caller surfaces it
    as a 400 so the operator sees what to fix.
    """
    if not env.ftp_creds_present():
        raise RuntimeError(
            "No SFTP credentials found. Set the GJESUS3_FTP_* environment "
            "variables, or create ~/.ssh/gjesus3_mri.cred (see "
            "equipment/historical_data_archives.md §MRI)."
        )
    try:
        import paramiko
    except ImportError:
        raise RuntimeError("paramiko is not installed. Run: pip install paramiko")
    c = env.ftp_creds()
    transport = paramiko.Transport((c["host"], c["port"]))
    transport.connect(username=c["user"], password=c["password"])
    sftp = paramiko.SFTPClient.from_transport(transport)
    return transport, sftp


def _under_known_root(remote):
    """True if `remote` sits directly under one of the documented SFTP roots.

    Defence-in-depth: the operator only ever picks from the listed exams, but a
    crafted request must not coax a pull of an arbitrary remote path. We only
    ever READ/COPY, never write, so the blast radius is small — but bound it.
    """
    remote = (remote or "").rstrip("/")
    for root in MRI_SFTP_ROOTS:
        base = root["path"].rstrip("/")
        if remote.startswith(base + "/") and "/" not in remote[len(base) + 1:]:
            return True
    return False


def _default_mri_staging_root(nas_root=None):
    """Default landing dir for pulled studies: `<nas_root>/staging`.

    The MFB NAS has a top-level `staging/` dir on every root — pulling there
    keeps the follow-on ingest NAS-local (no second SMB hop) and means the
    operator never has to think about where the temporary copy goes. `nas_root`
    overrides the saved one (so staging follows the destination chosen for this
    pull). Falls back to the documented local dir when the NAS root isn't a real
    dir yet.
    """
    nas = nas_root or load_saved_nas_root()
    if nas and os.path.isdir(nas):
        return os.path.normpath(os.path.join(nas, "staging"))
    return MRI_PULL_STAGING_ROOT


@app.route("/api/sftp_status")
def api_sftp_status():
    """Whether remote pull is usable on this machine: creds present + host."""
    present = env.ftp_creds_present()
    host = env.ftp_creds().get("host") if present else None
    try:
        import paramiko  # noqa: F401
        has_paramiko = True
    except ImportError:
        has_paramiko = False
    return jsonify({
        "creds_present": present,
        "host": host,
        "paramiko": has_paramiko,
        "available": present and has_paramiko,
        "roots": MRI_SFTP_ROOTS,
        "staging_root": _default_mri_staging_root(),
    })


@app.route("/api/sftp_listdir", methods=["POST"])
def api_sftp_listdir():
    """List MFB (jrc) ParaVision study folders on the MRI host, newest first.

    Read-only: a single non-recursive listdir of each documented root. Folder
    names start with YYYYMMDD_HHMMSS, so a reverse name sort is a reliable
    chronological order (st_mtime is also returned as a backstop).
    """
    import stat as _stat
    data = request.get_json(silent=True) or {}
    show_all = bool(data.get("all"))   # default False -> jrc-only
    try:
        transport, sftp = _sftp_connect()
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    try:
        exams = []
        root_errors = []
        for root in MRI_SFTP_ROOTS:
            try:
                entries = sftp.listdir_attr(root["path"])
            except IOError as e:
                root_errors.append({"root": root["path"], "error": str(e)})
                continue
            for ent in entries:
                if not _stat.S_ISDIR(ent.st_mode):
                    continue
                name = ent.filename
                if not show_all and MRI_SFTP_FILTER not in name.lower():
                    continue
                exams.append({
                    "name": name,
                    "root": root["path"],
                    "version": root["label"],
                    "remote": root["path"].rstrip("/") + "/" + name,
                    "mtime": int(ent.st_mtime or 0),
                })
        exams.sort(key=lambda d: d["name"], reverse=True)   # newest first
        return jsonify({
            "host": env.ftp_creds().get("host"),
            "filter": None if show_all else MRI_SFTP_FILTER,
            "count": len(exams),
            "exams": exams,
            "root_errors": root_errors,
        })
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": f"SFTP listing failed: {e}"}), 500
    finally:
        transport.close()


@app.route("/api/sftp_pull", methods=["POST"])
def api_sftp_pull():
    """Mirror the selected remote study folders into a local batch dir, SSE-streamed.

    Each checked remote `/opt/.../nmr/<study>` is mirrored to
    `<staging_root>/<batch>/<study>/`, so the batch dir holds study folders and
    the existing MRI `*/*` scope matches. The final `done` event carries the
    local `staging_dir` — the page drops it into the source field and the
    operator runs Preview as usual. Read-only on the remote (download only).
    """
    from datetime import datetime
    data = request.get_json(silent=True) or {}
    remotes = [r for r in (data.get("remotes") or []) if isinstance(r, str)]
    nas_root = (data.get("nas_root") or "").strip() or load_saved_nas_root()
    staging_root = (data.get("staging_root") or "").strip() or _default_mri_staging_root(nas_root)
    batch = (data.get("batch") or "").strip()
    force = bool(data.get("force"))

    # Validate up front so guard failures are a clean 400 (not mid-stream).
    if not remotes:
        return jsonify({"error": "Select at least one study to pull."}), 400
    # Check the DESTINATION NAS before pulling — pulling is the expensive step,
    # and a pull is pointless if the scans can't then be ingested. This stops the
    # "pulled 75 MB, then preview says the NAS is invalid" surprise.
    try:
        env.validate_nas_root(nas_root)
    except env.NasRootError as e:
        return jsonify({"error": "Set a valid destination NAS first (top of the "
                                 "page), then pull.\n\n" + str(e)}), 400
    if len(remotes) > MRI_PULL_MAX_STUDIES:
        return jsonify({"error": f"Too many studies selected "
                                 f"({len(remotes)} > {MRI_PULL_MAX_STUDIES})."}), 400
    bad = [r for r in remotes if not _under_known_root(r)]
    if bad:
        return jsonify({"error": f"Refusing to pull paths outside the known "
                                 f"ParaVision roots: {bad[:3]}"}), 400
    try:
        ftp_mirror = _load_ftp_mirror()
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": f"Cannot load the SFTP engine: {e}"}), 500

    # batch subfolder keeps each pull isolated; default to a timestamp.
    if not batch:
        batch = "sftp_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_batch = "".join(c if (c.isalnum() or c in "-_") else "_" for c in batch)
    staging_dir = os.path.normpath(os.path.join(staging_root, safe_batch))

    def generate():
        import queue
        q = queue.Queue()
        SENTINEL = object()

        def cb(msg, level="INFO"):
            q.put(("log", level, str(msg)))

        def worker():
            transport = None
            try:
                transport, sftp = _sftp_connect()
                cb(f"Connected. Pulling {len(remotes)} study folder(s) -> {staging_dir}")
                tot_x = tot_s = tot_b = 0
                for idx, remote in enumerate(remotes, 1):
                    study = remote.rstrip("/").rsplit("/", 1)[-1]
                    local = os.path.join(staging_dir, study)
                    cb(f"[{idx}/{len(remotes)}] {study}")
                    nx, ns, nb = ftp_mirror.mirror(
                        sftp, remote, local, force=force, log_callback=cb,
                    )
                    tot_x += nx
                    tot_s += ns
                    tot_b += nb
                cb(f"Done. transferred {tot_x} files "
                   f"({tot_b / 1_000_000:.1f} MB); skipped {tot_s} already-present")
                q.put(("done", "INFO", json.dumps({
                    "staging_dir": staging_dir,
                    "studies": len(remotes),
                    "transferred": tot_x,
                    "skipped": tot_s,
                    "bytes": tot_b,
                })))
            except Exception as e:  # noqa: BLE001 — report to the stream
                q.put(("error", "ERROR", str(e)))
            finally:
                if transport is not None:
                    transport.close()
                q.put(SENTINEL)

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        while True:
            item = q.get()
            if item is SENTINEL:
                break
            kind, level, msg = item
            yield f"data: {json.dumps({'kind': kind, 'level': level, 'msg': msg})}\n\n"

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
    parser.add_argument(
        "--mri", action="store_true",
        help="Open the browser straight to the MRI ingest page (/mri) instead "
             "of the microscopy landing page. Same server either way.",
    )
    args = parser.parse_args(argv)

    url = f"http://{args.host}:{args.port}/" + ("mri" if args.mri else "")
    if not args.no_browser:
        # Open the browser shortly after the server starts.
        threading.Timer(1.0, _open_browser, args=(url,)).start()
    # use_reloader=False: the reloader re-execs the process, which re-runs the
    # core loader and double-opens the browser; not wanted for a packaged app.
    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)


if __name__ == "__main__":
    main()
