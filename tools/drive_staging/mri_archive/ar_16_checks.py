"""Stream AR: the small read-only checks the production script (ar_16_production.sh) calls. Exit 0 = as expected.

    python ar_16_checks.py validator <validator output> [--save-baseline <file>] [--expect-pending-from <file> --plus N]
                                     [--allow-missing-folders]   (the rehearsal root only: production's rows have no /raw/)
    python ar_16_checks.py snapshot <nas> <file>         # MRI/XMRI acq_ids + every registry file's SHA-256
    python ar_16_checks.py mri-unchanged <nas> <file>    # no MRI/XMRI row of ANOTHER writer added or removed since
    python ar_16_checks.py plan <plan summary>           # the LIVE CHECK lines of ar_05_plan.py as expected
    python ar_16_checks.py cases <batch>                 # print the case-table row count
    python ar_16_checks.py rows <nas> [<config>]         # print the registry row count (of one ingest config)
    python ar_16_checks.py run-log <log> <expected> <nas> <config>
                                                         # Failed 0, and the registry holds exactly <expected> rows of it
    python ar_16_checks.py project-active <nas> <name>
    python ar_16_checks.py claims <dry-run output> <sessions> <acquisitions>
    python ar_16_checks.py same-registries <nas> <snapshot>   # every registry file unchanged since the pre-flight
    python ar_16_checks.py rehearsal-reopen <rehearsal root> <project>   # REHEARSAL ONLY: status -> active
"""
import collections
import csv
import hashlib
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ar_common as C  # noqa: E402


def reg(nas):
    with io.open(os.path.join(nas, "registries", "registry_raw.csv"), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def say(ok, msg):
    print(f"{'OK  ' if ok else 'STOP'} {msg}")
    return 0 if ok else 1


def validator(a):
    text = open(a[0], encoding="utf-8", errors="replace").read()
    m = re.search(r"operator awaiting claim \(pending-claim\):\s*([\d,]+)", text)
    pending = int(m.group(1).replace(",", "")) if m else None
    failed = re.search(r"validation FAILED", text)
    if failed and "--allow-missing-folders" in a:
        # the rehearsal root holds no /raw/ for production's own rows: those errors, and only those, are expected
        errs = [l for l in text.splitlines() if "ERROR" in l and "validation FAILED" not in l and "-- ERRORS (" not in l]
        failed = [l for l in errs if "acquisition folder not found on disk" not in l]
    ok = (not failed) and (re.search(r"validation OK", text) or "--allow-missing-folders" in a) and pending is not None
    if "--save-baseline" in a:
        open(a[a.index("--save-baseline") + 1], "w").write(f"{pending}\n")
    if "--expect-pending-from" in a:
        base = int(open(a[a.index("--expect-pending-from") + 1]).read().strip())
        plus = int(a[a.index("--plus") + 1])
        return say(ok and pending == base + plus, f"validator OK; pending-claim {pending} == {base} + {plus}")
    return say(bool(ok), f"validator {'OK' if ok else 'FAILED'}; pending-claim {pending}")


def snapshot(a):
    nas, path = a
    rows = reg(nas)
    ids = sorted(r["acq_id"] for r in rows if r["instrument"] in ("MRI", "XMRI"))
    regd = os.path.join(nas, "registries")
    fp = [f"{n} {hashlib.sha256(open(os.path.join(regd, n), 'rb').read()).hexdigest()}"
          for n in sorted(os.listdir(regd)) if os.path.isfile(os.path.join(regd, n))]
    open(path, "w", encoding="utf-8").write("\n".join([f"rows {len(rows)}", *fp, "MRI", *ids]) + "\n")
    return say(True, f"snapshot: {len(rows)} rows, {len(ids)} MRI/XMRI")


def mri_unchanged(a):
    nas, path = a
    lines = open(path, encoding="utf-8").read().splitlines()
    then = set(lines[lines.index("MRI") + 1:])
    rows = reg(nas)
    # this stream's own rows (a resumed write) are not "another writer"
    now = {r["acq_id"] for r in rows if r["instrument"] in ("MRI", "XMRI")
           and not r["ingest_config"].replace("\\", "/").startswith(C.CFG_DIR_REL + "/")}
    other = collections.Counter(r["instrument"] for r in rows if r["acq_id"] not in then and r["instrument"] not in ("MRI", "XMRI"))
    return say(now == then, f"MRI/XMRI rows unchanged since the pre-flight ({len(now)}); rows now {len(rows)} "
               f"(was {lines[0].split()[1]}); MRI added {len(now - then)}, removed {len(then - now)}")


def same_registries(a):
    """Every registry file byte-identical to the pre-flight snapshot (then the pre-flight's validator still stands)."""
    nas, path = a
    lines = open(path, encoding="utf-8").read().splitlines()
    then = dict(l.split(" ", 1) for l in lines[1:lines.index("MRI")])
    regd = os.path.join(nas, "registries")
    now = {n: hashlib.sha256(open(os.path.join(regd, n), "rb").read()).hexdigest()
           for n in sorted(os.listdir(regd)) if os.path.isfile(os.path.join(regd, n))}
    diff = sorted(n for n in set(then) | set(now) if then.get(n) != now.get(n))
    print(f"registry files changed since the pre-flight: {diff or 'none'}")
    return 0 if not diff else 1


def rehearsal_reopen(a):
    """REHEARSAL ONLY: what tools/reopen_project.py does to the project row (status active), on the D: rehearsal root,
    whose /raw/ is empty so the real tool cannot relink production's acquisitions there. Refuses any other root."""
    nas, name = a
    if os.path.abspath(nas).lower() != os.path.abspath(C.REH).lower():
        return say(False, f"rehearsal-reopen refuses {nas}: the rehearsal root only")
    sys.path.insert(0, os.path.join(C.WT, "tools"))
    from ingest import locking, projects_registry
    regd = os.path.join(nas, "registries")
    with io.open(os.path.join(regd, "registry_projects.csv"), encoding="utf-8-sig", newline="") as f:
        pid = [p["project_id"] for p in csv.DictReader(f) if p["name"] == name][0]
    with locking.registry_lock(regd):
        found, applied = projects_registry.update_row(os.path.join(regd, "registry_projects.csv"), pid,
                                                      {"status": "active"}, allowed=["status"])
    return say(found, f"rehearsal: {name} ({pid}) status set active {sorted(applied)}")


def plan(a):
    t = open(a[0], encoding="utf-8").read()
    want = [r"original_name \(or <study>__<exam>\) is in the registry now: 0\b",
            r"session id and day are in production \(expected 0\): 0 ",
            r"another session that day.*?: \{'A2': 12\} \[\]",
            r"already taken in production now: 0 \[\]",
            r"duplicated within the plan: 0 \[\]",
            r"dated 2026: 0\b"]
    bad = [w for w in want if not re.search(w, t)]
    return say(not bad, f"plan live checks: {len(want) - len(bad)} of {len(want)} as expected {bad}")


def cases(a):
    print(len(C.rows(os.path.join(C.CFG_DIR, f"cases_{a[0]}.csv"))))
    return 0


def rows(a):
    rs = reg(a[0])
    if len(a) > 1:
        rs = [r for r in rs if r["ingest_config"].replace("\\", "/") == a[1]]
    print(len(rs))
    return 0


def run_log(a):
    log, expected, nas, cfg = a[0], int(a[1]), a[2], a[3]
    t = open(log, encoding="utf-8", errors="replace").read()
    g = {k: int(m.group(1)) if (m := re.search(rf"^\s*{k}:\s+(\d+)", t, re.M)) else None for k in ("Total", "Success", "Failed")}
    have = sum(1 for r in reg(nas) if r["ingest_config"].replace("\\", "/") == cfg)
    ok = g["Failed"] == 0 and g["Total"] == g["Success"] and have == expected
    return say(ok, f"{os.path.basename(cfg)}: run {g}; rows of this config in the registry {have} (expected {expected})")


def project_active(a):
    with io.open(os.path.join(a[0], "registries", "registry_projects.csv"), encoding="utf-8-sig", newline="") as f:
        st = [p["status"] for p in csv.DictReader(f) if p["name"] == a[1]]
    return say(st == ["active"], f"{a[1]} status {st}")


def claims(a):
    t = open(a[0], encoding="utf-8", errors="replace").read()
    m = re.search(r"to append: ([\d,]+) sessions \(([\d,]+) acquisitions\)", t)
    got = (int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))) if m else None
    ok = got == (int(a[1]), int(a[2])) and "every existing cell unchanged" in t
    return say(ok, f"claims-append: {got} (expected {a[1]} sessions, {a[2]} acquisitions); existing cells unchanged "
               f"{'every existing cell unchanged' in t}")


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    sys.exit({"validator": validator, "snapshot": snapshot, "mri-unchanged": mri_unchanged, "plan": plan,
              "cases": cases, "rows": rows, "run-log": run_log, "project-active": project_active,
              "claims": claims, "same-registries": same_registries, "rehearsal-reopen": rehearsal_reopen}[cmd](args))
