#!/usr/bin/env python3
"""test_webapp.py: the web app (Box A port, Stage 2: 2.1 one app, 2.2 sign-in).

Drives tools/webapp/app.py through werkzeug's test client over throwaway NAS
roots built here, in a temp dir. Nothing touches J:, and the GUIs' per-PC state
(%LOCALAPPDATA%) and the web app's state folder are redirected into the temp dir
before anything loads.

Covered:
  1. settings: no root -> refused, even with $GJESUS3_ROOT and a PC's saved
     choice both naming a valid root; the precedence --nas-root > env > config
     file; a bad config file, a folder that is not an RDM System root, and the
     production root without --production are refused; the state folder never
     under the root; the source folders (always <root>\\staging, plus extras)
  2. the entry point: no root, other machines without HTTPS (or --allow-http),
     plain HTTP with --production, missing certificate files, and no accounts
     yet: each exits 2 without serving
  3. each GUI on its own is unchanged: no prefix, no shell, the per-PC root saved
  4. signed in: Home and every tool page under its mount, inside the shared
     shell; every link and script answers 200; the mount in window.GJ3_BASE
  5. one pinned root. /api/nas_root reports it, a POST cannot change it or write
     the PC's state file, a request naming another root is answered from the
     pinned one, recipes live in <root>/recipes; the folder browser is confined
     to the source folders
  6. a preview and a dry-run ingest stream (SSE) under /ingest
  7. the JS: every fetch() goes through apiUrl(); no template hard-codes "/..."
  8. sign-in: nothing without a session (pages redirect, calls get 401), static
     files are public, the cookie's flags, wrong passwords, the throttle, no open
     redirect, cross-site writes refused, sign-out; accounts: the admin's People
     page, a temporary password that must be changed first, a password change
     or disabling ending older sessions, non-admins kept out, the rules on
     usernames, names and passwords
  9. attribution: the people fields start as the signed-in person; the
     project's provenance records the signed-in person whatever the page posts;
     the action log records writes with their outcome, and Home shows them
 10. the guard: a tool call naming a folder or file outside the source folders
     is refused before the tool runs

Run:  python tools/webapp/test_webapp.py      (exit 0 = pass)
"""

import csv
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))     # tools/webapp
TOOLS = os.path.dirname(_HERE)
if TOOLS not in sys.path:
    sys.path.append(TOOLS)

FAILED = []

# Test-only passwords for the throwaway accounts this file makes.
PW_ADA = "ada-test-password-1"
PW_BEA_NEW = "bea-test-password-2"


def check(cond, msg):
    print(f"  {'ok' if cond else 'FAIL'}:   {msg}")
    if not cond:
        FAILED.append(msg)


# ------------------------------------------------------------------ fixture

PROJECT_COLS = ["project_id", "name", "description", "owner", "start_date",
                "status", "last_activity", "folder_location", "notes"]


def build_nas(root, project_name):
    """A minimal RDM System root: the registries, one project with its folder."""
    from ingest import provenance, registry
    reg = os.path.join(root, "registries")
    os.makedirs(reg)
    for sub in ("raw", "staging"):
        os.makedirs(os.path.join(root, sub))
    with open(os.path.join(reg, "registry_raw.csv"), "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(registry.REGISTRY_FIELDS)
    with open(os.path.join(reg, "registry_projects.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(PROJECT_COLS)
        w.writerow(["PROJ-0001", project_name, "A study", "AA", "2026-01-01", "active",
                    "2026-01-01", f"/projects/{project_name}/", ""])
    pdir = os.path.join(root, "projects", project_name)
    os.makedirs(os.path.join(pdir, "raw_linked"))
    with open(os.path.join(pdir, "_project.yaml"), "w", encoding="utf-8") as f:
        f.write(f"project_id: PROJ-0001\nname: {project_name}\nstatus: active\n")
    provenance.write_empty(os.path.join(pdir, "provenance.csv"))
    return root


_NAS_READONLY = re.compile(r'<input id="nas-root"[^>]*\breadonly\b')


def snapshot(path):
    """{path: (size, mtime)} for every file under `path`."""
    out = {}
    for dp, _dn, fn in os.walk(path):
        for name in fn:
            p = os.path.join(dp, name)
            st = os.stat(p)
            out[p] = (st.st_size, st.st_mtime_ns)
    return out


def sign_in(client, username, password, next_="/"):
    return client.post("/account/login",
                       data={"username": username, "password": password, "next": next_})


def location(r):
    return r.headers.get("Location", "")


# ------------------------------------------------------------------ 1. settings

def test_settings(nas, decoy, prod, tmp):
    print("1. settings: one explicit root, never a fallback")
    from webapp import settings as s

    def refused(**kw):
        try:
            s.load_settings(**kw)
        except s.SettingsError as e:
            return str(e)
        return None

    msg = refused(environ={})
    check(msg and "--nas-root" in msg, "no root anywhere -> refused, naming --nas-root")
    msg = refused(environ={"GJESUS3_ROOT": decoy})
    check(msg is not None, "$GJESUS3_ROOT naming a valid root is NOT used -> still refused")

    cfg = s.load_settings(environ={s.ENV_NAS_ROOT: nas})
    check(cfg.nas_root == os.path.abspath(nas) and cfg.source == f"${s.ENV_NAS_ROOT}"
          and not cfg.production, f"${s.ENV_NAS_ROOT} sets the root")
    cfg = s.load_settings(nas_root=nas, environ={s.ENV_NAS_ROOT: decoy})
    check(cfg.nas_root == os.path.abspath(nas) and cfg.source == "--nas-root",
          "--nas-root beats the environment variable")

    conf = os.path.join(tmp, "webapp.json")
    with open(conf, "w", encoding="utf-8") as f:
        json.dump({"nas_root": nas}, f)
    cfg = s.load_settings(config_path=conf, environ={})
    check(cfg.nas_root == os.path.abspath(nas), "a config file (--config) sets the root")
    cfg = s.load_settings(environ={s.ENV_CONFIG: conf})
    check(cfg.nas_root == os.path.abspath(nas), f"a config file named by ${s.ENV_CONFIG} too")
    cfg = s.load_settings(environ={s.ENV_CONFIG: conf, s.ENV_NAS_ROOT: decoy})
    check(cfg.nas_root == os.path.abspath(decoy), "the environment variable beats the config file")

    bad = os.path.join(tmp, "typo.json")
    with open(bad, "w", encoding="utf-8") as f:
        json.dump({"nasroot": nas}, f)
    msg = refused(config_path=bad, environ={})
    check(msg and "unknown key" in msg, "a config file with an unknown key is refused")
    with open(bad, "w", encoding="utf-8") as f:
        f.write("{not json")
    check(refused(config_path=bad, environ={}) is not None, "a config file that is not JSON is refused")
    msg = refused(nas_root=os.path.join(tmp, "no_such_root"), environ={})
    check(msg and "registries" in msg, "a folder that is not an RDM System root is refused")

    msg = refused(nas_root=prod, environ={})
    check(msg and "PRODUCTION" in msg, "the production root without --production is refused")
    cfg = s.load_settings(nas_root=prod, production=True, environ={})
    check(cfg.production, "--production lets it start, flagged as production")
    with open(conf, "w", encoding="utf-8") as f:
        json.dump({"nas_root": prod, "production": True}, f)
    check(s.load_settings(config_path=conf, environ={}).production,
          "or \"production\": true in the config file")

    msg = refused(nas_root=nas, state_dir=os.path.join(nas, "tmp", "state"), environ={})
    check(msg and "state folder" in msg, "a state folder under the NAS root is refused")
    cfg = s.load_settings(nas_root=nas, environ={"LOCALAPPDATA": os.path.join(tmp, "lad")})
    check(cfg.state_dir == os.path.join(tmp, "lad", "gjesus3-webapp"),
          "the state folder defaults to %LOCALAPPDATA%\\gjesus3-webapp")
    extra = os.path.join(tmp, "instrument_share")
    cfg = s.load_settings(nas_root=nas, state_dir=os.path.join(tmp, "st"),
                          source_roots=[extra], environ={})
    check(cfg.source_roots == (os.path.join(cfg.nas_root, "staging"), os.path.abspath(extra)),
          "source folders: <root>\\staging first, then each --source-root")
    msg = refused(nas_root=nas, source_roots=["relative\\share"], environ={})
    check(msg and "absolute" in msg, "a relative source folder is refused")


# ------------------------------------------------------------- 2. entry point

def test_entry_point(decoy, prod, state, tmp):
    print("2. the entry point refuses to serve when it should")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GJESUS3_WEBAPP_")}
    env.update({"GJESUS3_ROOT": decoy, "LOCALAPPDATA": state, "PYTHONDONTWRITEBYTECODE": "1"})
    script = os.path.join(_HERE, "app.py")
    try:
        p = subprocess.run([sys.executable, script, "--no-browser"], env=env,
                           capture_output=True, text=True, timeout=120)
        rc, err = p.returncode, p.stderr
    except subprocess.TimeoutExpired:
        rc, err = None, "TIMEOUT: it started serving"
    check(rc == 2 and "not starting" in err and "no NAS root" in err,
          f"no root (with $GJESUS3_ROOT and a saved PC choice set): exit 2, nothing served "
          f"(rc={rc}, {err.strip()[-160:]!r})")

    from webapp import app as webapp_app
    empty_state = os.path.join(tmp, "empty_state")
    common = ["--state-dir", empty_state, "--no-browser"]
    check(webapp_app.main(["--nas-root", decoy, "--host", "0.0.0.0"] + common) == 2,
          "other machines (--host 0.0.0.0) without HTTPS or --allow-http: refused")
    check(webapp_app.main(["--nas-root", prod, "--production", "--host", "0.0.0.0",
                           "--allow-http"] + common) == 2,
          "plain HTTP to other machines with --production: refused")
    check(webapp_app.main(["--nas-root", decoy, "--cert", os.path.join(tmp, "none.pem"),
                           "--key", os.path.join(tmp, "none.key")] + common) == 2,
          "--cert/--key naming missing files: refused")
    check(webapp_app.main(["--nas-root", decoy] + common) == 2,
          "no accounts yet: refused (it says how to make the first administrator)")


# ---------------------------------------------------------- 3. standalone

def test_standalone(ingest_gui, manager_gui, nas, state):
    print("3. each GUI on its own: unchanged")
    check(ingest_gui.server_nas_root() is None and manager_gui.server_nas_root() is None,
          "nothing pinned until the combined app pins it")
    c = ingest_gui.app.test_client()
    html = c.get("/").get_data(as_text=True)
    check('window.GJ3_BASE = ""' in html, "ingest page: an empty base path")
    check('href="/static/help/microscopy_guide.html"' in html and 'href="/mri"' in html,
          "ingest page: the same links as before (url_for, no prefix)")
    check("all tools" not in html and not _NAS_READONLY.search(html),
          "ingest page: no home link, the root still editable")
    check("gj-top" not in html and "window.GJ3_USER = null" in html and "<header>" in html,
          "ingest page: no shell, no signed-in person, its own header shown")
    d = c.post("/api/nas_root", json={"nas_root": nas}).get_json()
    saved = os.path.join(state, "gjesus3-operator", "nas_root.txt")
    check(d.get("valid") is True and os.path.isfile(saved)
          and open(saved, encoding="utf-8").read().strip() == nas,
          "ingest: setting the root still saves the PC's choice")
    check(c.get("/api/nas_root").get_json().get("fixed") is False, "ingest: not fixed")
    d = c.post("/api/listdir", json={"path": nas}).get_json() or {}
    check("registries" in [e.get("name") for e in d.get("entries") or []] and not d.get("error"),
          "ingest: the folder browser still lists any folder of the PC")

    m = manager_gui.app.test_client()
    html = m.get("/").get_data(as_text=True)
    check('href="/shared/style.css"' in html and 'src="/shared/folder_browser.js"' in html
          and 'window.GJ3_BASE = ""' in html, "manager page: the same /shared links, empty base")
    check("all tools" not in html and not _NAS_READONLY.search(html),
          "manager page: no home link, the root still editable")
    check("gj-top" not in html and "window.GJ3_USER = null" in html
          and "Add files from my computer" in html and 'id="r-creator" type="text">' in html,
          "manager page: no shell; its tabs and the typed creator as before")
    check(m.get("/shared/style.css").status_code == 200, "manager: /shared/style.css still served")


# ------------------------------------------------------------ 4. combined pages

_LINK = re.compile(r'(?:href|src)="([^"]*)"')
SHELL_LINKS = {"/", "/ingest/", "/ingest/mri", "/projects/", "/static/shell.css",
               "/static/shell.js", "/account/password", "/account/people"}


def test_pages(client, nas):
    print("4. signed in: Home and every tool, inside the shared shell")
    r = client.get("/")
    html = r.get_data(as_text=True)
    check(r.status_code == 200, "Home answers")
    for target in ('href="/ingest/"', 'href="/ingest/mri"', 'href="/projects/"'):
        check(target in html, f"Home links {target}")
    check("Hello, Ada." in html and "Ada Admin" in html, "Home greets the signed-in person")
    check(nas in html and os.path.join(nas, "staging") in html,
          "Home names the root (badge) and the source folders")
    check('class="gj-env test"' in html and "Test copy" in html,
          "a test root is marked as a test copy")
    check(client.get("/ingest").status_code in (301, 308), "/ingest redirects to /ingest/")

    pages = {"/ingest/": ("/ingest", "microscopy"), "/ingest/mri": ("/ingest", "mri"),
             "/projects/": ("/projects", "projects")}
    for page, (mount, key) in pages.items():
        r = client.get(page)
        html = r.get_data(as_text=True)
        check(r.status_code == 200, f"{page} answers")
        check(f'window.GJ3_BASE = "{mount}"' in html, f"{page} writes its mount into GJ3_BASE")
        check('class="gj-top"' in html and "<header hidden>" in html
              and 'aria-current="page"' in html,
              f"{page}: the shared header, its own hidden, the current tool marked")
        check(bool(_NAS_READONLY.search(html)) and nas in html
              and re.search(r'id="nas-save"[^>]*\bhidden\b', html),
              f"{page} still holds the pinned root read-only (in the hidden header)")
        links = [u for u in _LINK.findall(html) if u.startswith("/")]
        stray = [u for u in links if not u.startswith(mount + "/") and u not in SHELL_LINKS]
        check(links and not stray, f"{page}: every link carries {mount} or is the shell's "
                                   f"({len(links)} links; stray {stray})")
        broken = [u for u in set(links) if client.get(u).status_code != 200]
        check(not broken, f"{page}: every linked page / asset answers 200 (broken {broken})")
    check(client.get("/nope").status_code == 404, "an unknown path is a 404")


# ------------------------------------------------------------ 5. pinned root

def test_pinned_root(client, nas, decoy, other, state):
    print("5. one pinned root, whatever a page sends; the browser confined")
    saved = os.path.join(state, "gjesus3-operator", "nas_root.txt")
    before = snapshot(state)
    for mount in ("/ingest", "/projects"):
        d = client.get(f"{mount}/api/nas_root").get_json()
        check(d.get("nas_root") == nas and d.get("valid") and d.get("fixed") is True,
              f"{mount}/api/nas_root reports the pinned root, fixed")
        r = client.post(f"{mount}/api/nas_root", json={"nas_root": other})
        d = r.get_json()
        check(d.get("nas_root") == nas and d.get("fixed") is True,
              f"{mount}: POSTing another (valid) root changes nothing")
    check(snapshot(state) == before, "no per-PC state file written or changed")
    check(open(saved, encoding="utf-8").read().strip() == decoy, "the saved PC choice is untouched")

    d = client.post("/projects/api/projects", json={"nas_root": decoy}).get_json()
    names = [p.get("name") for p in d.get("projects") or []]
    check(names == ["alpha"], f"/projects/api/projects naming another root lists the pinned one ({names})")
    d = client.post("/projects/api/check_project_name",
                    json={"nas_root": decoy, "name": "alpha"}).get_json()
    check(d.get("errors"), "a new-project name check runs against the pinned root (alpha is taken)")

    d = client.get("/ingest/api/recipes_dir").get_json()
    check(os.path.normcase(d.get("recipes_dir", "")) == os.path.normcase(os.path.join(nas, "recipes"))
          and d.get("fixed") is True, "recipes live in <pinned root>/recipes")
    d = client.post("/ingest/api/recipes_dir", json={"recipes_dir": decoy}).get_json()
    check(os.path.normcase(d.get("recipes_dir", "")) == os.path.normcase(os.path.join(nas, "recipes")),
          "POSTing another recipes folder changes nothing")

    staging = os.path.join(nas, "staging")
    os.makedirs(os.path.join(staging, "batch_a"), exist_ok=True)
    for mount in ("/ingest", "/projects"):
        d = client.post(f"{mount}/api/listdir", json={}).get_json() or {}
        check(d.get("path") == staging and "batch_a" in [e.get("name") for e in d.get("entries") or []]
              and d.get("parent") is None and d.get("drives") == [staging],
              f"{mount}/api/listdir opens on <root>\\staging; no way up; the jump bar is the sources")
        d = client.post(f"{mount}/api/listdir", json={"path": nas}).get_json() or {}
        check(d.get("error") and "only open" in d["error"] and d.get("path") == staging
              and "registries" not in [e.get("name") for e in d.get("entries") or []],
              f"{mount}/api/listdir of the root itself: refused, shows staging instead")
        d = client.post(f"{mount}/api/listdir",
                        json={"path": os.path.join(staging, "..", "registries")}).get_json() or {}
        check(d.get("error") and d.get("path") == staging,
              f"{mount}/api/listdir: a '..' path out of staging is refused")


# ------------------------------------------------------------ 6. ingest routes

def test_ingest_routes(client, nas, decoy, tmp):
    print("6. preview and a dry-run ingest stream under /ingest")
    staging = os.path.join(nas, "staging", "staging_one")
    os.makedirs(staging)
    with open(os.path.join(staging, "not_really.czi"), "wb") as f:
        f.write(b"not a czi")          # enough to pass the scope; the engine drops it
    body = {"instrument": "ZWSI", "overrides": {}, "staging_path": staging, "nas_root": decoy}
    r = client.post("/ingest/api/preview", json=body)
    d = r.get_json() or {}
    check(r.status_code == 200 and "n_matched" in d,
          f"/ingest/api/preview runs the engine ({r.status_code}: {str(d)[:160]})")
    before = snapshot(nas)
    r = client.post("/ingest/api/ingest", json=dict(body, dry_run=True))
    text = r.get_data(as_text=True)
    events = [json.loads(ln[6:]) for ln in text.splitlines() if ln.startswith("data: ")]
    kinds = [e.get("kind") for e in events]
    check(r.status_code == 200 and r.mimetype == "text/event-stream" and kinds
          and kinds[-1] in ("done", "error"),
          f"/ingest/api/ingest streams SSE to a final event ({r.status_code}, {kinds[-3:]})")
    check(snapshot(nas) == before, "a dry run writes nothing under the root")
    d = client.post("/ingest/api/mri/preview", json={"staging_path": staging}).get_json() or {}
    check("n_matched" in d or "error" in d, f"/ingest/api/mri/preview answers JSON ({str(d)[:120]})")


# ------------------------------------------------------------------ 7. the JS

def test_js_and_templates():
    print("7. the JS and templates: no absolute URL left")
    js_files = [os.path.join(TOOLS, "operator", "gui", "static", n)
                for n in ("app.js", "mri.js", "folder_browser.js")]
    js_files.append(os.path.join(TOOLS, "manager", "gui", "static", "manager.js"))
    for path in js_files:
        with open(path, encoding="utf-8") as f:
            code = [ln for ln in f.read().splitlines()
                    if not ln.strip().startswith(("//", "*", "/*"))]
        src = "\n".join(code)
        bad = re.findall(r"\bfetch\((?!apiUrl\()[^)]{0,40}", src)
        check(not bad, f"{os.path.basename(path)}: every fetch() goes through apiUrl() ({bad})")
        check("window.GJ3_BASE" in src, f"{os.path.basename(path)}: apiUrl reads window.GJ3_BASE")
    tpls = [os.path.join(TOOLS, "operator", "gui", "templates", n) for n in ("index.html", "mri.html")]
    tpls.append(os.path.join(TOOLS, "manager", "gui", "templates", "index.html"))
    for path in tpls:
        with open(path, encoding="utf-8") as f:
            src = f.read()
        bad = re.findall(r'(?:href|src)="/[^"]*"', src)
        check(not bad, f"{os.path.basename(os.path.dirname(os.path.dirname(path)))}/"
                       f"{os.path.basename(path)}: no hard-coded absolute link ({bad})")
        check("window.GJ3_BASE = {{ request.script_root|tojson }}" in src,
              f"{os.path.basename(path)}: writes the mount into GJ3_BASE")


# ------------------------------------------------------------------ 8. sign-in

def test_sign_in(make_client, nas, store):
    print("8. sign-in and accounts")
    from webapp import accounts as acc
    anon = make_client()
    r = anon.get("/")
    check(r.status_code == 302 and location(r).endswith("/account/login?next=/"),
          f"not signed in: Home redirects to the sign-in page ({r.status_code} {location(r)})")
    r = anon.get("/projects/")
    check(r.status_code == 302 and "next=/projects/" in location(r),
          "not signed in: a tool page redirects to sign-in, and back afterwards")
    r = anon.get("/ingest/api/nas_root")
    check(r.status_code == 401 and "signed out" in (r.get_json() or {}).get("error", ""),
          "not signed in: an API call gets 401 with a message")
    before = snapshot(nas)
    r = anon.post("/projects/api/create_project",
                  json={"name": "sneaky", "description": "x", "owner": "x"})
    check(r.status_code == 401 and snapshot(nas) == before,
          "not signed in: a write is refused and nothing changes")
    check(all(anon.get(u).status_code == 200 for u in
              ("/account/login", "/static/shell.css", "/ingest/static/style.css")),
          "the sign-in page and static files need no session")

    r = sign_in(anon, "ada", "wrong-password-xx")
    check(r.status_code == 401 and "do not match" in r.get_data(as_text=True),
          "a wrong password: refused, without saying which part was wrong")
    r = sign_in(anon, "nobody", PW_ADA)
    check(r.status_code == 401, "an unknown username: refused the same way")

    ada = make_client()
    r = sign_in(ada, "ada", PW_ADA, next_="/projects/")
    cookie = " ".join(r.headers.getlist("Set-Cookie"))
    check(r.status_code == 302 and location(r).endswith("/projects/"),
          "signed in: sent on to where they were going")
    check("gj3_session=" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie,
          "the session cookie is HttpOnly and SameSite=Strict")
    check(ada.get("/").status_code == 200, "signed in: Home answers")
    r = sign_in(make_client(), "ada", PW_ADA, next_="//evil.example/x")
    check(location(r).rstrip("/") in ("", "http://localhost") and "evil" not in location(r),
          f"no open redirect: next=//evil.example goes Home ({location(r)})")
    r = ada.post("/projects/api/create_project", json={"name": "fromelsewhere",
                 "description": "x", "owner": "x"}, headers={"Origin": "http://evil.example"})
    check(r.status_code == 403 and not os.path.isdir(os.path.join(nas, "projects", "fromelsewhere")),
          "a write from another site (Origin) is refused, nothing created")
    r = ada.post("/projects/api/projects", json={},
                 headers={"Origin": "http://localhost"})
    check(r.status_code == 200, "a same-site call with its Origin is let through")

    # --- People: an admin adds a person with a temporary password
    r = ada.post("/account/people", data={"op": "add", "username": "bea", "name": "Bea User"})
    html = r.get_data(as_text=True)
    m = re.search(r'<code class="gj-temp">([^<]+)</code>', html)
    check(r.status_code == 200 and m and r.headers.get("Cache-Control") == "no-store",
          "People: adding someone shows a one-time temporary password, not cached")
    temp = m.group(1) if m else ""
    r = ada.post("/account/people", data={"op": "add", "username": "bea", "name": "Bea Again"})
    check("already an account" in r.get_data(as_text=True), "People: a duplicate username is refused")
    r = ada.post("/account/people", data={"op": "add", "username": "cy", "name": "Cy; Semi"})
    check("cannot contain" in r.get_data(as_text=True), "People: a name with ';' is refused")
    r = ada.post("/account/people", data={"op": "add", "username": "Bad Name!", "name": "X"})
    check("username is 2 to 32" in r.get_data(as_text=True), "People: a bad username is refused")
    r = ada.post("/account/people", data={"op": "disable", "username": "ada"})
    check("cannot disable yourself" in r.get_data(as_text=True), "People: no one disables themselves")

    bea = make_client()
    r = sign_in(bea, "bea", temp)
    check(r.status_code == 302 and location(r).endswith("/account/password"),
          "a temporary password: sent straight to choose their own")
    r = bea.get("/ingest/")
    check(r.status_code == 302 and location(r).endswith("/account/password"),
          "until then, every page leads back to the password page")
    r = bea.get("/ingest/api/nas_root")
    check(r.status_code == 403, "until then, every API call is refused")
    check(bea.get("/account/people").status_code == 302, "until then, not even the People page")
    r = bea.post("/account/password", data={"new": "short", "again": "short"})
    check(r.status_code == 400 and "at least" in r.get_data(as_text=True), "a short password is refused")
    r = bea.post("/account/password", data={"new": PW_BEA_NEW, "again": PW_BEA_NEW + "x"})
    check(r.status_code == 400 and "differ" in r.get_data(as_text=True), "two different passwords are refused")
    r = bea.post("/account/password", data={"new": PW_BEA_NEW, "again": PW_BEA_NEW})
    check(r.status_code == 302 and location(r).rstrip("/") in ("", "http://localhost"),
          "own password chosen: on to Home")
    check("Hello, Bea." in bea.get("/").get_data(as_text=True), "and Home greets them")
    r = bea.get("/account/people")
    check(r.status_code == 403, "a non-admin cannot open People")
    r = bea.post("/account/people", data={"op": "add", "username": "eve", "name": "Eve"})
    check(r.status_code == 403 and store.get("eve") is None, "a non-admin cannot add anyone")

    bea2 = make_client()
    sign_in(bea2, "bea", PW_BEA_NEW)
    check(bea2.get("/").status_code == 200, "a second session for the same person works")
    r = bea.post("/account/password", data={"current": "not-it-at-all", "new": PW_BEA_NEW + "3",
                                            "again": PW_BEA_NEW + "3"})
    check(r.status_code == 400 and "current password" in r.get_data(as_text=True),
          "changing a password needs the current one")
    r = bea.post("/account/password", data={"current": PW_BEA_NEW, "new": PW_BEA_NEW + "3",
                                            "again": PW_BEA_NEW + "3"})
    check(r.status_code == 200 and "is changed" in r.get_data(as_text=True)
          and bea.get("/").status_code == 200,
          "a password change keeps this session")
    check(bea2.get("/").status_code == 302, "...and ends the older one")
    r = ada.post("/account/people", data={"op": "disable", "username": "bea"})
    check("disabled" in r.get_data(as_text=True) and bea.get("/").status_code == 302
          and sign_in(make_client(), "bea", PW_BEA_NEW + "3").status_code == 401,
          "disabling someone ends their session and stops their sign-in")
    ada.post("/account/people", data={"op": "enable", "username": "bea"})
    check(sign_in(make_client(), "bea", PW_BEA_NEW + "3").status_code == 302,
          "enabling them again lets them back in")

    try:
        store.update("ada", active=False)
        last_admin = False
    except acc.AccountError:
        last_admin = True
    check(last_admin, "the last administrator cannot be disabled")
    try:
        store.add("dan", "Dan", "dan")
        weak = False
    except acc.AccountError:
        weak = True
    check(weak, "a password equal to the username (and too short) is refused")
    raw = open(store.path, encoding="utf-8").read()
    check(PW_ADA not in raw and PW_BEA_NEW not in raw and '"hash"' in raw,
          "users.json holds hashes, never a password")

    r = ada.post("/account/logout")
    check(r.status_code == 302 and "gj3_session=;" in " ".join(r.headers.getlist("Set-Cookie"))
          and ada.get("/").status_code == 302, "sign-out clears the session")

    t = make_client()      # a fresh app: its own throttle
    for _ in range(5):
        sign_in(t, "ada", "wrong-password-xx")
    r = sign_in(t, "ada", PW_ADA)
    check(r.status_code == 429 and "Too many tries" in r.get_data(as_text=True),
          "five wrong passwords: even the right one waits")


# ------------------------------------------------------------ 9. attribution

def test_attribution(client, nas, log):
    print("9. attribution: the signed-in person, and the action log")
    html = client.get("/ingest/mri").get_data(as_text=True)
    check('id="operator" type="text" placeholder="e.g. Irene" value="Ada Admin"' in html,
          "MRI: the operator starts as the signed-in person (still editable)")
    html = client.get("/ingest/").get_data(as_text=True)
    check('window.GJ3_USER = {"name": "Ada Admin"' in html or '"name": "Ada Admin"' in html,
          "microscopy: the page knows the person, for the researcher field")
    html = client.get("/projects/").get_data(as_text=True)
    check('id="c-owner" type="text" size="18" value="Ada Admin"' in html,
          "projects: a new project's owner starts as the signed-in person")
    check(re.search(r'id="r-creator" type="text" value="Ada Admin" readonly', html)
          and re.search(r'id="l-creator" type="text" value="Ada Admin" readonly', html),
          "projects: 'recorded as' is the signed-in person and cannot be edited")
    check("Add other files" in html and "Add files from my computer" not in html,
          "projects: the tabs say what they do on a server")

    src = os.path.join(nas, "staging", "notes_for_alpha.txt")
    with open(src, "w", encoding="utf-8") as f:
        f.write("a note\n")
    r = client.post("/projects/api/import_local",
                    json={"project": "PROJ-0001", "sources": [src], "creator": "Mallory"})
    text = r.get_data(as_text=True)
    kinds = [json.loads(ln[6:]).get("kind") for ln in text.splitlines() if ln.startswith("data: ")]
    prov = open(os.path.join(nas, "projects", "alpha", "provenance.csv"), encoding="utf-8").read()
    check(kinds and kinds[-1] == "done" and "Ada Admin" in prov and "Mallory" not in prov,
          f"provenance records the signed-in person, not the name the page posted ({kinds[-1:]})")

    recs = log.recent("ada", limit=50)
    acts = {r_["action"]: r_ for r_ in recs}
    ing = acts.get("microscopy-ingest")
    check(ing and ing["dry_run"] is True and ing["status"] in ("done", "error")
          and ing["user"] == "ada" and ing["name"] == "Ada Admin" and "staging_one" in ing["what"],
          f"the action log has the dry-run ingest, its person and folder ({ing})")
    add = acts.get("project-add-files")
    check(add and add["status"] == "done" and "PROJ-0001" in add["what"],
          f"the action log has the file copy, done ({add})")
    check(not any(r_["action"] == "project-create" and "fromelsewhere" in r_["what"] for r_ in recs),
          "a refused cross-site write is not logged as an action")
    html = client.get("/").get_data(as_text=True)
    check("Added files to a project" in html and "Microscopy ingest" in html and "test run" in html,
          "Home lists the person's recent activity")


# ------------------------------------------------------------ 10. the guard

def test_guard(client, nas, tmp):
    print("10. the guard: tool calls read only from the source folders")
    outside = os.path.join(tmp, "outside_batch")
    os.makedirs(outside)
    with open(os.path.join(outside, "secret.czi"), "wb") as f:
        f.write(b"x")
    r = client.post("/ingest/api/preview", json={"instrument": "ZWSI", "overrides": {},
                                                 "staging_path": outside})
    check(r.status_code == 403 and "outside the folders" in (r.get_json() or {}).get("error", ""),
          "a preview of a folder outside the sources: refused, naming where to put files")
    r = client.post("/ingest/api/ingest", json={"instrument": "ZWSI", "overrides": {},
                                                "staging_path": outside, "dry_run": False})
    check(r.status_code == 403, "an ingest from outside the sources: refused")
    r = client.post("/projects/api/import_local_plan",
                    json={"project": "PROJ-0001", "sources": [os.path.join(outside, "secret.czi")]})
    check(r.status_code == 403, "copying a file from outside the sources into a project: refused")
    r = client.post("/ingest/api/sample_layout", json={"path": outside})
    check(r.status_code == 403, "reading a sample layout outside the sources: refused")
    r = client.post("/ingest/api/sftp_pull", json={"remotes": [], "staging_root": outside})
    check(r.status_code == 403, "pulling scanner data into a folder outside the sources: refused")
    from webapp import guard
    check(guard.inside_any(os.path.join(nas, "staging", "x", "y"), [os.path.join(nas, "staging")])
          and not guard.inside_any(os.path.join(nas, "staging", "..", "raw"),
                                   [os.path.join(nas, "staging")]),
          "inside_any: below a root yes; '..' out of it no")


# ------------------------------------------------------------------ main

def main():
    if importlib.util.find_spec("flask") is None:
        print("skip: Flask not installed")
        return 0
    tmp = tempfile.mkdtemp(prefix="gj3_webapp_")
    try:
        # Redirect the GUIs' per-PC state BEFORE they load, and plant a saved
        # choice + $GJESUS3_ROOT naming a valid decoy root: the combined app
        # must use neither.
        state = os.path.join(tmp, "state")
        os.environ["LOCALAPPDATA"] = state
        os.environ.pop("XDG_STATE_HOME", None)
        for k in [k for k in os.environ if k.startswith("GJESUS3_WEBAPP_")]:
            os.environ.pop(k)
        nas = build_nas(os.path.join(tmp, "nas"), "alpha")
        decoy = build_nas(os.path.join(tmp, "decoy"), "decoyproj")
        other = build_nas(os.path.join(tmp, "other"), "otherproj")
        prod = build_nas(os.path.join(tmp, "prod"), "prodproj")
        open(os.path.join(prod, "registries", ".production"), "w").close()
        os.makedirs(os.path.join(state, "gjesus3-operator"))
        with open(os.path.join(state, "gjesus3-operator", "nas_root.txt"), "w", encoding="utf-8") as f:
            f.write(decoy)
        os.environ["GJESUS3_ROOT"] = decoy

        test_settings(nas, decoy, prod, tmp)
        test_entry_point(decoy, prod, state, tmp)

        from webapp import app as webapp_app
        from webapp import settings as s
        from webapp.accounts import AccountStore
        from webapp.actionlog import ActionLog
        from werkzeug.test import Client
        ingest_gui, manager_gui = webapp_app.load_guis()
        test_standalone(ingest_gui, manager_gui, nas, state)
        # The standalone check saved `nas` as the PC choice; put the decoy back.
        with open(os.path.join(state, "gjesus3-operator", "nas_root.txt"), "w", encoding="utf-8") as f:
            f.write(decoy)

        web_state = os.path.join(tmp, "web_state")
        cfg = s.load_settings(nas_root=nas, state_dir=web_state, environ={})
        store = AccountStore(web_state)
        store.add("ada", "Ada Admin", PW_ADA, role="admin")

        def make_client():
            return Client(webapp_app.create_app(cfg))

        client = make_client()
        check(sign_in(client, "ada", PW_ADA).status_code == 302, "the test admin signs in")
        test_pages(client, nas)
        test_pinned_root(client, nas, decoy, other, state)
        test_ingest_routes(client, nas, decoy, tmp)
        test_js_and_templates()
        test_sign_in(make_client, nas, store)
        test_attribution(client, nas, ActionLog(web_state))
        test_guard(client, nas, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILED:
        print(f"{len(FAILED)} CHECK(S) FAILED")
        for m in FAILED:
            print(f"  - {m}")
        return 1
    print("ALL WEB-APP CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
