"""Turn an operator's "point at this folder" into an (staging_dir, pattern)
pair for the ingest config's auto_discover block.

The pipeline's `config.expand_batch` globs `os.path.join(staging_dir, pattern)`.
`expand_batch` is idempotent (it dedups against the live registry on
`(acq_date, original_name)`), so re-pointing at an overlapping scope is safe —
already-ingested acquisitions are simply skipped. That gives us latitude to err
toward a slightly-broader pattern when in doubt.

Per instrument key, three "point at" shapes are handled:

  NI   — point at ONE acquisition folder (protocol.txt + recon_<idx>/, OR an
         archive-shaped basename) -> staging_dir = parent, pattern = <basename>/.
         Point at a BATCH ROOT (children look like acquisitions) -> pattern "*/".
  MRI  — point at ONE ParaVision exam (acqp + method) -> staging_dir = the
         study's PARENT, pattern "<study>/<exam>". Point at a STUDY folder
         (children are exams) -> staging_dir = its PARENT, pattern "<study>/*".
         Point at a BATCH ROOT (grandchildren are exams) -> "*/*" (template
         default). All three keep original_name = "<study>/<exam>" so the
         (acq_date, original_name) dedup key never collapses to the bare exam
         number (ParaVision exam numbers repeat across studies on a date).
  ZWSI/CELL/LSM9 (microscopy) — glob for the primary extension. If the folder
         directly holds primary files -> "*.czi"; if one level down -> "*/*.czi";
         else fall back to the template's own recursive pattern ("**/*.czi").

`resolve_scope` returns the two strings; the front-end feeds them into
config_builder via `auto_discover.staging_dir` + `auto_discover.pattern`.
"""

import glob as globmod
import os
from pathlib import Path

# tools/ on sys.path (see templates.py) so `from ingest import ...` works.
from . import templates as _templates  # noqa: F401  (ensures sys.path setup)
from ingest import config, ni_metadata


class ScopeError(ValueError):
    """Raised when a folder cannot be scoped for the given instrument key."""


# Default primary extension per microscopy instrument key.
_MICROSCOPY_EXT = {
    "ZWSI": ".czi",
    "CELL": ".czi",
    "LSM9": ".czi",
}


def _norm_path(path):
    p = os.path.abspath(path)
    if not os.path.exists(p):
        raise ScopeError(f"path does not exist: {path!r}")
    if not os.path.isdir(p):
        raise ScopeError(
            f"path is not a directory: {path!r}. Point at a folder."
        )
    return p


def _scandir_sorted(path):
    """Return sorted os.scandir entries, surfacing an unreadable directory as a
    clean ScopeError instead of a raw OSError traceback.

    Shared NAS staging trees commonly contain a permission-denied folder; the
    classification helpers below scan child/grandchild dirs that _norm_path
    never validated, and the front-ends only catch ScopeError — so a bare
    PermissionError from os.scandir would otherwise crash the operator with a
    traceback rather than a readable message.
    """
    try:
        return sorted(os.scandir(path), key=lambda e: e.name)
    except OSError as e:
        raise ScopeError(f"cannot read directory {path!r}: {e}") from e


# ----------------------------------------------------------------- NI

def _looks_like_ni_acquisition(path):
    """True if `path` is itself one NI acquisition.

    Primary signal: ni_metadata.is_ni_acquisition (protocol.txt + recon_<idx>/).
    The extracted round-8 staging folders carry both, so this is reliable for
    archive-mode. (A future live-mode template will need its own detector;
    this is intentionally conservative.)
    """
    return ni_metadata.is_ni_acquisition(path)


def _has_ni_acquisition_children(path):
    """True if any immediate child of `path` looks like an NI acquisition."""
    for entry in _scandir_sorted(path):
        if entry.is_dir() and _looks_like_ni_acquisition(entry.path):
            return True
    return False


def _resolve_ni(path):
    if _looks_like_ni_acquisition(path):
        # Point-at-one-session: staging_dir = parent, pattern = this folder.
        parent = os.path.dirname(path)
        basename = os.path.basename(path)
        return parent, f"{basename}/"
    if _has_ni_acquisition_children(path):
        # Batch root: one level of acquisition folders.
        return path, "*/"
    raise ScopeError(
        f"{path!r} is neither an NI acquisition (needs protocol.txt + a "
        f"recon_<idx>/ subfolder) nor a folder of NI acquisitions. If this is "
        f"a non-extracted / live acquisition, NI live mode is not yet "
        f"supported (pending platform-layout confirmation) — extract the "
        f"archive first."
    )


# ----------------------------------------------------------------- MRI

def _is_paravision_exam(path):
    return config._is_paravision_exam(path)


def _has_paravision_exam_children(path):
    """True if any immediate child of `path` is a ParaVision exam folder."""
    for entry in _scandir_sorted(path):
        if entry.is_dir() and _is_paravision_exam(entry.path):
            return True
    return False


def _has_paravision_exam_grandchildren(path):
    """True if any <child>/<grandchild> of `path` is a ParaVision exam."""
    for child in _scandir_sorted(path):
        if not child.is_dir():
            continue
        if _has_paravision_exam_children(child.path):
            return True
    return False


def _resolve_mri(path):
    if _is_paravision_exam(path):
        # Point-at-one-exam. CRITICAL: root the glob at the study's PARENT and
        # include the study folder in the pattern, so original_name stays
        # "<study>/<exam>". If we instead used (staging=study, pattern="<exam>/")
        # original_name would collapse to the BARE exam number — and ParaVision
        # exam numbers REPEAT across study folders on the same acquisition date
        # (e.g. studies m17/m18/m19/m20 each have an exam "12" on 20251016), so
        # the (acq_date, original_name) dedup key would collide and silently
        # skip a different animal's exams as "already ingested" (data loss).
        # This mirrors batch-root mode, which is the safe relpath form.
        study = os.path.dirname(path)
        batch_root = os.path.dirname(study)
        return batch_root, (
            f"{globmod.escape(os.path.basename(study))}/"
            f"{globmod.escape(os.path.basename(path))}"
        )
    if _has_paravision_exam_children(path):
        # Study folder: glob <study>/<exam> from the study's PARENT (same reason
        # as above — keep original_name = "<study>/<exam>", never the bare exam).
        batch_root = os.path.dirname(path)
        return batch_root, f"{globmod.escape(os.path.basename(path))}/*"
    if _has_paravision_exam_grandchildren(path):
        # Batch root: <study>/<exam> — the template default.
        return path, "*/*"
    raise ScopeError(
        f"{path!r} does not contain Bruker ParaVision exams (an exam folder "
        f"has both 'acqp' and 'method' files). Point at a single exam, a study "
        f"folder, or a batch root containing study folders."
    )


# ----------------------------------------------------------------- microscopy

def _resolve_microscopy(key, path, template_pattern=None):
    ext = _MICROSCOPY_EXT[key]
    # Direct primary files in this folder?
    if globmod.glob(os.path.join(path, f"*{ext}")):
        return path, f"*{ext}"
    # One level down (e.g. <batch>/<file>.czi)?
    if globmod.glob(os.path.join(path, f"*/*{ext}")):
        return path, f"*/*{ext}"
    # Recursive fallback: the template's own pattern (e.g. Cell Observer's
    # "**/*.czi" + path_parse). Keep the template's pattern so its path_parse
    # levels still line up.
    if globmod.glob(os.path.join(path, f"**/*{ext}"), recursive=True):
        return path, (template_pattern or f"**/*{ext}")
    raise ScopeError(
        f"no {ext} files found anywhere under {path!r}. This folder doesn't "
        f"look like a {key} batch."
    )


# ----------------------------------------------------------------- dispatch

_MRI_KEYS = {"MRI"}
_NI_KEYS = {"NI"}


def resolve_scope(instrument_key, path, template_pattern=None):
    """Resolve a "point at this folder" into (staging_dir, pattern).

    Args:
        instrument_key: one of NI / MRI / ZWSI / CELL / LSM9 (case-insensitive).
        path: the folder the operator pointed at (single acquisition / study /
            batch root).
        template_pattern: OPTIONAL — the instrument template's own
            auto_discover.pattern. Used only by the microscopy recursive
            fallback so a template that relies on path_parse keeps its
            recursive glob. Ignored for NI/MRI.

    Returns:
        (staging_dir, pattern) — both strings, ready for
        auto_discover.staging_dir / auto_discover.pattern.

    Raises:
        ScopeError: if `path` doesn't look like a valid scope for the key.
        KeyError:   if `instrument_key` is unknown.
    """
    key = (instrument_key or "").strip().upper()
    abspath = _norm_path(path)

    if key in _NI_KEYS:
        return _resolve_ni(abspath)
    if key in _MRI_KEYS:
        return _resolve_mri(abspath)
    if key in _MICROSCOPY_EXT:
        return _resolve_microscopy(key, abspath, template_pattern)

    raise KeyError(
        f"Unknown instrument key {instrument_key!r}. "
        f"Known: NI, MRI, ZWSI, CELL, LSM9."
    )
