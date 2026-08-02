#!/usr/bin/env python3
"""Tests for the project reference model — no NAS, no DB.

Covers the contract in 05_PROJECTS "Project reference model":
  name rules (space->hyphen, FS-safety), folder == name verbatim,
  case-insensitive resolve that canonicalizes casing, auto-create preserving
  the operator's casing, and the hard cut on the old `project_hint` key.

Run: python tools/test_project_naming.py
"""

import csv
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest import project_naming, linker, registry, resolver  # noqa: E402
import create_project  # noqa: E402

_fail = 0


def check(cond, msg):
    global _fail
    print(f"  {'ok:  ' if cond else 'FAIL:'} {msg}")
    if not cond:
        _fail += 1


print("name normalization (spaces -> hyphens, casing preserved):")
n = project_naming.normalize_project_name
check(n("My Project") == "My-Project", "single space -> hyphen")
check(n("  padded  name  ") == "padded-name", "trimmed; internal run -> one hyphen")
check(n("AE-biomaGUNE-1123") == "AE-biomaGUNE-1123", "already-canonical name untouched")
check(n("Mixed\tCase\nName") == "Mixed-Case-Name", "tabs/newlines are whitespace too")
check(n("") == "" and n(None) == "", "empty / None -> empty")

print("name validation (it becomes a folder):")
v = project_naming.validate_project_name
check(v("AE-biomaGUNE-1123") == [], "canonical name is valid")
check(v("laura-tholt") == [], "person/topic slug is valid")
check(v("Ainhize_2026.batch") == [], "underscores and dots are allowed")
check(v("") and "empty" in v("")[0].lower(), "empty name rejected")
for bad in ["a/b", "a\\b", "a:b", "a*b", "a?b", 'a"b', "a<b", "a>b", "a|b"]:
    if not v(bad):
        check(False, f"illegal char in {bad!r} should be rejected")
check(all(v(b) for b in ["a/b", "a\\b", "a:b", "a*b", "a?b", 'a"b', "a<b", "a>b", "a|b"]),
      "every Windows-illegal character is rejected")
check(v(" leading") and v("trailing ") and v("trailing."),
      "leading/trailing space or dot rejected")
check(v("x" * 61) and not v("x" * 60), "max length 60 enforced")

print("folder derivation (folder == name, verbatim):")
check(project_naming.folder_name("AE-biomaGUNE-1123") == "AE-biomaGUNE-1123",
      "folder is the name, no prefix, no lowercasing")
check(project_naming.folder_location("AE-biomaGUNE-1123") == "/projects/AE-biomaGUNE-1123/",
      "folder_location is /projects/<name>/")

print("resolve_project (case-insensitive; canonicalizes):")
with tempfile.TemporaryDirectory() as d:
    reg_path = os.path.join(d, "registry_projects.csv")
    with open(reg_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(create_project.PROJECT_REGISTRY_FIELDS)
        w.writerow(["PROJ-0014", "AE-biomaGUNE-1123", "", "MBC", "", "active", "",
                    "/projects/AE-biomaGUNE-1123/", ""])
    pid, name, folder = linker.resolve_project(reg_path, "AE-biomaGUNE-1123")
    check((pid, name, folder) == ("PROJ-0014", "AE-biomaGUNE-1123",
                                  "/projects/AE-biomaGUNE-1123/"),
          "exact name -> (id, name, folder)")
    pid, name, _ = linker.resolve_project(reg_path, "ae-biomagune-1123")
    check(pid == "PROJ-0014" and name == "AE-biomaGUNE-1123",
          "lowercase spelling resolves AND canonicalizes the casing")
    pid, name, _ = linker.resolve_project(reg_path, "PROJ-0014")
    check(pid == "PROJ-0014" and name == "AE-biomaGUNE-1123",
          "PROJ-id resolves and yields the human name")
    check(linker.resolve_project(reg_path, "nope") == (None, None, None),
          "no match -> (None, None, None)")
    check(linker.resolve_project(reg_path, "") == (None, None, None),
          "empty reference -> (None, None, None)")

print("create_project (single construction site):")
with tempfile.TemporaryDirectory() as d:
    pid, ok = create_project.create_project(
        "Ainhize Confocal 2026", "test", "AU", d, notes="")
    check(ok and pid == "PROJ-0001", "created with a generated id")
    folder = os.path.join(d, "projects", "Ainhize-Confocal-2026")
    check(os.path.isdir(folder), "folder == the space-normalized name, verbatim")
    check(os.path.isdir(os.path.join(folder, "raw_linked")), "raw_linked/ created")
    rows = create_project.read_project_registry(
        os.path.join(d, "registries", "registry_projects.csv"))
    check(rows[0]["name"] == "Ainhize-Confocal-2026", "registry 'name' column carries the name")
    check(rows[0]["folder_location"] == "/projects/Ainhize-Confocal-2026/",
          "folder_location matches the name")
    yaml_text = open(os.path.join(folder, "_project.yaml"), encoding="utf-8").read()
    check("name: Ainhize-Confocal-2026" in yaml_text, "_project.yaml uses the `name:` key")
    # Uniqueness is case-insensitive: the FS can't hold both spellings.
    _, ok2 = create_project.create_project("ainhize-confocal-2026", "dup", "AU", d)
    check(not ok2, "a case-different duplicate name is refused")
    # An unusable name never reaches the filesystem.
    _, ok3 = create_project.create_project("bad/name", "x", "AU", d)
    check(not ok3, "an illegal name is refused")

print("schema mirror + the hard cut on the old key:")
check("project_name" in resolver.USER_CONTROLLABLE_COLUMNS,
      "registry.project_name is the operator input key")
check("project_hint" not in resolver.USER_CONTROLLABLE_COLUMNS,
      "registry.project_hint is NOT accepted (hard cut, no alias)")
errs = resolver.validate_registry_block({
    "instrument": "ZWSI", "data_ecosystem": "MICROSCOPY",
    "researcher": "MBC", "data_source": "internal",
    "project_hint": "AE-biomaGUNE-1123",
})
check(any("project_hint" in e for e in errs),
      "a stale config using project_hint fails loudly")
check(any("project_name" in e for e in errs),
      "...and the error lists project_name among the allowed keys")
check("project_id" in registry.REGISTRY_FIELDS and "project_hint" not in registry.REGISTRY_FIELDS,
      "the STORED column is project_id (it holds PROJ-ids)")
check("project_name" not in registry.REGISTRY_FIELDS,
      "no project_name column — the stored value is an id, not a name")
check("project_name" in resolver.LINK_FILENAME_REGISTRY_FIELDS
      and "project_id" in resolver.LINK_FILENAME_REGISTRY_FIELDS,
      "link_filename offers both ${project_name} and ${project_id}")

print()
if _fail:
    print(f"{_fail} CHECK(S) FAILED")
    sys.exit(1)
print("ALL PROJECT-NAMING CHECKS PASSED")
