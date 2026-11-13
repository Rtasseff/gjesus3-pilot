#!/usr/bin/env python3
r"""The web app's own accounts: one person, one sign-in (Box A port, Stage 2.2).

Ryan's direction (2026-11-06, confirmed 2026-11-13): people sign in to the app
with a password that belongs to the app alone; the server process itself runs
under Ryan's Windows account, so every file it writes is his on the share. The
sign-in is what records WHO did something: it fills `creator`, defaults
`owner`, the researcher and the MRI operator, and names the person in the
action log.

The store is one JSON file, `users.json`, in the server's state folder (see
settings.py; never under the NAS root). Passwords are kept only as salted hashes
(werkzeug's generate_password_hash). A user record:

    {"name": "Ryan Tasseff",      # as written into creator / owner / researcher
     "role": "admin" | "user",    # admin may add people and reset passwords
     "active": true,
     "hash": "scrypt:...",
     "must_change": false,        # true after an admin sets a temporary one
     "pw_version": 3,             # bumped on every change: older sessions end
     "created": "2026-11-13T10:00:00", "last_login": "..."}

The first administrator is made on the server, from this file:

    python tools\webapp\accounts.py add ryan --name "Ryan Tasseff" --admin
    (asks for the password twice; nothing is echoed or printed)

Everyone else is added on the app's "People" page by an administrator, who
gives them a temporary password to change at first sign-in.
"""

import argparse
import datetime as _dt
import getpass
import json
import os
import re
import secrets
import sys
import threading

from werkzeug.security import check_password_hash, generate_password_hash

USERS_FILE = "users.json"
ROLES = ("user", "admin")
MIN_PASSWORD = 10
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,31}$")
# A name goes into registry and sidecar fields; `;` separates list values there.
NAME_BAD = re.compile(r"[;\x00-\x1f\x7f]")


class AccountError(ValueError):
    """A refused account change; the message is shown to the person."""


def _now():
    return _dt.datetime.now().replace(microsecond=0).isoformat()


def check_username(username):
    u = (username or "").strip().lower()
    if not USERNAME_RE.match(u):
        raise AccountError("A username is 2 to 32 characters: lower-case letters, "
                           "digits, dot, dash or underscore, starting with a letter "
                           "or digit.")
    return u


def check_name(name):
    n = " ".join((name or "").split())
    if not n or len(n) > 80:
        raise AccountError("The full name is required (at most 80 characters). It is "
                           "what the app writes as creator, owner or researcher.")
    if NAME_BAD.search(n):
        raise AccountError("The full name cannot contain ';' or control characters.")
    return n


def check_password(password, username=""):
    if len(password or "") < MIN_PASSWORD:
        raise AccountError(f"The password needs at least {MIN_PASSWORD} characters.")
    if username and password.strip().lower() == username.lower():
        raise AccountError("The password cannot be the username.")
    return password


def temporary_password():
    """A one-time password an admin hands over; the person changes it at once."""
    return secrets.token_urlsafe(9)


class AccountStore:
    """users.json in the state folder. Thread-safe within one server process;
    every change is written to a temporary file and swapped in whole."""

    def __init__(self, state_dir):
        self.state_dir = state_dir
        self.path = os.path.join(state_dir, USERS_FILE)
        self._lock = threading.Lock()

    # -------------------------------------------------------------- storage
    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return {"users": {}}
        if not isinstance(data, dict) or not isinstance(data.get("users"), dict):
            raise AccountError(f"{self.path} is not an accounts file")
        return data

    def _save(self, data):
        os.makedirs(self.state_dir, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    # -------------------------------------------------------------- reading
    def get(self, username):
        """The public part of one user (no hash), or None."""
        u = (username or "").strip().lower()
        with self._lock:
            rec = self._load()["users"].get(u)
        return self.public(u, rec) if rec else None

    @staticmethod
    def public(username, rec):
        return {"username": username, "name": rec["name"], "role": rec["role"],
                "active": bool(rec.get("active", True)),
                "must_change": bool(rec.get("must_change")),
                "pw_version": int(rec.get("pw_version", 1)),
                "created": rec.get("created"), "last_login": rec.get("last_login")}

    def list(self):
        with self._lock:
            users = self._load()["users"]
        return [self.public(u, r) for u, r in sorted(users.items())]

    def count(self):
        with self._lock:
            return len(self._load()["users"])

    def verify(self, username, password):
        """The public user when the password matches an ACTIVE account, else None.
        A wrong username costs the same hash check as a wrong password."""
        u = (username or "").strip().lower()
        with self._lock:
            rec = self._load()["users"].get(u)
        if not rec or not rec.get("active", True):
            check_password_hash(_DUMMY_HASH, password or "")
            return None
        if not check_password_hash(rec["hash"], password or ""):
            return None
        return self.public(u, rec)

    # -------------------------------------------------------------- changes
    def add(self, username, name, password, role="user", must_change=False):
        u = check_username(username)
        n = check_name(name)
        if role not in ROLES:
            raise AccountError(f"role must be one of {ROLES}")
        check_password(password, u)
        with self._lock:
            data = self._load()
            if u in data["users"]:
                raise AccountError(f"There is already an account '{u}'.")
            data["users"][u] = {
                "name": n, "role": role, "active": True,
                "hash": generate_password_hash(password),
                "must_change": bool(must_change), "pw_version": 1,
                "created": _now(), "last_login": None,
            }
            self._save(data)
        return self.get(u)

    def set_password(self, username, password, must_change=False):
        u = (username or "").strip().lower()
        check_password(password, u)
        with self._lock:
            data = self._load()
            rec = data["users"].get(u)
            if not rec:
                raise AccountError(f"No account '{u}'.")
            rec["hash"] = generate_password_hash(password)
            rec["must_change"] = bool(must_change)
            rec["pw_version"] = int(rec.get("pw_version", 1)) + 1
            self._save(data)
        return self.get(u)

    def update(self, username, name=None, role=None, active=None):
        u = (username or "").strip().lower()
        with self._lock:
            data = self._load()
            rec = data["users"].get(u)
            if not rec:
                raise AccountError(f"No account '{u}'.")
            if name is not None:
                rec["name"] = check_name(name)
            if role is not None:
                if role not in ROLES:
                    raise AccountError(f"role must be one of {ROLES}")
                if rec["role"] == "admin" and role != "admin" and \
                        _active_admins(data) == [u]:
                    raise AccountError("This is the last administrator.")
                rec["role"] = role
            if active is not None:
                if not active and rec["role"] == "admin" and _active_admins(data) == [u]:
                    raise AccountError("This is the last administrator.")
                rec["active"] = bool(active)
                if not active:      # end their sessions
                    rec["pw_version"] = int(rec.get("pw_version", 1)) + 1
            self._save(data)
        return self.get(u)

    def touch_login(self, username):
        with self._lock:
            data = self._load()
            rec = data["users"].get(username)
            if rec:
                rec["last_login"] = _now()
                self._save(data)


def _active_admins(data):
    return [u for u, r in data["users"].items()
            if r.get("role") == "admin" and r.get("active", True)]


# A fixed hash to check against when the username does not exist, so the
# response time does not tell anyone which usernames are real.
_DUMMY_HASH = generate_password_hash(secrets.token_hex(16))


# ------------------------------------------------------------------ CLI

def _read_password(args):
    if args.password_stdin:
        pw = sys.stdin.readline().rstrip("\r\n")
    else:
        pw = getpass.getpass("New password: ")
        if getpass.getpass("Again: ") != pw:
            raise AccountError("The two passwords differ.")
    return pw


def main(argv=None):
    from webapp import settings as server_settings   # the same default folder
    p = argparse.ArgumentParser(description="The gjesus3 web app's accounts.")
    p.add_argument("--state-dir", help="the server's state folder (default: "
                   f"${server_settings.ENV_STATE_DIR}, else "
                   f"{server_settings.default_state_dir()})")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="add an account (asks for its password)")
    a.add_argument("username")
    a.add_argument("--name", required=True, help="full name, as written into metadata")
    a.add_argument("--admin", action="store_true")
    a.add_argument("--password-stdin", action="store_true",
                   help="read the password from one line of standard input")
    r = sub.add_parser("reset", help="set a new password (asks for it)")
    r.add_argument("username")
    r.add_argument("--password-stdin", action="store_true")
    sub.add_parser("list", help="list the accounts (never the passwords)")
    args = p.parse_args(argv)

    state = (args.state_dir or os.environ.get(server_settings.ENV_STATE_DIR)
             or server_settings.default_state_dir())
    store = AccountStore(os.path.abspath(state))
    try:
        if args.cmd == "add":
            user = store.add(args.username, args.name, _read_password(args),
                             role="admin" if args.admin else "user")
            print(f"Added {user['username']} ({user['name']}, {user['role']}) in {store.path}")
        elif args.cmd == "reset":
            user = store.set_password(args.username, _read_password(args))
            print(f"New password set for {user['username']}; their old sessions have ended.")
        else:
            for u in store.list():
                print(f"{u['username']:<16} {u['role']:<6} "
                      f"{'active' if u['active'] else 'disabled':<9} {u['name']}"
                      f"  (last sign-in: {u['last_login'] or 'never'})")
    except AccountError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    _TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _TOOLS not in sys.path:
        sys.path.append(_TOOLS)
    sys.exit(main())
