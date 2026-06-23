#!/usr/bin/env python3
"""Tests for tools/operator/collisions.py -- no NAS, no DB. Run: python tools/test_collisions.py"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "operator"))
import collisions  # noqa: E402

_fail = 0


def check(cond, msg):
    global _fail
    print(f"  {'ok:  ' if cond else 'FAIL:'} {msg}")
    if not cond:
        _fail += 1


def case(acq, link, hint):
    """Build a minimal case dict shaped like the GUI's _case_to_dict output."""
    return {"acq_id": acq, "link_filename": link,
            "registry_resolved": {"project_hint": hint}}


print("in-batch collisions:")
# Two acquisitions, same project + same link name -> collision.
cs = [case("ACQ-1", "MRI_27", "ae-biomegune-0424"),
      case("ACQ-2", "MRI_27", "ae-biomegune-0424")]
cols = collisions.find_link_collisions(cs)
check(len(cols) == 1, "one collision group for two identical (hint, link)")
check(cols and cols[0]["acq_ids"] == ["ACQ-1", "ACQ-2"], "both acq_ids reported, sorted")

# Same link name but DIFFERENT projects -> NOT a collision (different folders).
cs = [case("ACQ-1", "MRI_27", "ae-biomegune-0424"),
      case("ACQ-2", "MRI_27", "ae-biomegune-0423")]
check(collisions.find_link_collisions(cs) == [], "same link in different projects is not a collision")

# Unique link names in one project -> no collision.
cs = [case("ACQ-1", "MRI_m17_29", "p"), case("ACQ-2", "MRI_m18_29", "p")]
check(collisions.find_link_collisions(cs) == [], "distinct link names do not collide")

# No project (blank hint) -> no link -> never a collision even with equal names.
cs = [case("ACQ-1", "MRI_27", ""), case("ACQ-2", "MRI_27", "")]
check(collisions.find_link_collisions(cs) == [], "blank project_hint -> skipped (no link)")

# Blank link name -> skipped.
cs = [case("ACQ-1", "", "p"), case("ACQ-2", "", "p")]
check(collisions.find_link_collisions(cs) == [], "blank link name -> skipped")

# Three-way collision.
cs = [case("ACQ-3", "X", "p"), case("ACQ-1", "X", "p"), case("ACQ-2", "X", "p")]
cols = collisions.find_link_collisions(cs)
check(cols and cols[0]["acq_ids"] == ["ACQ-1", "ACQ-2", "ACQ-3"], "3-way collision, acq_ids sorted")

print("on-NAS existing-target check:")
with tempfile.TemporaryDirectory() as nas:
    # Pre-create an existing link target for hint 'p0424', link 'MRI_existing'.
    linkdir = os.path.join(nas, "projects", "proj-p0424", "raw_linked")
    os.makedirs(linkdir)
    open(os.path.join(linkdir, "MRI_existing"), "w").close()

    cs = [case("ACQ-9", "MRI_existing", "p0424"),   # collides with the pre-made file
          case("ACQ-8", "MRI_brand_new", "p0424")]  # does not exist yet
    hits = collisions.find_existing_link_targets(cs, nas)
    check(len(hits) == 1, "exactly one existing-target hit")
    check(hits and hits[0]["acq_id"] == "ACQ-9", "the right acq flagged as overwriting")
    check(collisions.find_existing_link_targets(cs, "") == [], "empty nas_root -> no hits, no crash")

print()
if _fail:
    print(f"{_fail} CHECK(S) FAILED")
    sys.exit(1)
print("ALL COLLISION CHECKS PASSED")
