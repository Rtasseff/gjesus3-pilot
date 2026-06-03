# `tools/operator/` import contract — READ BEFORE ADDING A FRONT-END

This package is the shared, GUI-agnostic core for the operator-facing ingest
front-ends (Phase 1 of `tasks/operator_ingest_tooling_plan.md`). It reuses the
validated pipeline (`ingest.*`, `ingest_raw`) and never reimplements ingest
logic.

## Why there is no importable `__init__.py`

The directory is named `operator` (mandated by the build plan), which collides
with the Python standard-library `operator` module. If this directory were a
regular package with an importable `__init__.py`, then **any** time `tools/` (or
`tools/` as the current working directory) is on `sys.path` ahead of the
stdlib — which is exactly what happens when an operator runs
`python ingest_raw.py` from `tools/` — the bare name `operator` would resolve to
THIS package and shadow the stdlib `operator`. That breaks the interpreter:
`collections`, `dataclasses`, `functools`, etc. internally do
`from operator import eq`, and the whole pipeline fails to start with
`ImportError: cannot import name 'eq' from 'operator'`.

Verified: adding `tools/operator/__init__.py` makes `python ingest_raw.py --help`
crash from the `tools/` directory; removing it fixes it. This is a hard
constraint, not a style choice.

## How to import this package

Do NOT `import operator` (that's the stdlib) and do NOT `from operator import …`.
Use the loader, which registers the package under the non-colliding alias
`gj_op_core` and uses relative intra-package imports so the package works under
any name:

```python
import os, importlib.util
_here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "gj_operator_loader", os.path.join(_here, "operator", "_loader.py"))
_l = importlib.util.module_from_spec(spec); spec.loader.exec_module(_l)
op = _l.load()                      # the package

op.templates.load_template("MRI")
op.scope.resolve_scope("NI", "/path/to/folder")
op.preview.preview_batch(cfg, nas_root)
op.runner.run(cfg, nas_root, dry_run=True, log_callback=cb)
```

The front-ends `ni_ingest.py` / `mri_ingest.py` (Phases 2-3) live INSIDE this
directory and may instead use relative imports (`from . import preview`) when
launched as part of the package; the microscopy GUI (Phase 4) uses the loader.

`sys.path` handling: `templates.py` APPENDS `tools/` to `sys.path` (never
inserts at the front) so the stdlib `operator` keeps winning while the
non-colliding `ingest` / `ingest_raw` names still resolve.

## Modules

| module | role |
|---|---|
| `templates.py` | load a per-instrument template dict (repo + `sys._MEIPASS` aware); `INSTRUMENT_TEMPLATES` key map; `load_template(key)` / `template_path(key)` |
| `config_builder.py` | `build_config(template, overrides)` — deep-copy + whitelisted overrides; `copy_strategy`/`acquisition_layout` are template-locked |
| `scope.py` | `resolve_scope(key, path)` → `(staging_dir, pattern)` (single acquisition vs study vs batch root) |
| `preview.py` | `preview_batch(cfg, nas_root)` → `PreviewResult` (read-only acq_id/project/link replication) |
| `runner.py` | `run(cfg, nas_root, …, log_callback=…)` — wraps `ingest_raw.run_batch`, routes log, stamps recipe path |
| `env.py` | `resolve_nas_root` / `validate_nas_root` (fail-fast: needs `registries/`); `ftp_creds_present` |
| `_loader.py` | the non-colliding package loader described above |
