"""Commit path: run a batch ingest by delegating to ingest_raw.run_batch.

This is the ONLY place the operator core writes to the NAS, and it does so
exclusively through the validated pipeline (`ingest_raw.run_batch` ->
`ingest_single`) — no reimplementation. The two operator conveniences layered
on top are:

  - log routing: `ingest_raw` logs via a module-level `log(msg, level)` to
    stdout. When the caller passes `log_callback`, we temporarily swap
    `ingest_raw.log` for a shim that forwards each `(msg, level)` to the
    callback (for a progress UI / streaming log), restoring it afterwards.
  - recipe stamping: the registry `ingest_config` column records which config
    produced each row. Operator runs build the config in memory (no YAML on
    disk), so we stamp `cfg["_ingest_config_path"]` with the
    template/recipe path the front-end passed, keeping that column meaningful.

`dry_run=True` here delegates to the real run_batch dry-run (which stops at the
ingest_single early-return) — use `preview.preview_batch` for the richer
acq_id/project/link preview; this dry_run is for parity-checking against the CLI.
"""

import os

# tools/ on sys.path (see templates.py) so `import ingest_raw` works.
from . import templates as _templates  # noqa: F401  (ensures sys.path setup)
import ingest_raw
from ingest import config


def run(cfg, nas_root, dry_run=False, delete_source=False,
        log_callback=None, nas_unc=None, recipe_path=None):
    """Run (or dry-run) a batch ingest for `cfg` against `nas_root`.

    Args:
        cfg: batch config dict (from config_builder.build_config). Must be a
            batch config (have an auto_discover block); run_batch expects that.
        nas_root: validated NAS root (see env.validate_nas_root).
        dry_run: pass through to run_batch (stops mid-ingest_single).
        delete_source: pass through (OR'd with cfg ingest flag by the pipeline).
        log_callback: optional callable (msg, level) -> None. When given,
            ingest_raw's log is routed to it for the duration of the run.
        nas_unc: optional UNC root (legacy .lnk seam; unused by the hard-link
            linker, threaded through for completeness).
        recipe_path: optional path string stamped into cfg["_ingest_config_path"]
            so the registry ingest_config column records the recipe/template
            that produced these rows. Stored as a forward-slash string.

    Returns:
        list[(acq_id, success)] — exactly what ingest_raw.run_batch returns.

    Raises:
        ValueError: if `cfg` is not a batch config (no auto_discover block).
    """
    if not config.is_batch_config(cfg):
        raise ValueError(
            "runner.run expects a batch config (an `auto_discover` block). "
            "Build it via config_builder.build_config from a per-instrument "
            "template."
        )

    # Stamp the recipe/template path so each row's ingest_config is meaningful.
    if recipe_path:
        cfg["_ingest_config_path"] = str(recipe_path).replace("\\", "/")
    else:
        cfg.setdefault("_ingest_config_path", "")

    if log_callback is None:
        return ingest_raw.run_batch(
            cfg, nas_root,
            dry_run=dry_run, nas_unc=nas_unc, delete_source=delete_source,
        )

    # Route ingest_raw.log -> the caller's callback for the run's duration.
    original_log = ingest_raw.log

    def _shim(msg, level="INFO"):
        try:
            log_callback(msg, level)
        except Exception:  # noqa: BLE001 — a bad callback must not abort ingest
            original_log(msg, level)

    ingest_raw.log = _shim
    try:
        return ingest_raw.run_batch(
            cfg, nas_root,
            dry_run=dry_run, nas_unc=nas_unc, delete_source=delete_source,
        )
    finally:
        ingest_raw.log = original_log


def default_recipe_path(template_path):
    """Build a sensible ingest_config stamp from a template path.

    Returns a repo-relative-ish forward-slash string ('tools/.../foo.yaml' when
    the path contains a 'tools' segment, else the basename). Best-effort — the
    front-ends may pass an explicit recipe_path instead.
    """
    norm = str(template_path).replace("\\", "/")
    parts = norm.split("/")
    if "tools" in parts:
        return "/".join(parts[parts.index("tools"):])
    return os.path.basename(norm)
