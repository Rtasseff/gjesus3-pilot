#!/usr/bin/env python3
"""test_stage_ni_gnuclear.py — staging the NI sync onto gnuclear from git objects.

Run:  python tools/operator/test_stage_ni_gnuclear.py

Stages every target from HEAD into a temporary "gnuclear" and checks what researchers and the Mac
depend on: the staged code is byte-identical to the commit, the launchers keep LF line endings, a
re-run writes nothing, a damaged file is restored, and the test kit reads only registry headers
and refuses to overwrite an existing kit. Reads the repo; never touches S: or J:.
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage_ni_gnuclear as st  # noqa: E402

_checks = [0, 0]


def check(cond, label):
    _checks[0] += 1
    if cond:
        print(f"  ok   {label}")
    else:
        _checks[1] += 1
        print(f"  FAIL {label}")


def read(path):
    with open(path, "rb") as f:
        return f.read()


def main():
    tmp = tempfile.mkdtemp(prefix="stage_ni_")
    try:
        sha = st.git("rev-parse", "--short", "HEAD").decode().strip()
        base = os.path.join(tmp, "2026", "Jesus")
        common = ["--ref", "HEAD", "--gnuclear", tmp, "--no-fetch"]

        print("production")
        check(st.main(["production", *common]) == 0, "stages with no mismatch")
        prod = os.path.join(base, "_gjesus3_sync")
        n_tools = len(st.tree_files("HEAD", "tools"))
        staged = sum(len(fs) for _r, _d, fs in os.walk(prod))
        check(staged == n_tools + 3, f"tools/ plus ni-ingest, the guide, VERSION.txt ({staged} vs {n_tools}+3)")
        git_copy = subprocess.check_output(["git", "-C", st.REPO, "show", "HEAD:tools/operator/ni_ingest.py"])
        check(read(os.path.join(prod, "tools", "operator", "ni_ingest.py")) == git_copy,
              "staged code is byte-identical to the commit")
        check(b"\r\n" not in read(os.path.join(prod, "ni-ingest")), "launcher keeps LF line endings")
        check(f"commit {sha} (HEAD)".encode() in read(os.path.join(prod, "VERSION.txt")),
              "VERSION.txt names the commit")
        plan, dirs = st.plan_production("HEAD", sha, None)
        check(st.stage(prod, plan, dirs)[1] == 0, "a re-run writes nothing")
        with open(os.path.join(prod, "tools", "operator", "ni_ingest.py"), "ab") as f:
            f.write(b"# local edit\n")
        _n, written, bad = st.stage(prod, plan, dirs)
        check(written == 1 and not bad, "a changed file is restored, and only that one")
        check(not any(f.endswith(".partial") for _r, _d, fs in os.walk(prod) for f in fs),
              "no .partial files left behind")

        print("mount-kit")
        check(st.main(["mount-kit", *common]) == 0, "stages with no mismatch")
        kit = os.path.join(base, "Ryan", "gjesus3-mount")
        check(sorted(os.listdir(kit)) == ["README.txt", "gjesus3-mount.py", "gjesus3.conf", "setup.sh", "undo.sh"],
              f"the four kit files and a README ({sorted(os.listdir(kit))})")
        check(read(os.path.join(kit, "setup.sh")) == subprocess.check_output(
            ["git", "-C", st.REPO, "show", "HEAD:tools/operator/ni_mac/gjesus3_mount_setup.sh"]),
            "setup.sh is gjesus3_mount_setup.sh at the commit")
        check(f"at commit {sha}".encode() in read(os.path.join(kit, "README.txt")), "README names the commit")

        print("tunnel-card")
        check(st.main(["tunnel-card", *common]) == 0, "stages with no mismatch")
        card = os.path.join(base, "Ryan", "tunnel")
        check(sorted(os.listdir(card)) == ["README.txt", "eus.biomagune.mfb.tunnel.plist", "tunnel.txt"],
              "the card and the plist sit together (step 7b copies the plist from the card's folder)")

        print("test-kit")
        regs = os.path.join(tmp, "registries")
        os.makedirs(regs)
        with open(os.path.join(regs, "registry_raw.csv"), "wb") as f:
            f.write(b"acq_id,original_name\nACQ-REAL-ROW,should-not-be-copied\n")
        with open(os.path.join(regs, "notes.txt"), "wb") as f:
            f.write(b"not a registry\n")
        check(st.main(["test-kit", *common, "--registries", regs]) == 0, "stages with no mismatch")
        tk = os.path.join(base, "Ryan", "ni-sync-test")
        check(read(os.path.join(tk, "nas3", "registries", "registry_raw.csv")) == b"acq_id,original_name\n",
              "scratch registry holds the header only, no production rows")
        check(os.listdir(os.path.join(tk, "nas3", "registries")) == ["registry_raw.csv"], "only CSVs are copied")
        check(os.path.isdir(os.path.join(tk, "nas3", "raw")) and os.path.isdir(os.path.join(tk, "nas3", "projects")),
              "scratch raw/ and projects/ exist")
        check(b"nas3" in read(os.path.join(tk, "ni-ingest")), "the kit launcher is the one pinned to nas3")
        check(os.path.isfile(os.path.join(tk, "box", "ryan", "1207", "260212", "0324_m61",
                                          "20260212130722_CT", "recon_1", "img_1.dcm")), "synthetic box is there")
        check(st.main(["test-kit", *common, "--registries", regs]) == 2, "refuses a kit folder that is not empty")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    total, failed = _checks
    print(f"\n{total - failed}/{total} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
