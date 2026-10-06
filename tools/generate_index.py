#!/usr/bin/env python3
"""generate_index.py — write the self-contained, searchable HTML "Finder" for the
acquisition registry onto the NAS share. A researcher double-clicks it over SMB,
types a query (id / instrument / date / subject / region), and copies the path
straight to their data — zero install, no server, no Python on their side.

  # global index -> <nas>/registries/index.html
  python tools/generate_index.py --nas-root J:/gjesus3-data

  # + one scoped index in each project folder
  python tools/generate_index.py --nas-root J:/gjesus3-data --per-project

  # regenerate ONLY one project's scoped index (skips the global rebuild) — the
  # cheap path the GUI uses after an ingest to refresh just the touched project
  python tools/generate_index.py --nas-root J:/gjesus3-data --project PROJ-0011

  # preview locally first (writes nothing to the share)
  python tools/generate_index.py --nas-root J:/gjesus3-data --per-project --out ./_finder_preview

The page embeds its data inline (self-contained), so it works over file:// with
no fetch/CORS. The data path is shown as a COPYABLE UNC path (browsers block
file:// links opened from a file:// page — copy + paste into Explorer always
works). See tools/FINDER.md.
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_acq  # noqa: E402
from ingest import project_ids as pids  # noqa: E402  (the ;-separated project cell)

# The SMB share UNC works on any locked-down machine regardless of drive-letter
# mapping; override with --link-base if your share is reached differently.
# Must point at the *container* (the dir holding raw/ + registries/), because the
# canonical paths we join onto it are share-relative like "/raw/...". The old value
# (\\GJESUS3\gjesus3) omitted the gjesus3-data component and produced unresolvable
# paths.
DEFAULT_LINK_BASE = r"\\GJESUS3\gjesus3\gjesus3-data"


def _winpath(base, rel):
    """Join the share base + a share-relative path into a Windows UNC path."""
    rel = (rel or "").strip()
    if not rel:
        return ""
    return base.rstrip("/\\") + "\\" + rel.strip("/\\").replace("/", "\\")


def _payload(records, link_base, scope=None):
    """Curated per-record dict embedded in the page (display + search + paths).

    `scope` (per-project pages only): the `registry_projects.csv` entry for the
    project this page belongs to — ``{folder, name, owner, desc, status}``. An
    acquisition can now belong to SEVERAL projects (`project_id` is a `;`-list),
    so the project-scoped fields have to say WHICH project they mean. On a
    project page they mean *this* project; on the global index they fall back to
    the record's first project. The `project` column always shows the whole
    list — that an acquisition is shared is worth seeing.
    """
    scope = scope or {}
    out = []
    for r in records:
        raw = r.get("_raw_path", "")
        out.append({
            "acq": r.get("acq_id", ""),
            "date": (r.get("acquisition_datetime") or "")[:10],
            "instr": r.get("instrument", ""),
            "mod": r.get("modalities_in_study", ""),
            "sample": r.get("sample_id", ""),
            "subject": r.get("subject_ids", ""),
            "organism": r.get("sample_organism", ""),
            "region": r.get("anatomical_entity", ""),
            "project": r.get("project_id", ""),
            "researcher": r.get("researcher", ""),
            "size": r.get("file_size_mb", ""),
            "sample_type": r.get("sample_type", ""),
            "proj_short": r.get("_project_name", ""),
            "proj_owner": scope.get("owner") or r.get("_project_owner", ""),
            "proj_desc": scope.get("desc") or r.get("_project_desc", ""),
            "path": _winpath(link_base, raw),
            "proj_path": _winpath(
                link_base, scope.get("folder") or r.get("_project_folder", "")),
            "meta_path": _winpath(link_base, raw.rstrip("/") + "/metadata.json") if raw else "",
            "s": r.get("_search", ""),
            # detail-only extras:
            "operator": r.get("operator", ""),
            "session": r.get("session_id", ""),
            "format": r.get("file_format", ""),
            "count": r.get("file_count", ""),
            "orig": r.get("original_name", ""),
            "notes": r.get("notes", ""),
        })
    return out


# The page: inline CSS + JS, data injected at __DATA__. Built with str.replace so
# the CSS/JS braces need no escaping.
_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  body{font-family:system-ui,"Segoe UI",Arial,sans-serif;margin:0;color:#1a1a1a;background:#f6f7f9}
  header{background:#10403b;color:#fff;padding:12px 18px}
  header h1{margin:0;font-size:17px}
  header .meta{font-size:12px;opacity:.85;margin-top:3px}
  .controls{position:sticky;top:0;background:#fff;border-bottom:1px solid #ddd;padding:10px 18px;
            display:flex;gap:10px;flex-wrap:wrap;align-items:center;z-index:2}
  .controls input,.controls select{font-size:14px;padding:6px 8px;border:1px solid #ccc;border-radius:4px}
  #q{flex:1;min-width:240px}
  #count{font-size:13px;color:#555;margin-left:auto}
  #showall{font-size:13px;padding:5px 11px;cursor:pointer;border:1px solid #10403b;border-radius:4px;
           background:#10403b;color:#fff}
  #showall:hover{background:#1a5c55}
  table{border-collapse:collapse;background:#fff;font-size:13px;table-layout:fixed}
  th,td{text-align:left;padding:6px 10px;border-bottom:1px solid #eee;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  th{position:sticky;top:55px;background:#eaf0ef;cursor:pointer;user-select:none;z-index:1}
  .rz{position:absolute;top:0;right:0;width:6px;height:100%;cursor:col-resize;z-index:2}
  .rz:hover{background:#9bb}
  tr.acq{cursor:pointer}
  tr.acq:hover{background:#eef6ff}
  td.path{font-family:Consolas,monospace;font-size:12px;color:#333}
  button.copy{font-size:12px;padding:2px 9px;cursor:pointer;border:1px solid #bbb;border-radius:4px;background:#f3f3f3}
  button.copy:hover{background:#e7eefc}
  tr.detail td{background:#fafbff;white-space:normal;overflow:visible;text-overflow:clip}
  dl.d{margin:0;display:grid;grid-template-columns:max-content 1fr;gap:3px 14px;font-size:12px}
  dl.d dt{color:#666}
  dl.d dd{margin:0;font-family:Consolas,monospace}
  .empty{padding:24px 18px;color:#666}
</style></head>
<body>
<header><h1>__TITLE__</h1>
<div class="meta">__COUNT__ acquisitions · generated __GENERATED__ · type to search, then "Copy path" and paste into File Explorer · click a row for details</div></header>
<div class="controls">
  <input id="q" placeholder='Search — e.g. m17, MRI, 2026-02, heart, a project...' autofocus>
  <select id="instr"><option value="">All instruments</option></select>
  <input id="from" type="date" title="acquired on/after">
  <input id="to" type="date" title="acquired on/before">
  <span id="count"></span>
  <button id="showall" hidden></button>
</div>
<table><thead><tr id="head"></tr></thead><tbody id="rows"></tbody></table>
<div id="empty" class="empty" hidden>No matches.</div>
<script>
const DATA = __DATA__;
const COLS = [["acq","Acq ID",185],["date","Date",92],["instr","Instr",64],["mod","Modality",95],
  ["researcher","Researcher",105],["operator","Operator",100],["sample","Sample",150],["subject","Subject",170],
  ["organism","Organism",120],["sample_type","Sample type",100],["orig","Original name",210],
  ["proj_short","Project",150],["proj_owner","Owner",110]];
// Rows rendered before we stop and offer "Show all". This is a *display* cap,
// never a search cap: every match is always counted, and "Show all" renders the
// lot. It matters because the default sort is newest-first, so a plain truncation
// silently hides whole instruments — the older ecosystems (LSM9/ZWSI/PET/CT) fall
// outside the newest CAP rows and the page then looks like it only holds MRI+CELL.
const CAP = 800;
let sortKey = "date", sortDir = -1;
let showAll = false;   // reset on every filter change; set by the Show-all button
let hits = [];         // current filtered+sorted matches (row index -> DATA record)
const $ = id => document.getElementById(id);
const esc = s => (s==null?"":(""+s)).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

const head = $("head");
const TABLE = document.querySelector("table");
let tableW = 0;
function startResize(e, th){
  e.preventDefault();
  const startX = e.clientX, startW = th.offsetWidth, startTW = TABLE.offsetWidth;
  const mv = ev => { const w = Math.max(40, startW + ev.clientX - startX);
    th.style.width = w + "px"; TABLE.style.width = (startTW + (w - startW)) + "px"; };
  const up = () => { document.removeEventListener("mousemove", mv);
    document.removeEventListener("mouseup", up); document.body.style.userSelect = ""; };
  document.addEventListener("mousemove", mv); document.addEventListener("mouseup", up);
  document.body.style.userSelect = "none";
}
function buildTh(key, label, w, sortable){
  const th = document.createElement("th"); th.style.width = w + "px"; th.textContent = label;
  if(sortable) th.onclick = () => { sortDir = (sortKey===key) ? -sortDir : 1; sortKey = key; render(); };
  const rz = document.createElement("div"); rz.className = "rz";
  rz.onmousedown = e => { e.stopPropagation(); startResize(e, th); };
  rz.onclick = e => e.stopPropagation();
  th.appendChild(rz); head.appendChild(th); tableW += w;
}
COLS.forEach(([k,label,w]) => buildTh(k, label, w || 120, true));
buildTh("_open", "Open", 96, false);
TABLE.style.width = tableW + "px";
[...new Set(DATA.map(d=>d.instr).filter(Boolean))].sort().forEach(v => {
  const o = document.createElement("option"); o.value = v; o.textContent = v; $("instr").appendChild(o);
});
// A new filter starts a fresh (capped) result set; the Show-all opt-in shouldn't
// silently persist into an unrelated 13k-row query.
["q","instr","from","to"].forEach(id => $(id).addEventListener("input", () => {
  showAll = false; render();
}));
$("showall").onclick = () => { showAll = true; render(); };

function copyPath(p){
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(p).then(()=>{}, ()=>window.prompt("Copy this path:", p));
  } else { window.prompt("Copy this path:", p); }
}
function detailRow(d){
  // 3-tuple rows carry a data-p tag (meta|raw|proj) -> a Copy button in the <dd>.
  const f = [["Raw path",d.path,"raw"],["Project link",d.proj_path,"proj"],
    ["Metadata",d.meta_path,"meta"],
    ["Researcher",d.researcher],["Operator",d.operator],["Session",d.session],
    ["Format",d.format],["File count",d.count],["File size (MB)",d.size],
    ["Original name",d.orig],["Project",d.proj_short],
    ["Project description",d.proj_desc],["Notes",d.notes]];
  const tr = document.createElement("tr"); tr.className = "detail";
  tr.innerHTML = '<td colspan="'+(COLS.length+1)+'"><dl class="d">' +
    f.filter(([,v])=>v).map(([k,v,p]) => "<dt>"+esc(k)+"</dt><dd>"+esc(v) +
      (p ? ' <button class="copy" data-p="'+p+'">Copy</button>' : "") + "</dd>").join("") +
    "</dl></td>";
  tr.querySelectorAll("button.copy").forEach(b => { b.onclick = e => { e.stopPropagation();
    copyPath(b.dataset.p==="meta"?d.meta_path : b.dataset.p==="raw"?d.path : d.proj_path); }; });
  return tr;
}
// One delegated listener on the tbody instead of two per row — at 13k rows the
// per-row handlers were the thing that made "render everything" untenable.
// Detail rows carry their own Copy handlers (which stopPropagation), so only
// the data-copy buttons and tr.acq rows are handled here.
$("rows").addEventListener("click", e => {
  const btn = e.target.closest("button.copy[data-copy]");
  if(btn){ e.stopPropagation(); copyPath(hits[+btn.dataset.copy].path); return; }
  const tr = e.target.closest("tr.acq");
  if(!tr) return;
  const nx = tr.nextSibling;
  if(nx && nx.classList && nx.classList.contains("detail")){ nx.remove(); }
  else { tr.after(detailRow(hits[+tr.dataset.i])); }
});

function render(){
  const term = $("q").value.trim().toLowerCase(), inst = $("instr").value,
        f = $("from").value, t = $("to").value;
  hits = DATA.filter(d =>
    (!term || d.s.includes(term)) && (!inst || d.instr===inst) &&
    (!f || (d.date && d.date>=f)) && (!t || (d.date && d.date<=t)));
  hits.sort((a,b)=>{ const x=a[sortKey]||"", y=b[sortKey]||""; return x<y?-sortDir : x>y?sortDir : 0; });

  const shown = showAll ? hits.length : Math.min(hits.length, CAP);
  $("count").textContent = hits.length + " of " + DATA.length + " match" +
    (shown < hits.length ? "  ·  showing first " + shown : "");
  const sa = $("showall");
  sa.hidden = shown >= hits.length;
  if(!sa.hidden) sa.textContent = "Show all " + hits.length;
  $("empty").hidden = hits.length > 0;

  // Build one HTML string and assign once: at "Show all" sizes this is orders of
  // magnitude cheaper than appending elements row by row.
  let html = "";
  for(let i = 0; i < shown; i++){
    const d = hits[i];
    html += '<tr class="acq" data-i="'+i+'">' +
      COLS.map(([k]) => "<td title=\""+esc(d[k])+"\">"+esc(d[k])+"</td>").join("") +
      '<td><button class="copy" data-copy="'+i+'">Copy path</button></td></tr>';
  }
  $("rows").innerHTML = html;
}
render();
</script></body></html>
"""


def render_html(records, link_base, title, scope=None):
    payload = _payload(records, link_base, scope=scope)
    # ensure_ascii=False keeps it compact + readable; escape "</" so a notes value
    # containing "</script>" can't break out of the embedded script block.
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (_HTML
            .replace("__TITLE__", title)
            .replace("__GENERATED__", generated)
            .replace("__COUNT__", str(len(records)))
            .replace("__DATA__", data))


def _write(path, html):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  wrote {path}  ({len(html)//1024} KB)")


def _project_match_keys(pinfo, pid):
    """Lower-cased identifiers that should match a project group: its PROJ-id,
    its name, and its folder basename. Lets a caller pass whichever it has — the
    resolved PROJ-id, the project's name, or the folder name. Under the
    folder-==-name rule the last two converge, but both are kept so a
    pre-migration folder name still matches.

    Reads the project's OWN registry entry (`pinfo`), not a member record's
    derived `_project_*` fields: those now carry `;`-joined lists across every
    project an acquisition belongs to, which would make `--project X` match a
    group it has nothing to do with.
    """
    keys = {pid.strip().lower()}
    name = (pinfo.get("name") or "").strip().lower()
    if name:
        keys.add(name)
    folder = (pinfo.get("folder") or "").replace("\\", "/").strip().strip("/")
    if folder:
        base = folder.split("/")[-1].lower()
        keys.add(base)
        if base.startswith("proj-"):
            keys.add(base[len("proj-"):])
    return keys


def _write_per_project(records, proj_idx, link_base, nas, out, only=None):
    """Write each project's scoped index.html.

    only=None      -> every project (the --per-project sweep).
    only={ids...}  -> ONLY the projects matching those identifiers (targeted
                      mode); the caller does NOT write the global index.

    Groups by EACH stored project id. `project_id` is a `;`-separated list
    (2026-08-11), so an acquisition in two projects is emitted into BOTH groups.
    Grouping on the whole cell instead would form a bogus `"PROJ-0001;PROJ-0007"`
    group and the acquisition would appear in NEITHER project's index — i.e.
    adding an acquisition to a second project would silently delete it from the
    index of the project it was already in.

    Projects with no folder_location, and closed projects (folder deleted at
    close-out), are skipped. Returns the list of project ids actually written.
    """
    by_proj = defaultdict(list)
    for r in records:
        for pid in (r.get("_project_ids")
                    if r.get("_project_ids") is not None
                    else pids.split_project_ids(r.get("project_id"))):
            by_proj[pid].append(r)

    want = {v.strip().lower() for v in only if v and v.strip()} if only is not None else None
    if want is not None:
        print(f"per-project (targeted): {sorted(want)}")
    else:
        print(f"per-project: {len(by_proj)} project(s)")

    matched, written = set(), []
    for pid, recs in sorted(by_proj.items()):
        # The project's own registry entry — authoritative for its folder, name
        # and status. A group whose id isn't in registry_projects.csv at all is
        # a dangling reference; skip it loudly rather than guessing a path.
        pinfo = proj_idx.get(pid)
        if pinfo is None:
            print(f"  skip {pid}: not in registry_projects.csv")
            continue
        if want is not None:
            hit = _project_match_keys(pinfo, pid) & want
            if not hit:
                continue
            matched |= hit
        folder = pinfo.get("folder", "")
        if not folder:
            print(f"  skip {pid}: no folder_location in registry_projects.csv")
            continue
        # Closed = retention close-out: the registry row survives (so the
        # acquisitions stay findable in the global index) but the folder is
        # gone. Writing here would resurrect the folder we deliberately deleted.
        if pinfo.get("status") == "closed":
            print(f"  skip {pid}: status=closed (folder deleted)")
            continue
        name = pinfo.get("name", "")
        title = f"gjesus3 Finder — {pid}" + (f" ({name})" if name else "")
        out_path = (os.path.join(out, pid, "index.html") if out
                    else os.path.join(nas, folder.lstrip("/"), "index.html"))
        _write(out_path, render_html(recs, link_base, title, scope=pinfo))
        written.append(pid)

    if want is not None:
        for u in sorted(want - matched):
            print(f"  WARN: no acquisitions for project '{u}' -- nothing written")
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nas-root", default=os.environ.get("GJESUS3_ROOT", "J:/gjesus3-data"))
    ap.add_argument("--per-project", action="store_true",
                    help="also write a scoped index.html into each project folder")
    ap.add_argument("--project", action="append", metavar="ID",
                    help="regenerate ONLY the scoped index.html for this project "
                         "(PROJ-id / project name / folder name); repeatable. Skips "
                         "the global index — the cheap path the GUI uses after an "
                         "ingest to refresh just the project it touched.")
    ap.add_argument("--out", default=None,
                    help="write under this local dir instead of the share (preview)")
    ap.add_argument("--link-base", default=DEFAULT_LINK_BASE,
                    help=r"share root prepended to data paths (default \\GJESUS3\gjesus3)")
    args = ap.parse_args(argv)

    nas = os.path.normpath(args.nas_root)
    # proj_idx is no longer discarded: with `project_id` a `;`-list, the
    # per-project writer resolves each group's folder/name/status from the
    # project's OWN registry row rather than from a member record.
    records, proj_idx = find_acq.build_records(nas)
    print(f"Finder: {len(records)} acquisitions (nas={nas}, link_base={args.link_base})")

    # Targeted mode: regenerate ONLY the named project(s); skip the global index.
    # This is the cheap path the GUI uses right after an ingest so a researcher
    # sees the new acquisition in the project index within seconds, without paying
    # for (or racing on) the full ~18 MB global rebuild. The scheduled job keeps
    # the global index fresh.
    if args.project:
        written = _write_per_project(records, proj_idx, args.link_base, nas,
                                     args.out, only=set(args.project))
        print(f"targeted refresh: wrote {len(written)} project index(es)")
        return 0

    # Global index.
    global_path = (os.path.join(args.out, "index.html") if args.out
                   else os.path.join(nas, "registries", "index.html"))
    _write(global_path, render_html(records, args.link_base, "gjesus3 Finder — all acquisitions"))

    # Per-project scoped indexes (all projects).
    if args.per_project:
        _write_per_project(records, proj_idx, args.link_base, nas, args.out,
                           only=None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
