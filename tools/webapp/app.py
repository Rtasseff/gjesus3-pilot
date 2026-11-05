r"""gjesus3 web app: the ingest GUI and the Project Manager from one URL.

Box A port, Stage 2.1 (tasks/box_a_production_migration_plan.md, "Stage 2").
One WSGI process serves:

    /              a landing page with a link to each tool
    /ingest/       microscopy ingest  (tools/operator/gui/app.py)
    /ingest/mri    MRI ingest         (the same app's second page)
    /projects/     the Project Manager (tools/manager/gui/app.py)

The two existing Flask apps are MOUNTED as they are (werkzeug's
DispatcherMiddleware), not rewritten as blueprints. The same app.py files still
run on their own and still build the two exes (gjesus3_ingest.exe,
gjesus3_manager.exe), the fallback for a month after cut-over. Their pages work
under any prefix: the templates build links with url_for and write the mount
point into window.GJ3_BASE, and every request the JS makes goes through
apiUrl(), which prefixes it.

ONE NAS root for the whole server, from tools/webapp/settings.py: --nas-root,
else $GJESUS3_WEBAPP_NAS_ROOT, else a JSON config file. Without one the app
refuses to start. It never falls back to $GJESUS3_ROOT or a PC's saved choice,
so a test instance cannot open production by default; the production root
(registries\.production) also needs --production. Pinned, the root is the only
one either GUI uses, whatever a page posts.

Not in this step (2.2 to 2.4): sign-in and accounts, the action log, a job
queue, the NI page, IIS. Until sign-in exists the server listens on the
loopback address only.

Run, from the repo root:
    python tools/operator/make_test_nas.py --dest C:\Users\<you>\temp\testnas
    python tools/webapp/app.py --nas-root C:\Users\<you>\temp\testnas
    # serves http://127.0.0.1:5002/ (5000 and 5001 are the two exes)

NEVER `import operator` here (tools/operator/IMPORT_CONTRACT.md). The ingest GUI
is loaded by path, and it loads the operator core through its own loader.
"""

import argparse
import importlib.util
import os
import sys
import threading
import webbrowser

_HERE = os.path.dirname(os.path.abspath(__file__))       # tools/webapp/
_TOOLS_DIR = os.path.dirname(_HERE)                       # tools/
if _TOOLS_DIR not in sys.path:
    # APPEND, never insert: the stdlib `operator` must keep winning over
    # tools/operator/ (IMPORT_CONTRACT.md).
    sys.path.append(_TOOLS_DIR)

from webapp import settings as server_settings  # noqa: E402

# Flask last, so a missing-flask error does not mask an import problem above.
from flask import Flask, render_template, request  # noqa: E402
from werkzeug.middleware.dispatcher import DispatcherMiddleware  # noqa: E402

DEFAULT_PORT = 5002
INGEST_MOUNT = "/ingest"
PROJECTS_MOUNT = "/projects"
# No sign-in yet (step 2.2): an address other people can reach would hand them
# writes to the NAS and a listing of this machine's disks.
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")

# Both GUIs are files called app.py, so each is loaded by path under its own
# module name rather than imported.
_GUI_FILES = {
    "gj3_webapp_ingest_gui": os.path.join(_TOOLS_DIR, "operator", "gui", "app.py"),
    "gj3_webapp_manager_gui": os.path.join(_TOOLS_DIR, "manager", "gui", "app.py"),
}


def _load_gui(name):
    """Load one GUI module by path, once."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _GUI_FILES[name])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod     # before exec: Flask finds the app's root path through it
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return mod


def load_guis():
    """(the ingest GUI module, the Project Manager module)."""
    return _load_gui("gj3_webapp_ingest_gui"), _load_gui("gj3_webapp_manager_gui")


def _landing_app(cfg):
    landing = Flask(__name__, template_folder=os.path.join(_HERE, "templates"),
                    static_folder=None)

    @landing.route("/")
    def index():
        # script_root is "" unless the whole server itself sits under a prefix.
        base = request.script_root
        return render_template("index.html", nas_root=cfg.nas_root,
                               production=cfg.production,
                               ingest=base + INGEST_MOUNT,
                               projects=base + PROJECTS_MOUNT)

    # A mount point typed without its slash (/ingest) never reaches this app:
    # the dispatcher hands it to the mounted app, which redirects to /ingest/.
    return landing


def create_app(cfg):
    """The one WSGI application: the landing page, and both GUIs under their
    mounts with the server's NAS root pinned in each."""
    ingest_gui, manager_gui = load_guis()
    for gui in (ingest_gui, manager_gui):
        gui.use_server_settings(cfg.nas_root, home_url="/")
    return DispatcherMiddleware(_landing_app(cfg), {
        INGEST_MOUNT: ingest_gui.app,
        PROJECTS_MOUNT: manager_gui.app,
    })


def main(argv=None):
    p = argparse.ArgumentParser(
        description="gjesus3 web app: microscopy and MRI ingest and the Project "
                    "Manager from one URL, against ONE NAS root.")
    p.add_argument("--nas-root",
                   help=f"The RDM System root this server works on (else "
                        f"${server_settings.ENV_NAS_ROOT}, else the config file). "
                        f"$GJESUS3_ROOT is never used.")
    p.add_argument("--config",
                   help=f"A JSON settings file, e.g. {{\"nas_root\": \"...\"}} "
                        f"(else ${server_settings.ENV_CONFIG}).")
    p.add_argument("--production", action="store_true",
                   help="Required when the root is the production root "
                        "(registries/.production). Never for testing.")
    p.add_argument("--host", default="127.0.0.1",
                   help="Loopback only until sign-in exists (127.0.0.1, "
                        "localhost or ::1).")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--no-browser", action="store_true",
                   help="Do not open the default browser.")
    args = p.parse_args(argv)

    try:
        cfg = server_settings.load_settings(
            nas_root=args.nas_root, config_path=args.config,
            production=args.production)
    except server_settings.SettingsError as e:
        print(f"gjesus3 web app: not starting: {e}", file=sys.stderr)
        return 2
    if args.host not in LOOPBACK_HOSTS:
        print(f"gjesus3 web app: not starting: --host {args.host!r} would let "
              f"other machines in, and there is no sign-in yet. Use "
              f"{' / '.join(LOOPBACK_HOSTS)}.", file=sys.stderr)
        return 2

    application = create_app(cfg)
    url = f"http://{args.host}:{args.port}/"
    print(f"gjesus3 web app on {url}")
    print(f"  NAS root: {cfg.nas_root}  (from {cfg.source})"
          + ("  ** PRODUCTION **" if cfg.production else ""))
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    from werkzeug.serving import run_simple
    # threaded: an SSE ingest stream must not block the other pages. No
    # reloader: it would re-exec the process and load the GUIs twice.
    run_simple(args.host, args.port, application, threaded=True,
               use_reloader=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
