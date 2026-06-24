"""NAS-root resolution + validation and FTP-creds presence check.

Mirrors `ingest_raw.main`'s fail-fast: a real NAS root is a directory that
contains a `registries/` subfolder. Without this check, native Python silently
creates whatever path was passed (e.g. the WSL default `/mnt/gjesus3` resolves
to `C:\\mnt\\gjesus3` on Windows native Python) and an ingest can run to
completion writing into a phantom tree. The front-ends call `validate_nas_root`
so the operator gets one clear message instead of the silent-phantom failure.

FTP creds use the same env-var names as `tools/ftp_mirror.py`:
`GJESUS3_FTP_HOST/USER/PASSWORD/PORT`.
"""

import configparser
import os

# Defaults mirror ingest_raw.main's argparse defaults.
DEFAULT_NAS_ROOT = "/mnt/gjesus3"
DEFAULT_NAS_UNC = r"\\GJESUS3\gjesus3"


class NasRootError(ValueError):
    """Raised when the resolved NAS root does not look like a real NAS root."""


def resolve_nas_root(explicit=None):
    """Resolve the NAS root: explicit arg > $GJESUS3_ROOT > default.

    Does NOT validate — call `validate_nas_root` for that. Mirrors the
    precedence of ingest_raw.main's --nas-root (default $GJESUS3_ROOT or
    /mnt/gjesus3).
    """
    if explicit:
        return explicit
    return os.environ.get("GJESUS3_ROOT", DEFAULT_NAS_ROOT)


def resolve_nas_unc(explicit=None):
    """Resolve the NAS UNC root: explicit arg > $GJESUS3_UNC > default.

    The current hard-link linker does not use the UNC (it uses local
    NAS-volume paths), but the value is still threaded through for the legacy
    .lnk porting seam — same as ingest_raw.main.
    """
    if explicit:
        return explicit
    return os.environ.get("GJESUS3_UNC", DEFAULT_NAS_UNC)


def is_valid_nas_root(nas_root):
    """True if `nas_root` is a dir containing a `registries/` subdir."""
    if not nas_root:
        return False
    registries_dir = os.path.join(nas_root, "registries")
    return os.path.isdir(nas_root) and os.path.isdir(registries_dir)


def validate_nas_root(nas_root):
    """Validate the NAS root, raising NasRootError with a plain-language message.

    Returns `nas_root` unchanged on success so it can be used inline.
    """
    if not is_valid_nas_root(nas_root):
        raise NasRootError(
            f"NAS root does not look valid: {nas_root!r} (expected a directory "
            f"containing a 'registries/' subfolder).\n"
            "Pass an explicit NAS root, or set GJESUS3_ROOT in your shell. "
            "On Windows PowerShell: $env:GJESUS3_ROOT = 'J:\\' (adjust the "
            "drive letter to your NAS mount). On WSL/Linux: typically "
            "/mnt/gjesus3."
        )
    return nas_root


def require_nas_root(explicit=None):
    """Resolve then validate in one step. Returns the validated NAS root."""
    return validate_nas_root(resolve_nas_root(explicit))


# --- FTP credentials (SFTP pull from the MRI console; see ftp_mirror.py) ---

# Same env-var names as tools/ftp_mirror.py.
FTP_ENV_HOST = "GJESUS3_FTP_HOST"
FTP_ENV_USER = "GJESUS3_FTP_USER"
FTP_ENV_PASSWORD = "GJESUS3_FTP_PASSWORD"
FTP_ENV_PORT = "GJESUS3_FTP_PORT"

# Durable credential store (DECIDED 2026-06-12, see
# equipment/historical_data_archives.md §MRI). INI file in the user profile --
# NOT the repo, NOT OneDrive. A shared on-site machine reads it instead of
# re-setting env vars every session:
#
#     [mri]
#     host = kenia.cicbiomagune.int
#     user = mriuser
#     password = <password>
#
# Env vars (GJESUS3_FTP_*) still win per-field, so a session can override.
FTP_CRED_FILE = os.path.join(os.path.expanduser("~"), ".ssh", "gjesus3_mri.cred")
FTP_CRED_SECTION = "mri"


def read_cred_file(path=None):
    """Read the [mri] section of the SFTP credentials file.

    Returns a dict with host/user/password/port keys (missing -> None), or an
    empty dict if the file is absent / unreadable / has no [mri] section.
    Never raises -- a missing or malformed file degrades to "no creds here".
    """
    path = path or FTP_CRED_FILE
    if not os.path.isfile(path):
        return {}
    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8")
    except (configparser.Error, OSError):
        return {}
    if not parser.has_section(FTP_CRED_SECTION):
        return {}
    sec = parser[FTP_CRED_SECTION]
    return {k: (sec.get(k) or None) for k in ("host", "user", "password", "port")}


def ftp_creds():
    """Return the SFTP connection params dict.

    Precedence per field: env var (GJESUS3_FTP_*) > ~/.ssh/gjesus3_mri.cred
    [mri] section > default. Port defaults to 22 to match ftp_mirror.main.
    """
    cred = read_cred_file()
    port_raw = os.environ.get(FTP_ENV_PORT) or cred.get("port") or "22"
    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        port = 22
    return {
        "host": os.environ.get(FTP_ENV_HOST) or cred.get("host"),
        "user": os.environ.get(FTP_ENV_USER) or cred.get("user"),
        "password": os.environ.get(FTP_ENV_PASSWORD) or cred.get("password"),
        "port": port,
    }


def ftp_creds_present():
    """True if host + user + password are resolvable (env var or cred file).

    Port has a default (22), so it is not required here.
    """
    c = ftp_creds()
    return bool(c["host"] and c["user"] and c["password"])
