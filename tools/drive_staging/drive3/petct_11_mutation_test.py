"""Mutation test for the discovery fallback: break the fix in three ways, run tools/test_ni_flat.py, expect FAIL.

The worktree file is restored byte-for-byte after each mutant (and in a finally).
"""
import os
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))      # the repository root (tools/drive_staging/drive3/<this>)
F = os.path.join(WT, "tools", "ni_gnuclear_discover.py")
BAK = r"D:\projects\gjesus3\drive3_streams\petct\scripts\_main_copy\ni_gnuclear_discover_branch.bak"

MUTANTS = {
    "no fallback": ("elif valid_codes is not None and not project and subject and not p.get(\"phantom\"):",
                    "elif False:"),
    "walk includes the subject folder": ("rec = recover_project(mid[:k], valid_codes) if k > 0 else None",
                                         "rec = recover_project(mid[:k + 1], valid_codes) if k >= 0 else None"),
    "walk includes year/group/researcher": ("rec = recover_project(mid[:k], valid_codes) if k > 0 else None",
                                            "rec = recover_project(rel.split('/')[:-1][:researcher_idx + 1 + k], valid_codes)"),
    "phantoms recovered too": ("and not project and subject and not p.get(\"phantom\"):",
                               "and not project and subject:"),
}


def run():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.path.join(WT, "tools"))
    r = subprocess.run([sys.executable, os.path.join(WT, "tools", "test_ni_flat.py")], cwd=WT, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    last = [l for l in r.stdout.splitlines() if "checks passed" in l]
    fails = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("FAIL")]
    return r.returncode, (last[-1] if last else "?"), fails


def main():
    shutil.copyfile(F, BAK)
    orig = open(F, "rb").read()
    try:
        rc, line, _ = run()
        print(f"unmutated: rc={rc} {line}")
        for name, (a, b) in MUTANTS.items():
            src = orig.decode("utf-8")
            assert src.count(a) == 1, (name, src.count(a))
            open(F, "wb").write(src.replace(a, b).encode("utf-8"))
            rc, line, fails = run()
            print(f"mutant '{name}': rc={rc} {line} -> {'KILLED' if rc else 'SURVIVED'}")
            for f in fails[:4]:
                print("      ", f)
            open(F, "wb").write(orig)
    finally:
        open(F, "wb").write(orig)
    assert open(F, "rb").read() == orig
    print("restored:", open(F, "rb").read() == open(BAK, "rb").read())


if __name__ == "__main__":
    main()
