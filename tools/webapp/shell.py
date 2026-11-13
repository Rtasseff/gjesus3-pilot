r"""One look for every page: the shared header, navigation and page title.

The three tools were built as separate apps, each with its own header, its own
"← all tools" link and a box showing the storage root. Inside the web app they
should read as ONE tool: the same top bar (gjesus3 · Home · Microscopy · MRI ·
Projects · the person's menu), the same test-copy warning, the same page title
and help link, in the same place on every page.

`install(gui_app, cfg)` teaches a mounted GUI's templates about the shell:
  * its Jinja loader also finds this folder's templates (`_shell_header.html`);
  * a context processor gives every template `shell` (None when the GUI runs on
    its own or as an exe, so their pages stay exactly as they were).
The GUIs' templates then include the header and hide their own when `shell` is
set. Nothing else in them changes.
"""

import os

from flask import request
from jinja2 import ChoiceLoader, FileSystemLoader

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

# key, label, path under the server root
NAV = (
    ("home", "Home", "/"),
    ("microscopy", "Microscopy", "/ingest/"),
    ("mri", "MRI", "/ingest/mri"),
    ("projects", "Projects", "/projects/"),
)

PAGES = {
    "home": {"title": "Home", "lede": "", "help": None},
    "microscopy": {
        "title": "Add microscopy images",
        "lede": "AxioScan 7, Cell Observer or LSM 900: pick a batch folder, check what "
                "will happen, then add it to gjesus3.",
        "help": "/ingest/static/help/microscopy_guide.html"},
    "mri": {
        "title": "Add MRI scans",
        "lede": "Bruker ParaVision: pull studies from the scanner, check what will "
                "happen, then add them to gjesus3.",
        "help": "/ingest/static/help/mri_guide.html"},
    "projects": {
        "title": "Projects",
        "lede": "Find a project, start a new one, or add data to one: acquisitions "
                "already in gjesus3, or other files from the source folders.",
        "help": None},
    "account": {"title": "Your account", "lede": "", "help": None},
    "people": {"title": "People", "lede": "Who can sign in, and as whom their work "
                                          "is recorded.", "help": None},
}


def _active(environ, path):
    mount = environ.get("SCRIPT_NAME", "")[len(environ.get("gj3.base", "")):]
    if mount.startswith("/ingest"):
        return "mri" if path.startswith("/mri") else "microscopy"
    if mount.startswith("/projects"):
        return "projects"
    if path.startswith("/account/people"):
        return "people"
    if path.startswith("/account"):
        return "account"
    return "home"


def context(cfg, environ, path):
    """The `shell` dict a template renders the header from, or None."""
    user = environ.get("gj3.user")
    if not user:
        return None
    base = environ.get("gj3.base", "")
    active = _active(environ, path)
    page = dict(PAGES.get(active, PAGES["home"]))
    if page.get("help"):
        page["help"] = base + page["help"]
    return {
        "user": user,
        "is_admin": user.get("role") == "admin",
        "active": active,
        "nav": [{"key": k, "label": label, "url": base + url} for k, label, url in NAV],
        "page": page,
        "production": cfg.production,
        "root": cfg.nas_root,
        "home": base + "/",
        "css": base + "/static/shell.css",
        "js": base + "/static/shell.js",
        "account_url": base + "/account/password",
        "people_url": base + "/account/people",
        "logout_url": base + "/account/logout",
    }


_CFG_KEY = "GJ3_SHELL_SETTINGS"


def install(gui_app, cfg):
    """Give a mounted GUI the shell; again later only swaps the settings.

    The processor is appended to Flask's list directly: `@app.context_processor`
    refuses once an app has served a request (the GUIs may have, standalone)."""
    first = _CFG_KEY not in gui_app.config
    gui_app.config[_CFG_KEY] = cfg
    if not first:
        return
    gui_app.jinja_loader = ChoiceLoader([gui_app.jinja_loader, FileSystemLoader(TEMPLATES)])

    def _shell():
        return {"shell": context(gui_app.config[_CFG_KEY], request.environ, request.path)}
    gui_app.template_context_processors[None].append(_shell)
