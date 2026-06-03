# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Microscopy operator ingest GUI (single .exe).

Build (from the repo root, on the Windows microscopy machine):

    pip install flask pyinstaller czifile tifffile numpy pyyaml
    pyinstaller tools/operator/gui/microscopy_ingest.spec

Produces dist/microscopy_ingest/microscopy_ingest.exe (one-folder by default;
flip `onefile` below for a single file). Double-clicking it starts the local
Flask server and opens the browser.

DATA BUNDLING — coordinate with the core's path resolution:
  * templates.template_path() looks under <_MEIPASS>/tools/templates/instruments
    first (see tools/operator/templates.py::_candidate_dirs). We map the
    per-instrument templates to exactly that subpath.
  * gui/app.py::recipes_dir() looks under <_MEIPASS>/tools/operator/recipes
    first. We map the seed recipes there.
  * Flask needs its templates/ + static/ next to app.py inside the bundle;
    we map them under tools/operator/gui/ so url_for/render_template resolve.

WHY the source layout is preserved inside the bundle: the core appends the
bundle's tools/ dir to sys.path implicitly via _MEIPASS-aware lookups; keeping
the tools/.../ shape avoids any divergence between frozen and source runs.
"""

import os

# PyInstaller runs this spec with __file__ pointing at the spec; derive the
# repo root from it (spec lives at tools/operator/gui/).
SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))  # noqa: F821 (SPEC injected)
REPO_ROOT = os.path.abspath(os.path.join(SPEC_DIR, "..", "..", ".."))

TOOLS = os.path.join(REPO_ROOT, "tools")

datas = [
    # Per-instrument templates -> <_MEIPASS>/tools/templates/instruments
    (os.path.join(TOOLS, "templates", "instruments"),
     os.path.join("tools", "templates", "instruments")),
    # Universal starter template (fallback) — harmless to include.
    (os.path.join(TOOLS, "templates", "ingest_template.yaml"),
     os.path.join("tools", "templates")),
    # Seed recipes -> <_MEIPASS>/tools/operator/recipes
    (os.path.join(TOOLS, "operator", "recipes"),
     os.path.join("tools", "operator", "recipes")),
    # Flask templates + static next to app.py inside the bundle.
    (os.path.join(TOOLS, "operator", "gui", "templates"),
     os.path.join("tools", "operator", "gui", "templates")),
    (os.path.join(TOOLS, "operator", "gui", "static"),
     os.path.join("tools", "operator", "gui", "static")),
]

# The operator core + the reused pipeline are imported dynamically (via the
# _loader and the appended-tools/ sys.path). PyInstaller's static analysis may
# miss them, so collect them explicitly as source data AND as hidden imports.
datas += [
    (os.path.join(TOOLS, "operator"), os.path.join("tools", "operator")),
    (os.path.join(TOOLS, "ingest"), os.path.join("tools", "ingest")),
    (os.path.join(TOOLS, "ingest_raw.py"), "tools"),
]

hiddenimports = [
    "flask", "jinja2", "werkzeug",
    "yaml",
    # .czi embedded-metadata extraction (verify the frozen exe reads a .czi).
    "czifile", "tifffile", "numpy",
    # pipeline modules that may be reached only dynamically.
    "ingest", "ingest_raw",
]

block_cipher = None

a = Analysis(
    [os.path.join(TOOLS, "operator", "gui", "app.py")],
    pathex=[TOOLS],            # so `import ingest_raw` / `from ingest import ...` resolve
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="microscopy_ingest",
    console=True,           # keep the console so the operator sees the URL/log
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="microscopy_ingest",
)
