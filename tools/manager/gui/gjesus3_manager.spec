# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — gjesus3 Project Manager GUI (single .exe).

A SEPARATE exe from `gjesus3_ingest.exe`, on purpose: a different audience
(researchers vs. operators) and, decisively, a different release cadence —
folding this in would make every project-manager tweak force a redeploy of the
production ingest exe, the artifact that is replaced under a backup-and-rollback
procedure. Both exes are expected to retire around Oct 2026 when a dedicated RDM
server turns the tools into one web app; until then they share code and assets
rather than being merged.

Build (from the repo root, on a Windows machine). The repo lives under OneDrive,
which LOCKS build artifacts mid-build (PermissionError on PYZ-00.pyz), so build
and dist MUST go to a non-synced path:

    pip install flask pyyaml pyinstaller
    pyinstaller --workpath D:/_build --distpath D:/_dist \
        tools/manager/gui/gjesus3_manager.spec

Produces <distpath>/gjesus3_manager.exe. Double-clicking it starts the local
Flask server on port 5001 (NOT 5000 — a researcher may have the ingest GUI open
at the same time) and opens the browser.

DATA BUNDLING — coordinate with the runtime's path resolution:
  * app.py derives <_MEIPASS>/tools/... when frozen, so the source layout is
    preserved inside the bundle. Keep it that way; any divergence between the
    frozen and source shapes is the class of bug the 2026-07-17 frozen-exe fix
    chased for two months.
  * `ingest/resources.py::resource_path` is _MEIPASS-aware and looks under
    <_MEIPASS>/tools/<parts>. Every bundled resource reached through it must
    live at exactly that subpath. `create_project.py` reads
    tools/templates/project.yaml through it — a MISSING bundle does not crash,
    it silently falls through to an inline non-templated fallback, which is
    precisely the failure mode that made the ingest exe write degraded
    _project.yaml files unnoticed.
  * The Project Manager serves the ingest GUI's static assets from
    <_MEIPASS>/tools/operator/gui/static (app.py::_SHARED_STATIC) — ONE
    stylesheet and ONE folder-browser component for both tools, so both specs
    bundle that directory.
"""

import os

SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))  # noqa: F821 (SPEC injected)
REPO_ROOT = os.path.abspath(os.path.join(SPEC_DIR, "..", "..", ".."))
TOOLS = os.path.join(REPO_ROOT, "tools")

datas = [
    # This app's own Flask templates + static, next to app.py in the bundle.
    (os.path.join(TOOLS, "manager", "gui", "templates"),
     os.path.join("tools", "manager", "gui", "templates")),
    (os.path.join(TOOLS, "manager", "gui", "static"),
     os.path.join("tools", "manager", "gui", "static")),
    # The SHARED assets, served at /shared/* — style.css, folder_browser.js,
    # completion_modal.js. Same files the ingest exe ships; not a fork.
    (os.path.join(TOOLS, "operator", "gui", "static"),
     os.path.join("tools", "operator", "gui", "static")),
    # _project.yaml template — read via ingest/resources.py by
    # create_project.py. Missing => a silent non-templated fallback.
    (os.path.join(TOOLS, "templates", "project.yaml"),
     os.path.join("tools", "templates")),
    # The rest of tools/templates + tools/reference are cheap and are what
    # ingest/resources.py resolves against; bundling the whole (tiny) dirs keeps
    # the set closed rather than relying on this app never reaching one of them.
    (os.path.join(TOOLS, "templates"), os.path.join("tools", "templates")),
    (os.path.join(TOOLS, "reference"), os.path.join("tools", "reference")),
    # The manager core + the shared ingest layer, as source (imported through
    # the tools/ dir appended to sys.path at startup, so static analysis can
    # miss them).
    (os.path.join(TOOLS, "manager"), os.path.join("tools", "manager")),
    (os.path.join(TOOLS, "ingest"), os.path.join("tools", "ingest")),
    # Top-level modules loaded by name from tools/.
    (os.path.join(TOOLS, "create_project.py"), "tools"),
    (os.path.join(TOOLS, "filebrowse.py"), "tools"),
    (os.path.join(TOOLS, "find_acq.py"), "tools"),
    # Imported inside the import worker to refresh the touched project's
    # index.html; without it that refresh silently no-ops in the frozen build
    # (the import is caught), exactly as it did for the ingest GUI in 2026-07.
    (os.path.join(TOOLS, "generate_index.py"), "tools"),
]

hiddenimports = [
    "flask", "jinja2", "werkzeug",
    "yaml",                       # _project.yaml read/verify
    "ingest",
    "manager", "manager.projects", "manager.raw_import",
    "manager.local_import", "manager.acq_search",
    "create_project", "filebrowse", "find_acq", "generate_index",
]

block_cipher = None

a = Analysis(
    [os.path.join(TOOLS, "manager", "gui", "app.py")],
    pathex=[TOOLS],            # so `from ingest import ...` / `import manager` resolve
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # This app never ingests, never talks SFTP and never reads a .czi;
        # excluding the heavy scientific stack keeps the exe a fraction of the
        # ingest exe's ~95 MB.
        "paramiko", "cryptography", "bcrypt", "nacl",
        "czifile", "tifffile", "numpy", "pydicom",
    ],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ONEFILE, matching the ingest exe: one self-extracting file to drop on
# \\gjesus3\...\tools\ and run in place.
ONEFILE = True

if ONEFILE:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="gjesus3_manager",
        console=True,       # keep the console so the URL / log is visible
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
        name="gjesus3_manager",
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
        name="gjesus3_manager",
    )
