# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — gjesus3 operator ingest GUI (single .exe, BOTH pages).

ONE Flask app, two pages: `/` = microscopy (recipes/builder) and `/mri` = the
simple MRI ingest page (SFTP pull from the scanner -> preview -> ingest). The
same exe serves both; ship TWO desktop shortcuts:
    Microscopy Ingest  ->  gjesus3_ingest.exe
    MRI Ingest         ->  gjesus3_ingest.exe --mri      (opens /mri directly)

Build (from the repo root, on a Windows machine):

    pip install flask paramiko pyinstaller czifile tifffile numpy pyyaml
    pyinstaller tools/operator/gui/gjesus3_ingest.spec

Produces dist/gjesus3_ingest/gjesus3_ingest.exe (one-folder by default; flip
`onefile` below for a single file). Double-clicking it starts the local Flask
server and opens the browser.

MRI-specific bundling (added 2026-06-24): paramiko (imported LAZILY inside the
SFTP endpoints, so PyInstaller's static analysis misses it -> hidden import) and
tools/ftp_mirror.py (loaded by path at runtime via app.py::_load_ftp_mirror ->
must be a bundled data file).

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
    # MRI remote-pull engine — app.py::_load_ftp_mirror loads it by path from
    # <_MEIPASS>/tools/ftp_mirror.py, so it must be a bundled data file.
    (os.path.join(TOOLS, "ftp_mirror.py"), "tools"),
]

hiddenimports = [
    "flask", "jinja2", "werkzeug",
    "yaml",
    # .czi embedded-metadata extraction (verify the frozen exe reads a .czi).
    "czifile", "tifffile", "numpy",
    # pipeline modules that may be reached only dynamically.
    "ingest", "ingest_raw",
    # MRI SFTP pull: paramiko is imported LAZILY inside app.py's SFTP endpoints,
    # so static analysis won't see it. Pull it (and its native deps) in by name.
    "paramiko", "cryptography", "bcrypt", "nacl", "cffi",
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

# ONEFILE (default): one self-extracting gjesus3_ingest.exe — chosen for NAS
# distribution (a single file to drop on \\gjesus3\...\tools\, run in place).
# Trade-off: ~3-5s self-extract on each launch. Set False for the faster-
# starting one-folder build (operators copy the whole folder locally instead).
ONEFILE = True

if ONEFILE:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="gjesus3_ingest",
        console=True,       # keep the console so the operator sees the URL/log
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        runtime_tmpdir=None,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="gjesus3_ingest",
        console=True,
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
        name="gjesus3_ingest",
    )
