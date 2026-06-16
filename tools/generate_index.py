#!/usr/bin/env python3
"""generate_index.py — write the self-contained, searchable HTML "Finder" for the
acquisition registry onto the NAS share. A researcher double-clicks it over SMB,
types a query (id / instrument / date / subject / region), and copies the path
straight to their data — zero install, no server, no Python on their side.

  # global index -> <nas>/registries/index.html
  python tools/generate_index.py --nas-root J:/gjesus3-data

  # + one scoped index in each project folder
  python tools/generate_index.py --nas-root J:/gjesus3-data --per-project

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

# The SMB share UNC works on any locked-down machine regardless of drive-letter
# mapping; override with --link-base if your share is reached differently.
DEFAULT_LINK_BASE = r"\\GJESUS3\gjesus3"


def _winpath(base, rel):
    """Join the share base + a share-relative path into a Windows UNC path."""
    rel = (rel or "").strip()
    if not rel:
        return ""
    return base.rstrip("/\\") + "\\" + rel.strip("/\\").replace("/", "\\")


def _payload(records, link_base):
    """Curated per-record dict embedded in the page (display + search + paths)."""
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
            "project": r.get("project_hint", ""),
            "researcher": r.get("researcher", ""),
            "size": r.get("file_size_mb", ""),
            "path": _winpath(link_base, raw),
            "proj_path": _winpath(link_base, r.get("_project_folder", "")),
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
  table{border-collapse:collapse;width:100%;background:#fff;font-size:13px}
  th,td{text-align:left;padding:6px 10px;border-bottom:1px solid #eee;white-space:nowrap}
  th{position:sticky;top:55px;background:#eaf0ef;cursor:pointer;user-select:none;z-index:1}
  tr.acq{cursor:pointer}
  tr.acq:hover{background:#eef6ff}
  td.path{font-family:Consolas,monospace;font-size:12px;color:#333}
  button.copy{font-size:12px;padding:2px 9px;cursor:pointer;border:1px solid #bbb;border-radius:4px;background:#f3f3f3}
  button.copy:hover{background:#e7eefc}
  tr.detail td{background:#fafbff;white-space:normal}
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
</div>
<table><thead><tr id="head"></tr></thead><tbody id="rows"></tbody></table>
<div id="empty" class="empty" hidden>No matches.</div>
<script>
const DATA = __DATA__;
const COLS = [["acq","Acq ID"],["date","Date"],["instr","Instr"],["mod","Modality"],
  ["sample","Sample"],["subject","Subject"],["organism","Organism"],["region","Region"],
  ["project","Project"],["size","MB"]];
const CAP = 800;
let sortKey = "date", sortDir = -1;
const $ = id => document.getElementById(id);
const esc = s => (s==null?"":(""+s)).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));

const head = $("head");
COLS.forEach(([k,label]) => {
  const th = document.createElement("th"); th.textContent = label;
  th.onclick = () => { sortDir = (sortKey===k) ? -sortDir : 1; sortKey = k; render(); };
  head.appendChild(th);
});
head.insertAdjacentHTML("beforeend", "<th>Open</th>");
[...new Set(DATA.map(d=>d.instr).filter(Boolean))].sort().forEach(v => {
  const o = document.createElement("option"); o.value = v; o.textContent = v; $("instr").appendChild(o);
});
["q","instr","from","to"].forEach(id => $(id).addEventListener("input", render));

function copyPath(p){
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(p).then(()=>{}, ()=>window.prompt("Copy this path:", p));
  } else { window.prompt("Copy this path:", p); }
}
function detailRow(d){
  const f = [["Raw path",d.path],["Project link",d.proj_path],["Metadata",d.meta_path],
    ["Researcher",d.researcher],["Operator",d.operator],["Session",d.session],
    ["Format",d.format],["File count",d.count],["Original name",d.orig],["Notes",d.notes]];
  const tr = document.createElement("tr"); tr.className = "detail";
  tr.innerHTML = '<td colspan="'+(COLS.length+1)+'"><dl class="d">' +
    f.filter(([,v])=>v).map(([k,v])=>"<dt>"+esc(k)+"</dt><dd>"+esc(v)+"</dd>").join("") + "</dl></td>";
  return tr;
}
function render(){
  const term = $("q").value.trim().toLowerCase(), inst = $("instr").value,
        f = $("from").value, t = $("to").value;
  let hits = DATA.filter(d =>
    (!term || d.s.includes(term)) && (!inst || d.instr===inst) &&
    (!f || (d.date && d.date>=f)) && (!t || (d.date && d.date<=t)));
  hits.sort((a,b)=>{ const x=a[sortKey]||"", y=b[sortKey]||""; return x<y?-sortDir : x>y?sortDir : 0; });
  $("count").textContent = hits.length + " of " + DATA.length + (hits.length>CAP ? "  (showing first "+CAP+")" : "");
  $("empty").hidden = hits.length>0;
  const rows = $("rows"); rows.innerHTML = "";
  hits.slice(0, CAP).forEach(d => {
    const tr = document.createElement("tr"); tr.className = "acq";
    tr.innerHTML = COLS.map(([k]) => "<td>"+esc(d[k])+"</td>").join("") +
      '<td><button class="copy">Copy path</button></td>';
    tr.querySelector("button.copy").onclick = e => { e.stopPropagation(); copyPath(d.path); };
    tr.onclick = () => {
      const nx = tr.nextSibling;
      if(nx && nx.classList && nx.classList.contains("detail")){ nx.remove(); }
      else { tr.after(detailRow(d)); }
    };
    rows.appendChild(tr);
  });
}
render();
</script></body></html>
"""


def render_html(records, link_base, title):
    payload = _payload(records, link_base)
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


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nas-root", default=os.environ.get("GJESUS3_ROOT", "J:/gjesus3-data"))
    ap.add_argument("--per-project", action="store_true",
                    help="also write a scoped index.html into each project folder")
    ap.add_argument("--out", default=None,
                    help="write under this local dir instead of the share (preview)")
    ap.add_argument("--link-base", default=DEFAULT_LINK_BASE,
                    help=r"share root prepended to data paths (default \\GJESUS3\gjesus3)")
    args = ap.parse_args(argv)

    nas = os.path.normpath(args.nas_root)
    records, _ = find_acq.build_records(nas)
    print(f"Finder: {len(records)} acquisitions (nas={nas}, link_base={args.link_base})")

    # Global index.
    global_path = (os.path.join(args.out, "index.html") if args.out
                   else os.path.join(nas, "registries", "index.html"))
    _write(global_path, render_html(records, args.link_base, "gjesus3 Finder — all acquisitions"))

    # Per-project scoped indexes.
    if args.per_project:
        by_proj = defaultdict(list)
        for r in records:
            pid = (r.get("project_hint") or "").strip()
            if pid:
                by_proj[pid].append(r)
        print(f"per-project: {len(by_proj)} project(s)")
        for pid, recs in sorted(by_proj.items()):
            folder = recs[0].get("_project_folder", "")
            if not folder:
                print(f"  skip {pid}: no folder_location in registry_projects.csv")
                continue
            short = recs[0].get("_project_short", "")
            title = f"gjesus3 Finder — {pid}" + (f" ({short})" if short else "")
            out_path = (os.path.join(args.out, pid, "index.html") if args.out
                        else os.path.join(nas, folder.lstrip("/"), "index.html"))
            _write(out_path, render_html(recs, args.link_base, title))
    return 0


if __name__ == "__main__":
    sys.exit(main())
