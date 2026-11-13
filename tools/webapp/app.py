r"""gjesus3 web app: the three tools in one place, behind one sign-in.

Box A port, Stage 2 (tasks/box_a_production_migration_plan.md). One WSGI
process serves:

    /                  Home: where to start, and your recent activity
    /ingest/           microscopy ingest  (tools/operator/gui/app.py)
    /ingest/mri        MRI ingest         (the same app's second page)
    /projects/         the Project Manager (tools/manager/gui/app.py)
    /account/...       sign in, sign out, change password, People (admins)

Around all of it, from the outside in:

    auth.Gate     no page or call without a signed-in person (local accounts,
                  accounts.py); refuses cross-site writes
    guard.Guard   tool calls may read only from the source folders; every write
                  goes to the action log with its outcome
    dispatcher    the web app's own pages, and both GUIs under their mounts

The two GUIs are MOUNTED as they are (2.1), not rewritten. The same app.py files
still run on their own and still build the two exes, the fallback until the
exes retire. Inside the web app they get the shared header (shell.py) and the
signed-in person's name in their people fields; on their own nothing changes.

The server runs under one Windows account (Ryan's, decision D1, 2026-11-06), so
every file is written with his rights; the sign-in decides who is RECORDED.

ONE NAS root for the whole server, from settings.py (--nas-root, else
$GJESUS3_WEBAPP_NAS_ROOT, else a JSON config file), never a fallback; the
production root also needs --production.

Run, from the repo root:
    python tools/operator/make_test_nas.py --dest C:\Users\<you>\temp\testnas
    python tools/webapp/accounts.py add <you> --name "Your Name" --admin
    python tools/webapp/app.py --nas-root C:\Users\<you>\temp\testnas
    # serves http://127.0.0.1:5002/ (5000 and 5001 are the two exes)

Other machines: --host 0.0.0.0 with --cert and --key (HTTPS), or --allow-http
for a test copy only (passwords then cross the network readable). The firewall
rule that lets them in is a security setting: Ryan's script, not this program.

NEVER `import operator` here (tools/operator/IMPORT_CONTRACT.md). The ingest GUI
is loaded by path, and it loads the operator core through its own loader.
"""

import argparse
import importlib.util
import os
import sys
import threading
import webbrowser
from urllib.parse import urlsplit

_HERE = os.path.dirname(os.path.abspath(__file__))       # tools/webapp/
_TOOLS_DIR = os.path.dirname(_HERE)                       # tools/
if _TOOLS_DIR not in sys.path:
    # APPEND, never insert: the stdlib `operator` must keep winning over
    # tools/operator/ (IMPORT_CONTRACT.md).
    sys.path.append(_TOOLS_DIR)

from webapp import settings as server_settings  # noqa: E402
from webapp import accounts as accounts_mod  # noqa: E402
from webapp import auth, guard, shell  # noqa: E402
from webapp.actionlog import ActionLog  # noqa: E402
import filebrowse  # noqa: E402

# Flask last, so a missing-flask error does not mask an import problem above.
from flask import Flask, redirect, render_template, request  # noqa: E402
from werkzeug.middleware.dispatcher import DispatcherMiddleware  # noqa: E402

DEFAULT_PORT = 5002
INGEST_MOUNT = "/ingest"
PROJECTS_MOUNT = "/projects"
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")

ACTION_LABELS = {
    "microscopy-ingest": "Microscopy ingest",
    "mri-ingest": "MRI ingest",
    "mri-pull": "MRI pull from the scanner",
    "recipe-save": "Saved a recipe",
    "project-create": "New project",
    "project-edit": "Edited a project",
    "project-add-acquisitions": "Added acquisitions to a project",
    "project-add-files": "Added files to a project",
}

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


def _safe_next(value, base):
    """Only a path on this server: never another site (an open redirect)."""
    value = value or ""
    parts = urlsplit(value)
    if parts.scheme or parts.netloc or not value.startswith("/") or value.startswith("//"):
        return base + "/"
    return value


def _portal_app(cfg, sessions, store, log):
    """The web app's own pages: Home and the account pages."""
    portal = Flask(__name__, template_folder=os.path.join(_HERE, "templates"),
                   static_folder=os.path.join(_HERE, "static"), static_url_path="/static")

    @portal.context_processor
    def _ctx():
        return {"shell": shell.context(cfg, request.environ, request.path),
                "base": request.environ.get("gj3.base", ""),
                "production": cfg.production}

    def secure():
        return request.scheme == "https"

    @portal.route("/")
    def home():
        me = request.environ["gj3.user"]
        everyone = log.recent(limit=12) if me["role"] == "admin" else []
        return render_template("home.html", mine=log.recent(me["username"], limit=8),
                               everyone=everyone, labels=ACTION_LABELS,
                               source_roots=cfg.source_roots)

    @portal.route(auth.LOGIN_PATH, methods=["GET", "POST"])
    def login():
        base = request.environ.get("gj3.base", "")
        nxt = _safe_next(request.values.get("next"), base)
        if request.method == "GET":
            if request.environ.get("gj3.user"):
                return redirect(nxt)
            return render_template("login.html", next=nxt, username="", error=None)
        username = (request.form.get("username") or "").strip().lower()
        addr = request.remote_addr or "?"
        wait = sessions.throttle.wait_seconds("u:" + username, "a:" + addr)
        if wait:
            return render_template(
                "login.html", next=nxt, username=username,
                error=f"Too many tries. Wait {max(1, wait // 60)} minute(s) and try again."), 429
        user = store.verify(username, request.form.get("password") or "")
        if not user:
            sessions.throttle.failed("u:" + username, "a:" + addr)
            return render_template("login.html", next=nxt, username=username,
                                   error="That username and password do not match."), 401
        sessions.throttle.cleared("u:" + username)
        store.touch_login(user["username"])
        resp = redirect(f"{base}{auth.PASSWORD_PATH}" if user["must_change"] else nxt)
        resp.headers.add(*sessions.cookie_header(user, secure()))
        return resp

    @portal.route(auth.LOGOUT_PATH, methods=["POST"])
    def logout():
        resp = redirect(request.environ.get("gj3.base", "") + auth.LOGIN_PATH)
        resp.headers.add(*sessions.clear_header(secure()))
        return resp

    @portal.route(auth.PASSWORD_PATH, methods=["GET", "POST"])
    def password():
        me = request.environ["gj3.user"]
        must = bool(request.environ.get("gj3.must_change"))
        page = dict(must_change=must, min_len=accounts_mod.MIN_PASSWORD, error=None, done=False)
        if request.method == "GET":
            return render_template("password.html", **page)
        new, again = request.form.get("new") or "", request.form.get("again") or ""
        if not must and not store.verify(me["username"], request.form.get("current") or ""):
            page["error"] = "Your current password is not right."
        elif new != again:
            page["error"] = "The two new passwords differ."
        else:
            try:
                user = store.set_password(me["username"], new)
            except accounts_mod.AccountError as e:
                page["error"] = str(e)
            else:
                # The change ended every session, this one too: issue a fresh one.
                dest = request.environ.get("gj3.base", "") + "/" if must else None
                if dest:
                    resp = redirect(dest)
                else:
                    page.update(must_change=False, done=True)
                    resp = portal.make_response(render_template("password.html", **page))
                resp.headers.add(*sessions.cookie_header(user, secure()))
                return resp
        return render_template("password.html", **page), 400

    @portal.route("/account/people", methods=["GET", "POST"])
    def people():
        me = request.environ["gj3.user"]
        if me["role"] != "admin":
            return render_template("base.html"), 403
        view = dict(error=None, notice=None, handover=None, me=me["username"])
        if request.method == "POST":
            op = request.form.get("op")
            username = (request.form.get("username") or "").strip().lower()
            try:
                if op == "add":
                    temp = accounts_mod.temporary_password()
                    user = store.add(username, request.form.get("name"), temp,
                                     role="admin" if request.form.get("admin") else "user",
                                     must_change=True)
                    view["handover"] = {"username": user["username"], "name": user["name"],
                                        "password": temp}
                elif op == "reset":
                    temp = accounts_mod.temporary_password()
                    user = store.set_password(username, temp, must_change=True)
                    view["handover"] = {"username": user["username"], "name": user["name"],
                                        "password": temp}
                elif op in ("disable", "enable"):
                    if username == me["username"]:
                        raise accounts_mod.AccountError("You cannot disable yourself.")
                    user = store.update(username, active=(op == "enable"))
                    view["notice"] = (f"{user['name']} can sign in again." if op == "enable"
                                      else f"{user['name']} is disabled and signed out.")
                else:
                    raise accounts_mod.AccountError("Unknown request.")
            except accounts_mod.AccountError as e:
                view["error"] = str(e)
        resp = portal.make_response(render_template("people.html", users=store.list(), **view))
        resp.headers["Cache-Control"] = "no-store"      # a temporary password is on it
        return resp

    return portal


def create_app(cfg):
    """The one WSGI application: the web app's pages and both GUIs, behind the
    sign-in gate and the guard, with the server's NAS root pinned in each GUI."""
    store = accounts_mod.AccountStore(cfg.state_dir)
    sessions = auth.Sessions(store, auth.load_secret(cfg.state_dir))
    log = ActionLog(cfg.state_dir)

    ingest_gui, manager_gui = load_guis()
    for gui in (ingest_gui, manager_gui):
        gui.use_server_settings(cfg.nas_root, home_url="/")
        shell.install(gui.app, cfg)
    # The folder browser in both tools lists only the source folders.
    filebrowse.set_allowed_roots(cfg.source_roots)

    dispatcher = DispatcherMiddleware(_portal_app(cfg, sessions, store, log), {
        INGEST_MOUNT: ingest_gui.app,
        PROJECTS_MOUNT: manager_gui.app,
    })
    return auth.Gate(guard.Guard(dispatcher, cfg.source_roots, log), sessions)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="gjesus3 web app: microscopy and MRI ingest and the Project "
                    "Manager from one URL, behind one sign-in, against ONE NAS root.")
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
    p.add_argument("--state-dir",
                   help="Accounts, session key and action log (default: "
                        f"{server_settings.default_state_dir()}). Never under the NAS root.")
    p.add_argument("--source-root", action="append", default=[],
                   help="A folder people may pick files from, besides <root>\\staging "
                        "(repeatable), e.g. an instrument's export share.")
    p.add_argument("--host", default="127.0.0.1",
                   help="127.0.0.1 (this machine only, the default) or 0.0.0.0 "
                        "(other machines: needs --cert/--key, or --allow-http).")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--cert", help="HTTPS certificate file (PEM)")
    p.add_argument("--key", help="HTTPS private key file (PEM)")
    p.add_argument("--allow-http", action="store_true",
                   help="Serve other machines over plain HTTP. A TEST COPY ONLY: "
                        "passwords then cross the network readable.")
    p.add_argument("--no-browser", action="store_true",
                   help="Do not open the default browser.")
    args = p.parse_args(argv)

    try:
        cfg = server_settings.load_settings(
            nas_root=args.nas_root, config_path=args.config,
            production=args.production, state_dir=args.state_dir,
            source_roots=args.source_root)
    except server_settings.SettingsError as e:
        print(f"gjesus3 web app: not starting: {e}", file=sys.stderr)
        return 2

    tls = None
    if args.cert or args.key:
        if not (args.cert and args.key and os.path.isfile(args.cert)
                and os.path.isfile(args.key)):
            print("gjesus3 web app: not starting: --cert and --key must both name "
                  "existing files.", file=sys.stderr)
            return 2
        tls = (args.cert, args.key)
    if args.host not in LOOPBACK_HOSTS and not tls:
        if not args.allow_http:
            print(f"gjesus3 web app: not starting: --host {args.host!r} lets other "
                  "machines in, and their passwords would cross the network as plain "
                  "text. Give --cert and --key (HTTPS), or --allow-http for a test "
                  "copy only.", file=sys.stderr)
            return 2
        if cfg.production:
            print("gjesus3 web app: not starting: plain HTTP to other machines is "
                  "for a test copy only, never with --production.", file=sys.stderr)
            return 2

    store = accounts_mod.AccountStore(cfg.state_dir)
    if store.count() == 0:
        print("gjesus3 web app: not starting: there are no accounts yet. Make the "
              "first administrator on this machine:\n"
              f"  python tools/webapp/accounts.py --state-dir \"{cfg.state_dir}\" "
              "add <username> --name \"Your Name\" --admin", file=sys.stderr)
        return 2

    application = create_app(cfg)
    scheme = "https" if tls else "http"
    shown = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    url = f"{scheme}://{shown}:{args.port}/"
    print(f"gjesus3 web app on {url}" + (f"  (listening on {args.host})"
                                         if shown != args.host else ""))
    print(f"  NAS root: {cfg.nas_root}  (from {cfg.source})"
          + ("  ** PRODUCTION **" if cfg.production else ""))
    print(f"  State:    {cfg.state_dir}  ({store.count()} account(s))")
    print("  Sources:  " + "; ".join(cfg.source_roots))
    if args.host not in LOOPBACK_HOSTS and not tls:
        print("  ** Plain HTTP to other machines: a test copy only. **")
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    from werkzeug.serving import run_simple
    # threaded: an SSE ingest stream must not block the other pages. No
    # reloader: it would re-exec the process and load the GUIs twice.
    run_simple(args.host, args.port, application, threaded=True,
               use_reloader=False, ssl_context=tls)
    return 0


if __name__ == "__main__":
    sys.exit(main())
