"""Project-manager core — the researcher-facing counterpart to `tools/operator/`.

Everything the Project Manager GUI does that is not HTTP lives here, so the
Flask layer stays a thin front-end and the same operations can be driven from a
script or, later, from the RDM server that replaces the frozen exes.

  projects.py      list / read / update projects (registry + `_project.yaml`)
  raw_import.py    add existing /raw/ acquisitions to a project (hard links)
  local_import.py  copy files from local or mounted storage into a project

The package name is deliberately NOT `operator` — that directory collides with
the stdlib module and needs a loader shim (see tools/operator/IMPORT_CONTRACT.md).
`manager` collides with nothing, so it is imported normally.
"""
