r"""The combined web app's server settings: one place, read once at start.

On a server the NAS root is a setting of the server, not each PC's saved
choice. The two GUIs keep their per-PC behaviour for the exes; the combined app
learns its root here and nowhere else, then pins it in both
(`use_server_settings` in each GUI's app.py).

Where the root may come from, first found wins:

  1. `--nas-root` on the command line
  2. the environment variable `GJESUS3_WEBAPP_NAS_ROOT`
  3. `"nas_root"` in a small JSON file named by `--config` or by
     `GJESUS3_WEBAPP_CONFIG`, e.g. `{"nas_root": "C:\\Users\\me\\temp\\testnas"}`

Deliberately never consulted: `$GJESUS3_ROOT` (the command-line tools' variable;
on the data-office workstation it names the live root), the GUIs' saved choice
in `%LOCALAPPDATA%`, and their built-in default `\\gjesus3\gjesus3\gjesus3-data`.
Any of them would let a test instance fall back to production. With no root the
app refuses to start.

The root must be an RDM System root (a folder holding `registries\`). The
production root, the one whose `registries\` holds the `.production` marker
(decision 16), is refused unless production is asked for: `--production`, or
`"production": true` in the config file. The same rule as `ingest_raw.py
--production`, and the same marker test (`ingest_raw.is_production_root`).

Two more settings since sign-in (2.2):

  * the STATE FOLDER: the accounts, the session key and the action log. It
    stays on the server's own disk, never under the NAS root, so password hashes
    never reach the share. `--state-dir`, else `GJESUS3_WEBAPP_STATE_DIR`, else
    `"state_dir"` in the config file, else `%LOCALAPPDATA%\gjesus3-webapp`.
  * the SOURCE FOLDERS: where a signed-in person may browse and pick files to
    ingest or copy. Always `<root>\staging`, plus each `--source-root` (or
    `"source_roots"` in the config file), e.g. an instrument's export share.
    Nothing outside them can be listed or read through the app.
"""

import json
import os
from dataclasses import dataclass, field

ENV_NAS_ROOT = "GJESUS3_WEBAPP_NAS_ROOT"
ENV_CONFIG = "GJESUS3_WEBAPP_CONFIG"
ENV_STATE_DIR = "GJESUS3_WEBAPP_STATE_DIR"
CONFIG_KEYS = ("nas_root", "production", "state_dir", "source_roots")


class SettingsError(ValueError):
    """The server cannot start with these settings; the message says why."""


@dataclass(frozen=True)
class Settings:
    nas_root: str       # absolute; a folder holding registries/
    source: str         # where the root came from, for the start-up banner
    production: bool    # the root carries registries/.production
    state_dir: str = ""                       # accounts, session key, action log
    source_roots: tuple = field(default=())   # where people may pick files from


def default_state_dir(environ=None):
    """%LOCALAPPDATA%\\gjesus3-webapp on Windows; ~/.local/state elsewhere."""
    environ = os.environ if environ is None else environ
    base = environ.get("LOCALAPPDATA") or environ.get("XDG_STATE_HOME") \
        or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, "gjesus3-webapp")


def _inside(path, root):
    """True when `path` is `root` or below it (case-insensitive on Windows)."""
    p = os.path.normcase(os.path.abspath(path))
    r = os.path.normcase(os.path.abspath(root))
    try:
        return os.path.commonpath([p, r]) == r
    except ValueError:      # different drives
        return False


def _read_config(path):
    """The config file's dict. Unknown keys are refused, so a typo cannot
    silently drop a setting."""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except OSError as e:
        raise SettingsError(f"cannot read the config file {path!r}: {e}")
    except ValueError as e:
        raise SettingsError(f"the config file {path!r} is not valid JSON: {e}")
    if not isinstance(data, dict):
        raise SettingsError(f"the config file {path!r} must hold a JSON object")
    unknown = sorted(set(data) - set(CONFIG_KEYS))
    if unknown:
        raise SettingsError(f"the config file {path!r} has unknown key(s) {unknown}; "
                            f"known: {list(CONFIG_KEYS)}")
    return data


def load_settings(nas_root=None, config_path=None, production=False, environ=None,
                  state_dir=None, source_roots=None):
    """Resolve, validate and return the server's Settings, or raise SettingsError.

    `nas_root`, `config_path`, `production`, `state_dir` and `source_roots` are
    the command-line values; `environ` defaults to os.environ (a test passes its
    own).
    """
    environ = os.environ if environ is None else environ
    config_path = config_path or environ.get(ENV_CONFIG) or None
    config = _read_config(config_path) if config_path else {}

    if nas_root and nas_root.strip():
        raw, source = nas_root, "--nas-root"
    elif (environ.get(ENV_NAS_ROOT) or "").strip():
        raw, source = environ[ENV_NAS_ROOT], f"${ENV_NAS_ROOT}"
    elif str(config.get("nas_root") or "").strip():
        raw, source = str(config["nas_root"]), f"config file {config_path}"
    else:
        raise SettingsError(
            "no NAS root is set. Pass --nas-root, or set "
            f"{ENV_NAS_ROOT}, or name a JSON config file holding \"nas_root\" "
            f"(--config or {ENV_CONFIG}). $GJESUS3_ROOT and a PC's saved choice "
            "are deliberately not used, so a test instance can never open the "
            "production root by default.")

    root = os.path.abspath(os.path.expanduser(raw.strip()))
    if not (os.path.isdir(root) and os.path.isdir(os.path.join(root, "registries"))):
        raise SettingsError(
            f"{root!r} (from {source}) is not an RDM System root: it must be a "
            "folder that contains 'registries'. Build a scratch one with "
            "tools/operator/make_test_nas.py.")

    from ingest_raw import PRODUCTION_MARKER, is_production_root
    is_prod = is_production_root(root)
    asked = bool(production) or config.get("production") is True
    if is_prod and not asked:
        raise SettingsError(
            f"{root!r} is the PRODUCTION root (registries/{PRODUCTION_MARKER} is "
            "present). Refusing without --production (or \"production\": true in "
            "the config file). Use a scratch root for testing.")

    state = (state_dir or "").strip() or (environ.get(ENV_STATE_DIR) or "").strip() \
        or str(config.get("state_dir") or "").strip() or default_state_dir(environ)
    state = os.path.abspath(os.path.expanduser(state))
    if _inside(state, root):
        raise SettingsError(
            f"the state folder {state!r} is inside the NAS root. It holds the "
            "accounts' password hashes, so it must stay on the server's own disk.")

    extra = list(source_roots or []) or list(config.get("source_roots") or [])
    roots = [os.path.join(root, "staging")]
    for r in extra:
        r = str(r).strip()
        if not r:
            continue
        if not os.path.isabs(r):
            raise SettingsError(f"source root {r!r} must be an absolute path")
        roots.append(os.path.abspath(r))
    return Settings(nas_root=root, source=source, production=is_prod,
                    state_dir=state, source_roots=tuple(roots))
