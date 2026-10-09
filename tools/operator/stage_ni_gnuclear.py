#!/usr/bin/env python3
"""stage_ni_gnuclear.py — copy the NI live sync onto gnuclear for the Molecubes Mac (Data Office tool).

The Mac cannot reach the repo: it runs what the Data Office stages on gnuclear. This tool does
that staging from a git commit (default origin/main, fetched first). It reads the files straight
from git objects, so it works from any checkout and never touches main's working copy.

Targets, all under <gnuclear>\\2026\\Jesus\\:

  production   _gjesus3_sync\\          the researchers' copy: tools\\, the ni-ingest launcher,
                                       NI_SYNC_GUIDE.html, VERSION.txt. Restage after every merge
                                       into main that touches tools/.
  mount-kit    Ryan\\gjesus3-mount\\     the interim gjesus3 mount kit (tools/operator/ni_mac/).
  tunnel-card  Ryan\\tunnel\\            the tunnel field card and its LaunchAgent plist
                                       (equipment/nuclear-imaging/tunnel/), to use at the Mac.
  test-kit     Ryan\\ni-sync-test\\      tools\\, a launcher pinned to a scratch gjesus3 (nas3\\,
                                       registry headers only) and a synthetic box. Refuses a
                                       folder that is not empty; delete the old kit first.

It writes only the files it names, leaves unchanged files alone, deletes nothing, and compares
every staged file with its git blob afterwards. Ryan\\ is the Data Office's free write zone on
gnuclear (the Molecubes Mac rules); _gjesus3_sync\\ is the code home Ryan chose on 2026-10-08.

    python tools/operator/stage_ni_gnuclear.py production
    python tools/operator/stage_ni_gnuclear.py mount-kit --ref <commit>
"""
import argparse
import datetime
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GNUCLEAR = "S:" + os.sep + "gnuclear"
GROUP = ("2026", "Jesus")
PROD_REGISTRIES = os.path.join("J:" + os.sep, "gjesus3-data", "registries")
TARGETS = {
    "production": ("_gjesus3_sync",),
    "mount-kit": ("Ryan", "gjesus3-mount"),
    "tunnel-card": ("Ryan", "tunnel"),
    "test-kit": ("Ryan", "ni-sync-test"),
}
SKIP_SUFFIXES = (".pyc", ".xlsx", ".docx")
MAC_KIT = "tools/operator/ni_mac/"
TUNNEL = "equipment/nuclear-imaging/tunnel/"


def git(*args):
    return subprocess.check_output(["git", "-C", REPO, *args])


def tree_files(ref, prefix):
    """{repo path: blob sha} for every file under `prefix` at `ref`, minus caches and office files."""
    files = {}
    for entry in filter(None, git("ls-tree", "-r", "-z", ref, "--", prefix).decode("utf-8").split("\0")):
        meta, path = entry.split("\t", 1)
        _mode, kind, sha = meta.split()
        if kind == "blob" and "/__pycache__/" not in path and not path.endswith(SKIP_SUFFIXES):
            files[path] = sha
    return files


def read_blobs(shas):
    """{sha: bytes}, read in one `git cat-file --batch` pass."""
    uniq = list(dict.fromkeys(shas))
    out = subprocess.run(["git", "-C", REPO, "cat-file", "--batch"], check=True, stdout=subprocess.PIPE,
                         input="".join(s + "\n" for s in uniq).encode()).stdout
    blobs, pos = {}, 0
    for sha in uniq:
        nl = out.index(b"\n", pos)
        head = out[pos:nl].split()
        if len(head) != 3 or head[1] != b"blob":
            raise RuntimeError(f"git cat-file: unexpected header {out[pos:nl]!r} for {sha}")
        start = nl + 1
        blobs[sha] = out[start:start + int(head[2])]
        pos = start + int(head[2]) + 1
    return blobs


def files_at(ref, prefix):
    """{repo path: bytes} under `prefix` at `ref`."""
    files = tree_files(ref, prefix)
    blobs = read_blobs(files.values())
    return {path: blobs[sha] for path, sha in files.items()}


def plan_production(ref, sha, opts):
    tools = files_at(ref, "tools")
    plan = dict(tools)
    plan["ni-ingest"] = tools["tools/operator/ni-ingest.sh"]
    plan["NI_SYNC_GUIDE.html"] = tools["tools/operator/NI_SYNC_GUIDE.html"]
    plan["VERSION.txt"] = (
        f"NI live sync for researchers. Data Office, staged from commit {sha} ({ref}) "
        f"on {datetime.date.today().isoformat()}.\n"
        "Do not edit files here; the data office restages from the repo.\n"
        "How to use it: NI_SYNC_GUIDE.html in this folder.\n").encode()
    return plan, []


MOUNT_NAMES = {"gjesus3_mount_setup.sh": "setup.sh", "gjesus3_mount_undo.sh": "undo.sh",
               "gjesus3.conf": "gjesus3.conf", "gjesus3_mount_helper.py": "gjesus3-mount.py"}


def plan_mount_kit(ref, sha, opts):
    kit = files_at(ref, MAC_KIT)
    plan = {dst: kit[MAC_KIT + src] for src, dst in MOUNT_NAMES.items()}
    plan["README.txt"] = f"""Keep gjesus3 mounted on the NI Mac -- INTERIM, Data Office login (Ryan, 2026-10-08)

Until Box A pulls NI data through the tunnel, the Mac's sync needs gjesus3 mounted.
Run by Ryan in his own ssh session on the Mac:

    bash /Volumes/gnuclear/2026/Jesus/Ryan/gjesus3-mount/setup.sh

It asks for the molecubes account password (to unlock the keychain over ssh), then your
gjesus3 password (saved in that keychain only). It mounts gjesus3 at ~/.gjesus3 (hidden from
Finder) and installs gjesus3-mount.py (the helper that does the mounting, one MacMounter copy
at a time) and gjesus3.conf into ~/.macmounter/, so MacMounter re-mounts it when it drops.

Undo everything:   bash /Volumes/gnuclear/2026/Jesus/Ryan/gjesus3-mount/undo.sh
Source of these files: repo tools/operator/ni_mac/ at commit {sha}.
""".encode()
    return plan, []


def plan_tunnel_card(ref, sha, opts):
    card = files_at(ref, TUNNEL)
    plan = {name: card[TUNNEL + name] for name in ("tunnel.txt", "eus.biomagune.mfb.tunnel.plist")}
    plan["README.txt"] = f"""Reverse SSH tunnel at the Molecubes Mac: the field card and its LaunchAgent.

tunnel.txt                       the field card (rev4): install the Mac's half of the tunnel
eus.biomagune.mfb.tunnel.plist   the LaunchAgent the card's step 7 installs

Keep the two together: step 7b copies the plist from the folder the card is in.
Needed only to re-install the tunnel from scratch; moving it to Box A needs no visit.
Source: repo equipment/nuclear-imaging/tunnel/ at commit {sha}. Background:
equipment/nuclear-imaging/live_machine_remote_access.md.
""".encode()
    return plan, []


def _synthetic_session(rel, recons):
    """A tiny fake Mac acquisition (text files named .dcm, not real scans)."""
    plan = {f"box/ryan/{rel}/protocol.txt": b"Scan bed position from 0 to 100\n"}
    for i in recons:
        plan[f"box/ryan/{rel}/recon_{i}/img_{i}.dcm"] = f"SYNTHETIC-{rel}-{i}".encode()
    return plan


def plan_test_kit(ref, sha, opts):
    plan = files_at(ref, "tools")
    plan["ni-ingest"] = plan[MAC_KIT + "ni-ingest-testkit.sh"]
    # Scratch gjesus3: the first line (header) of each registry CSV, nothing else is read.
    for name in sorted(os.listdir(opts.registries)):
        if name.lower().endswith(".csv") and os.path.isfile(os.path.join(opts.registries, name)):
            with open(os.path.join(opts.registries, name), "rb") as f:
                plan[f"nas3/registries/{name}"] = f.readline()
    plan.update(_synthetic_session("1207/260212/0324_m61/20260212130722_CT", [0, 1]))
    plan.update(_synthetic_session("1207/260213/0324_m62/20260213101500_CT", [0]))
    plan["README.txt"] = f"""NI sync test kit (Data Office) -- safe to delete as a whole.

ni-ingest   the launcher, pinned to nas3/ below: a test types exactly what a researcher
            would and cannot reach the real gjesus3
tools/      the sync code, repo commit {sha}
nas3/       a SCRATCH gjesus3: registry headers only. Test runs write here, never production.
box/ryan/   a SYNTHETIC Mac data folder (tiny text files named .dcm, not real scans)

Everything a test run writes lands in this folder or in ni_corrections_ryan.csv one level up.
""".encode()
    return plan, ["nas3/raw", "nas3/projects"]


PLANNERS = {"production": plan_production, "mount-kit": plan_mount_kit,
            "tunnel-card": plan_tunnel_card, "test-kit": plan_test_kit}


def stage(dest, plan, dirs=()):
    """Write each planned file whose bytes differ (via .partial + rename), then re-check them all.

    Returns (checked, written, mismatched paths)."""
    written = 0
    for rel, data in plan.items():
        dst = os.path.join(dest, *rel.split("/"))
        if os.path.isfile(dst):
            with open(dst, "rb") as f:
                if f.read() == data:
                    continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst + ".partial", "wb") as f:
            f.write(data)
        os.replace(dst + ".partial", dst)
        written += 1
    for d in dirs:
        os.makedirs(os.path.join(dest, *d.split("/")), exist_ok=True)
    bad = []
    for rel, data in plan.items():
        with open(os.path.join(dest, *rel.split("/")), "rb") as f:
            if f.read() != data:
                bad.append(rel)
    return len(plan), written, bad


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                epilog=__doc__.split("\n\n", 2)[2],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("target", choices=sorted(TARGETS))
    p.add_argument("--ref", default="origin/main", help="commit to stage from (default: origin/main)")
    p.add_argument("--gnuclear", default=GNUCLEAR, help=f"gnuclear root (default: {GNUCLEAR})")
    p.add_argument("--registries", default=PROD_REGISTRIES,
                   help="test-kit only: where to read the registry headers from (first line of each CSV)")
    p.add_argument("--no-fetch", action="store_true", help="do not fetch origin before an origin/ ref")
    opts = p.parse_args(argv)

    if opts.ref.startswith("origin/") and not opts.no_fetch:
        git("fetch", "-q", "origin")
    sha = git("rev-parse", "--short", opts.ref).decode().strip()
    dest = os.path.join(opts.gnuclear, *GROUP, *TARGETS[opts.target])
    if opts.target == "test-kit" and os.path.isdir(dest) and os.listdir(dest):
        print(f"refusing: {dest} exists and is not empty; delete the old kit first", file=sys.stderr)
        return 2
    plan, dirs = PLANNERS[opts.target](opts.ref, sha, opts)
    for rel, data in plan.items():
        if rel.endswith(".sh") or rel == "ni-ingest":
            assert b"\r\n" not in data, f"{rel} has CRLF line endings; bash on the Mac would break"
    checked, written, bad = stage(dest, plan, dirs)
    print(f"{opts.target}: {checked} files checked, {written} written, from {sha} into {dest}; "
          f"mismatches after copy: {len(bad)}")
    for rel in bad[:10]:
        print(f"  MISMATCH {rel}", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
