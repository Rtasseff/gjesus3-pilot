r"""Sign-in in front of the whole web app (Box A port, Stage 2.2).

One WSGI middleware, `Gate`, wraps EVERYTHING the server answers (the home page,
both mounted GUIs, the account pages), so no tool can be reached without a
session, and every tool sees the same person:

    environ["REMOTE_USER"]  the username
    environ["gj3.user"]     {"username", "name", "role"}  (name = what metadata gets)

The session is a signed cookie (itsdangerous, the key in the state folder's
`secret.key`), valid for SESSION_HOURS, holding only the username and the
account's password version: a password change, a reset or disabling an account
ends every older session at once.

Cross-site requests: the cookie is SameSite=Strict, and a request that changes
something (POST, PUT, PATCH, DELETE) is refused when its Origin (or Referer)
names another site. So a page elsewhere cannot make a signed-in browser ingest.

Not signed in: a page is redirected to the sign-in page (and back afterwards);
an API call gets 401 with a message the tools' pages already show.
"""

import json
import os
import secrets
import threading
import time
from urllib.parse import quote, urlsplit

from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.http import dump_cookie, parse_cookie

COOKIE = "gj3_session"
SESSION_HOURS = 12
SECRET_FILE = "secret.key"
LOGIN_PATH = "/account/login"
LOGOUT_PATH = "/account/logout"
PASSWORD_PATH = "/account/password"
SETUP_PATH = "/account/setup"
SETUP_CODE_FILE = "setup_code.txt"
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
# Reached without a session: the sign-in page and plain static files (the
# stylesheets and scripts are in the repository anyway).
PUBLIC_EXACT = (LOGIN_PATH,)
PUBLIC_PREFIXES = ("/static/", "/ingest/static/", "/projects/shared/", "/projects/static/")


def make_setup_code(state_dir):
    """A fresh one-time code for the first-run setup page, written to the state
    folder (readable only by the server's account) and never printed."""
    os.makedirs(state_dir, exist_ok=True)
    code = secrets.token_urlsafe(9)
    with open(os.path.join(state_dir, SETUP_CODE_FILE), "w", encoding="ascii") as f:
        f.write(code + "\n")
    return code


def load_secret(state_dir):
    """The session-signing key; made once, on first start."""
    path = os.path.join(state_dir, SECRET_FILE)
    try:
        with open(path, "r", encoding="ascii") as f:
            key = f.read().strip()
        if len(key) >= 32:
            return key
    except FileNotFoundError:
        pass
    os.makedirs(state_dir, exist_ok=True)
    key = secrets.token_hex(32)
    with open(path, "w", encoding="ascii") as f:
        f.write(key)
    return key


class Throttle:
    """Slows down password guessing. Keys are "u:<username>" or "a:<address>":
    after MAX_FAILS failed sign-ins for one username (MAX_FAILS_ADDRESS from one
    address, which several people may share) within WINDOW seconds, that key
    waits until its oldest failure leaves the window."""
    MAX_FAILS = 5
    MAX_FAILS_ADDRESS = 20
    WINDOW = 600

    def __init__(self):
        self._fails = {}
        self._lock = threading.Lock()

    def _recent(self, key, now):
        return [t for t in self._fails.get(key, []) if now - t < self.WINDOW]

    def wait_seconds(self, *keys):
        now = time.time()
        with self._lock:
            waits = []
            for k in keys:
                fails = self._recent(k, now)
                self._fails[k] = fails
                limit = self.MAX_FAILS_ADDRESS if k.startswith("a:") else self.MAX_FAILS
                if len(fails) >= limit:
                    waits.append(int(self.WINDOW - (now - fails[-limit])) + 1)
            return max(waits or [0])

    def failed(self, *keys):
        now = time.time()
        with self._lock:
            for k in keys:
                self._fails[k] = self._recent(k, now) + [now]

    def cleared(self, *keys):
        with self._lock:
            for k in keys:
                self._fails.pop(k, None)


class Sessions:
    """Makes and reads the session cookie."""

    def __init__(self, accounts, secret):
        self.accounts = accounts
        self._s = URLSafeTimedSerializer(secret, salt="gj3-session")
        self.throttle = Throttle()

    def cookie_header(self, user, secure):
        token = self._s.dumps({"u": user["username"], "v": user["pw_version"]})
        return ("Set-Cookie", dump_cookie(COOKIE, token, max_age=SESSION_HOURS * 3600,
                                          path="/", httponly=True, secure=secure,
                                          samesite="Strict"))

    @staticmethod
    def clear_header(secure):
        return ("Set-Cookie", dump_cookie(COOKIE, "", max_age=0, path="/",
                                          httponly=True, secure=secure,
                                          samesite="Strict"))

    def user_from(self, environ):
        """The signed-in, active user for this request, else None."""
        token = parse_cookie(environ.get("HTTP_COOKIE", "")).get(COOKIE)
        if not token:
            return None
        try:
            data = self._s.loads(token, max_age=SESSION_HOURS * 3600)
        except BadSignature:
            return None
        user = self.accounts.get(data.get("u"))
        if not user or not user["active"] or user["pw_version"] != data.get("v"):
            return None
        return user


def _same_origin(environ):
    """False when a state-changing request plainly comes from another site."""
    host = (environ.get("HTTP_HOST") or "").lower()
    for header in ("HTTP_ORIGIN", "HTTP_REFERER"):
        value = environ.get(header)
        if value:
            if value == "null":
                return False
            return urlsplit(value).netloc.lower() == host
    return True     # no browser context: a script on the server, or a test


def _is_api(path, environ):
    return "/api/" in path or "application/json" in (environ.get("HTTP_ACCEPT") or "")


def _json(start_response, status, message):
    body = json.dumps({"error": message}).encode("utf-8")
    start_response(status, [("Content-Type", "application/json"),
                            ("Content-Length", str(len(body))),
                            ("Cache-Control", "no-store")])
    return [body]


def _redirect(start_response, location):
    start_response("302 Found", [("Location", location), ("Cache-Control", "no-store")])
    return [b""]


class Gate:
    def __init__(self, app, sessions):
        self.app = app
        self.sessions = sessions

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO") or "/"
        method = environ.get("REQUEST_METHOD", "GET").upper()
        base = environ.get("SCRIPT_NAME", "")
        environ["gj3.base"] = base

        if method not in SAFE_METHODS and not _same_origin(environ):
            return _json(start_response, "403 Forbidden",
                         "Refused: this request came from another web site.")

        # First run: no account exists yet. Everything leads to the setup page,
        # which asks for the one-time code in the state folder (see app.py):
        # only someone who can open files as the server's account gets in.
        if self.sessions.accounts.count() == 0:
            if path == SETUP_PATH or path.startswith(PUBLIC_PREFIXES):
                return self.app(environ, start_response)
            if _is_api(path, environ):
                return _json(start_response, "503 Service Unavailable",
                             "This app has no accounts yet: the first administrator "
                             "must be made on the server.")
            return _redirect(start_response, f"{base}{SETUP_PATH}")

        user = self.sessions.user_from(environ)
        if user:
            environ["REMOTE_USER"] = user["username"]
            environ["gj3.user"] = {"username": user["username"], "name": user["name"],
                                   "role": user["role"]}
            environ["gj3.must_change"] = user["must_change"]

        if path in PUBLIC_EXACT or path.startswith(PUBLIC_PREFIXES):
            return self.app(environ, start_response)
        if not user:
            if _is_api(path, environ):
                return _json(start_response, "401 Unauthorized",
                             "You are signed out (the session ended). Reload the page "
                             "to sign in again; nothing was done.")
            here = base + path + (("?" + environ["QUERY_STRING"])
                                  if environ.get("QUERY_STRING") else "")
            return _redirect(start_response, f"{base}{LOGIN_PATH}?next={quote(here)}")
        if user["must_change"] and path not in (PASSWORD_PATH, LOGOUT_PATH):
            if _is_api(path, environ):
                return _json(start_response, "403 Forbidden",
                             "Choose your own password first (the page will ask).")
            return _redirect(start_response, f"{base}{PASSWORD_PATH}")
        return self.app(environ, start_response)
