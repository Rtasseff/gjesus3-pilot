#!/usr/bin/env python3
"""test_webapp.py: the combined web app (Box A port, Stage 2.1).

Drives tools/webapp/app.py through werkzeug's test client over throwaway NAS
roots built here, in a temp dir. Nothing touches J:, and the GUIs' per-PC state
(%LOCALAPPDATA%) is redirected into the temp dir before anything loads.

Covered:
  1. settings: no root -> refused, even with $GJESUS3_ROOT and a PC's saved
     choice both naming a valid root; the precedence --nas-root > env > config
     file; a bad config file, a folder that is not an RDM System root, and the
     production root without --production are refused
  2. the entry point: `python tools/webapp/app.py` with no root exits 2 without
     serving; a non-loopback --host is refused
  3. each GUI on its own is unchanged: no prefix, the per-PC root still saved
  4. combined: the landing page and every page under its mount; every link and
     script on each page carries the mount and answers 200; the pages write the
     mount into window.GJ3_BASE
  5. combined: one pinned root. /api/nas_root reports it, a POST cannot change
     it or write the PC's state file, a request naming another root is answered
     from the pinned one, recipes live in <root>/recipes
  6. combined: a preview and a dry-run ingest stream (SSE) under /ingest
  7. the JS: every fetch() goes through apiUrl(); no template hard-codes "/..."

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


# ------------------------------------------------------------- 2. entry point

def test_entry_point(decoy, state):
    print("2. the entry point refuses to serve without a root")
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
    rc = webapp_app.main(["--nas-root", decoy, "--host", "0.0.0.0", "--no-browser"])
    check(rc == 2, "--host 0.0.0.0 is refused while there is no sign-in")


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
    d = c.post("/api/nas_root", json={"nas_root": nas}).get_json()
    saved = os.path.join(state, "gjesus3-operator", "nas_root.txt")
    check(d.get("valid") is True and os.path.isfile(saved)
          and open(saved, encoding="utf-8").read().strip() == nas,
          "ingest: setting the root still saves the PC's choice")
    check(c.get("/api/nas_root").get_json().get("fixed") is False, "ingest: not fixed")

    m = manager_gui.app.test_client()
    html = m.get("/").get_data(as_text=True)
    check('href="/shared/style.css"' in html and 'src="/shared/folder_browser.js"' in html
          and 'window.GJ3_BASE = ""' in html, "manager page: the same /shared links, empty base")
    check("all tools" not in html and not _NAS_READONLY.search(html),
          "manager page: no home link, the root still editable")
    check(m.get("/shared/style.css").status_code == 200, "manager: /shared/style.css still served")


# ------------------------------------------------------------ 4. combined pages

_LINK = re.compile(r'(?:href|src)="([^"]*)"')


def test_pages(client, nas):
    print("4. combined: one URL, every page under its mount")
    r = client.get("/")
    html = r.get_data(as_text=True)
    check(r.status_code == 200, "the landing page answers")
    for target in ('href="/ingest/"', 'href="/ingest/mri"', 'href="/projects/"'):
        check(target in html, f"the landing page links {target}")
    check(nas in html, "the landing page shows the root")
    check(client.get("/ingest").status_code in (301, 308), "/ingest redirects to /ingest/")

    pages = {"/ingest/": "/ingest", "/ingest/mri": "/ingest", "/projects/": "/projects"}
    for page, mount in pages.items():
        r = client.get(page)
        html = r.get_data(as_text=True)
        check(r.status_code == 200, f"{page} answers")
        check(f'window.GJ3_BASE = "{mount}"' in html, f"{page} writes its mount into GJ3_BASE")
        check('href="/"' in html and "all tools" in html, f"{page} links back to the landing page")
        check(bool(_NAS_READONLY.search(html)) and nas in html
              and re.search(r'id="nas-save"[^>]*\bhidden\b', html),
              f"{page} shows the pinned root read-only, its Set button hidden")
        links = [u for u in _LINK.findall(html) if u.startswith("/") and u != "/"]
        stray = [u for u in links if not u.startswith(mount + "/")]
        check(links and not stray, f"{page}: every link carries {mount} ({len(links)} links; stray {stray})")
        broken = [u for u in links if client.get(u).status_code != 200]
        check(not broken, f"{page}: every linked page / asset answers 200 (broken {broken})")
    check(client.get("/nope").status_code == 404, "an unknown path is a 404")


# ------------------------------------------------------------ 5. pinned root

def test_pinned_root(client, nas, decoy, other, state):
    print("5. combined: one pinned root, whatever a page sends")
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

    for mount in ("/ingest", "/projects"):
        d = client.post(f"{mount}/api/listdir", json={"path": nas}).get_json() or {}
        names = [e.get("name") for e in d.get("entries") or []]
        check("registries" in names, f"{mount}/api/listdir lists a folder ({names})")


# ------------------------------------------------------------ 6. ingest routes

def test_ingest_routes(client, nas, decoy, tmp):
    print("6. combined: preview and a dry-run ingest stream under /ingest")
    staging = os.path.join(tmp, "staging_one")
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
        test_entry_point(decoy, state)

        from webapp import app as webapp_app
        from webapp import settings as s
        from werkzeug.test import Client
        ingest_gui, manager_gui = webapp_app.load_guis()
        test_standalone(ingest_gui, manager_gui, nas, state)
        # The standalone check saved `nas` as the PC choice; put the decoy back.
        with open(os.path.join(state, "gjesus3-operator", "nas_root.txt"), "w", encoding="utf-8") as f:
            f.write(decoy)

        client = Client(webapp_app.create_app(s.load_settings(nas_root=nas, environ={})))
        test_pages(client, nas)
        test_pinned_root(client, nas, decoy, other, state)
        test_ingest_routes(client, nas, decoy, tmp)
        test_js_and_templates()
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
