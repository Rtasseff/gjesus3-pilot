"""Safe importer for this package, working around the stdlib `operator` clash.

This package's directory is named `operator` (mandated by the build plan), which
collides with the Python standard-library `operator` module. You therefore must
NOT import it under the bare name `operator` — doing so either shadows stdlib
`operator` (breaking `collections`/`dataclasses`/etc. internals) or resolves to
stdlib `operator` (which has none of our submodules).

This module loads the package under a NON-colliding alias and returns it.
Intra-package imports are all relative (`from . import ...`), so the package
works under any alias.

Usage from a front-end / test that lives OUTSIDE the package::

    import os, importlib.util, sys
    _here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        "gj_operator_loader", os.path.join(_here, "operator", "_loader.py"))
    _l = importlib.util.module_from_spec(spec); spec.loader.exec_module(_l)
    op = _l.load()                      # the package, aliased as "gj_op_core"
    op.preview.preview_batch(...)

Or, the one-liner convenience::

    from operator._loader import load   # ONLY works if launched via `python -m`
                                        # from inside tools/ with the package on
                                        # a relative-import footing — prefer the
                                        # spec form above for standalone scripts.
"""

import importlib
import importlib.machinery
import importlib.util
import os
import sys

# Public alias the package is registered under in sys.modules.
ALIAS = "gj_op_core"

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))


def load():
    """Import (or return the already-imported) operator package under ALIAS.

    Returns the package module object; its submodules are accessible as
    `pkg.templates`, `pkg.config_builder`, `pkg.scope`, `pkg.preview`,
    `pkg.runner`, `pkg.env`.

    The package directory deliberately ships NO importable-as-top-level
    `__init__.py` (a regular `operator` package on sys.path would shadow the
    stdlib `operator` module and break any tool run from tools/). We therefore
    register the package as a synthetic namespace-style package here: an empty
    module object with `__path__` set to the package dir, under a non-colliding
    alias. Relative imports inside the submodules then resolve normally.
    """
    if ALIAS in sys.modules:
        return sys.modules[ALIAS]

    init_py = os.path.join(_PKG_DIR, "__init__.py")
    if os.path.isfile(init_py):
        spec = importlib.util.spec_from_file_location(
            ALIAS, init_py, submodule_search_locations=[_PKG_DIR]
        )
        pkg = importlib.util.module_from_spec(spec)
        sys.modules[ALIAS] = pkg
        spec.loader.exec_module(pkg)
    else:
        # Synthetic package: no __init__.py on disk (kept absent so the dir is
        # never picked up as top-level `operator`). Build a bare package module
        # whose __path__ points at the package dir so submodule imports work.
        spec = importlib.machinery.ModuleSpec(
            ALIAS, loader=None, is_package=True
        )
        spec.submodule_search_locations = [_PKG_DIR]
        pkg = importlib.util.module_from_spec(spec)
        pkg.__path__ = [_PKG_DIR]
        sys.modules[ALIAS] = pkg

    # Eagerly bind the public submodules so callers can do `pkg.preview` etc.
    # without a separate import (they import each other relatively anyway).
    for sub in ("templates", "config_builder", "scope", "preview",
                "runner", "env", "metadata_prompt"):
        full = f"{ALIAS}.{sub}"
        if full not in sys.modules:
            importlib.import_module(full)
        setattr(pkg, sub, sys.modules[full])
    return pkg
