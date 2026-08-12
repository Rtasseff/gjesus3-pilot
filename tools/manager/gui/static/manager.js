"use strict";

/* manager.js — the Project Manager page controller.
 *
 * Four panes over the /api/* endpoints in app.py: my projects (list + edit),
 * new project, add data from the RDM System (/raw/), add files from my
 * computer. Deliberately the same idioms as the ingest GUI's app.js — tabs,
 * a Preview verb before a commit verb, an SSE log, the completion modal, and
 * the shared folder browser — so the two tools feel like one system and fold
 * together when the RDM server replaces the exes.
 *
 * Shared components (loaded before this file, from /shared/):
 *   folder_browser.js  -> window.browseInto / window.browseFiles
 *   completion_modal.js-> window.showCompletionModal
 */

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;");

async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  let data = null;
  try { data = await r.json(); } catch (e) { /* non-json */ }
  if (!r.ok) throw new Error((data && data.error) || `HTTP ${r.status}`);
  return data;
}

const state = {
  nasRoot: $("nas-root").value.trim(),
  projects: [],
  selected: null,          // the project row shown in the detail panel
  rawSel: new Map(),       // acq_id -> row, the import-from-raw basket
  rawOffset: 0,
  rawRows: [],
  rawPlan: [],
  localFiles: [],          // absolute paths chosen in the file browser
  localOverwrite: new Set(),
};

function showError(msg) {
  $("global-error").textContent = msg || "";
  if (msg) window.scrollTo({ top: 0, behavior: "smooth" });
}

// ------------------------------------------------------------------- tabs

document.querySelectorAll(".tab").forEach((t) => {
  t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    document.querySelectorAll(".tabpane").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    $("tab-" + t.dataset.tab).classList.add("active");
    showError("");
    // Open the acquisition picker with data already in it. An empty table with
    // no explanation reads as "there is nothing here"; the Finder people are
    // used to shows its rows immediately and you narrow from there.
    if (t.dataset.tab === "fromraw" && !state.rawRows.length) runSearch(true);
  });
});

// -------------------------------------------------------------- RDM System

async function refreshNasStatus() {
  // GET, not POST: POSTing an empty body would be read as "set it to blank".
  const r = await fetch("/api/nas_root");
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

$("nas-browse").addEventListener("click", () =>
  window.browseInto($("nas-root"), "Select the RDM System (the folder holding 'registries')"));

$("nas-save").addEventListener("click", async () => {
  const value = $("nas-root").value.trim();
  try {
    const d = await postJSON("/api/nas_root", { nas_root: value });
    setNasPill(d.valid);
    if (d.valid) { state.nasRoot = value; await loadProjects(); }
    else showError("That folder does not contain a 'registries' subfolder, so "
                 + "it is not the RDM System.");
  } catch (e) { showError(e.message); }
});

function setNasPill(valid) {
  const p = $("nas-status");
  p.textContent = valid ? "connected" : "not found";
  p.className = "pill " + (valid ? "ok" : "no");
}

// ---------------------------------------------------------------- projects

const PROJ_COLS = [
  ["project_id", "Project id"], ["name", "Name"], ["owner", "Owner"],
  ["status", "Status"], ["start_date", "Started"],
  ["last_activity", "Last activity"], ["description", "Description"],
];

async function loadProjects() {
  try {
    const d = await postJSON("/api/projects", { nas_root: state.nasRoot });
    state.projects = d.projects || [];
    $("proj-counts").textContent =
      `${d.counts.total} projects · ${d.counts.with_folder} with a folder on the share`
      + (d.counts.no_folder
         ? ` · ${d.counts.no_folder} closed with the folder removed (normal — their data is still findable)`
         : "");
    renderProjects();
    fillProjectSelects();
    showError("");
  } catch (e) {
    state.projects = [];
    renderProjects();
    showError(e.message);
  }
}

function visibleProjects() {
  const q = $("proj-filter").value.trim().toLowerCase();
  const hide = $("proj-hide-closed").checked;
  return state.projects.filter((p) => {
    if (hide && (p.status || "").toLowerCase() === "closed") return false;
    if (!q) return true;
    return PROJ_COLS.some(([k]) => (p[k] || "").toLowerCase().includes(q));
  });
}

function renderProjects() {
  const rows = visibleProjects();
  let html = "<thead><tr>" + PROJ_COLS.map(([, l]) => `<th>${esc(l)}</th>`).join("")
    + "<th>Folder</th></tr></thead><tbody>";
  rows.forEach((p) => {
    html += `<tr class="pick-row" data-pid="${esc(p.project_id)}">`
      + PROJ_COLS.map(([k]) => `<td title="${esc(p[k])}">${esc(p[k])}</td>`).join("")
      + `<td>${p.folder_exists ? "on the share"
            : '<span class="muted">removed at close-out</span>'}</td></tr>`;
  });
  html += "</tbody>";
  $("proj-table").innerHTML = rows.length ? html
    : "<tbody><tr><td class='muted'>No projects match.</td></tr></tbody>";
  document.querySelectorAll("#proj-table tr.pick-row").forEach((tr) =>
    tr.addEventListener("click", () => selectProject(tr.dataset.pid)));
}

$("proj-filter").addEventListener("input", renderProjects);
$("proj-hide-closed").addEventListener("change", renderProjects);
$("proj-reload").addEventListener("click", loadProjects);

async function selectProject(pid) {
  try {
    const p = await postJSON("/api/project",
                             { nas_root: state.nasRoot, project: pid });
    state.selected = p;
    $("proj-detail").hidden = false;
    ["project_id", "name", "start_date", "last_activity", "folder_location"]
      .forEach((k) => { $("d-" + k).value = p[k] || ""; });
    $("e-description").value = p.description || "";
    $("e-owner").value = p.owner || "";
    $("e-status").value = p.status || "active";
    $("e-notes").value = p.notes || "";
    $("proj-save-msg").textContent = "";

    const notes = [];
    if (!p.folder_exists) {
      notes.push("This project has <strong>no folder</strong> on the share. "
        + "That is normal for a closed project — the folder was removed at "
        + "close-out and the registry entry kept so its acquisitions stay "
        + "findable. You can still edit the entry; you cannot add data to it.");
    } else if (!p.has_yaml) {
      notes.push("This project folder has no <code>_project.yaml</code> (it "
        + "predates the tool that writes one). Edits are saved to the registry.");
    }
    $("proj-banner").innerHTML = notes.length
      ? `<div class="note">${notes.join("<br>")}</div>` : "";

    const missing = p.missing_subfolders || [];
    $("proj-subfolders").innerHTML = !p.folder_exists ? ""
      : (missing.length
          ? `Recommended folders not yet here: <code>${missing.join("/</code>, <code>")}/</code>. `
            + `Copying a file into one creates it.`
          : "All the recommended folders are in place.");
    $("save-state").textContent = p.folder_exists
      ? "Saved to the registry and to _project.yaml." : "Saved to the registry.";
    $("proj-detail").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (e) { showError(e.message); }
}

$("proj-save").addEventListener("click", async () => {
  if (!state.selected) return;
  const btn = $("proj-save");
  btn.disabled = true;
  try {
    const d = await postJSON("/api/update_project", {
      nas_root: state.nasRoot,
      project_id: state.selected.project_id,
      updates: {
        description: $("e-description").value,
        owner: $("e-owner").value.trim(),
        status: $("e-status").value,
        notes: $("e-notes").value,
      },
    });
    const n = Object.keys(d.applied || {}).length;
    let msg = n ? `Saved ${n} change${n === 1 ? "" : "s"}.` : "Nothing changed.";
    if ((d.yaml_changed || []).length) msg += " _project.yaml updated too.";
    (d.warnings || []).forEach((w) => { msg += "\n" + w; });
    $("proj-save-msg").textContent = msg;
    await loadProjects();
    showError("");
  } catch (e) {
    $("proj-save-msg").textContent = "";
    showError(e.message);
  } finally { btn.disabled = false; }
});

function fillProjectSelects() {
  // Only projects that can actually receive data — a closed project's folder
  // was deleted, so offering it would only produce an error later.
  const open = state.projects.filter((p) => p.folder_exists);
  ["r-project", "l-project"].forEach((id) => {
    const sel = $(id), keep = sel.value;
    sel.innerHTML = '<option value="">— pick a project —</option>'
      + open.map((p) => `<option value="${esc(p.project_id)}">`
          + `${esc(p.name)} (${esc(p.project_id)})</option>`).join("");
    if (keep) sel.value = keep;
  });
}

// ------------------------------------------------------------- new project

let nameTimer = null;
$("c-name").addEventListener("input", () => {
  clearTimeout(nameTimer);
  nameTimer = setTimeout(checkName, 250);
});

async function checkName() {
  const raw = $("c-name").value;
  if (!raw.trim()) { $("c-name-msg").textContent = ""; return; }
  try {
    const d = await postJSON("/api/check_project_name",
                             { nas_root: state.nasRoot, name: raw });
    if ((d.errors || []).length) {
      $("c-name-msg").innerHTML = `<span class="bad">${esc(d.errors.join(" "))}</span>`;
    } else {
      const changed = d.name !== raw.trim();
      $("c-name-msg").innerHTML = `Folder: <code>${esc(d.folder)}</code>`
        + (changed ? ` <span class="muted">— spaces become hyphens</span>` : "");
    }
  } catch (e) { $("c-name-msg").textContent = ""; }
}

$("c-create").addEventListener("click", async () => {
  const btn = $("c-create");
  btn.disabled = true;
  try {
    const d = await postJSON("/api/create_project", {
      nas_root: state.nasRoot,
      name: $("c-name").value,
      description: $("c-description").value,
      owner: $("c-owner").value,
      notes: $("c-notes").value,
    });
    $("c-msg").innerHTML = `Created <strong>${esc(d.project_id)}</strong> — `
      + `<code>projects/${esc(d.name)}</code> with `
      + `<code>${(d.subfolders || []).join("/</code>, <code>")}/</code>.`;
    ["c-name", "c-description", "c-owner", "c-notes"].forEach((i) => { $(i).value = ""; });
    $("c-name-msg").textContent = "";
    await loadProjects();
    showError("");
  } catch (e) {
    $("c-msg").textContent = "";
    showError(e.message);
  } finally { btn.disabled = false; }
});

// ------------------------------------------------- add data from the RDM System

const RAW_COLS = [
  ["date", "Date"], ["acq_id", "Acq ID"], ["instrument", "Instr"],
  ["researcher", "Researcher"], ["sample_id", "Sample"],
  ["subject_ids", "Subject"], ["anatomical_entity", "Region"],
  ["original_name", "Original name"], ["project_names", "Already in"],
];

let searchTimer = null;
["r-q", "r-since", "r-until"].forEach((id) =>
  $(id).addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => runSearch(true), 300);
  }));
$("r-instrument").addEventListener("change", () => runSearch(true));
$("r-project").addEventListener("change", () => runSearch(true));

async function runSearch(reset) {
  if (reset) { state.rawOffset = 0; state.rawRows = []; }
  try {
    const d = await postJSON("/api/search_acqs", {
      nas_root: state.nasRoot,
      query: $("r-q").value,
      instrument: $("r-instrument").value,
      since: $("r-since").value,
      until: $("r-until").value,
      exclude_project: $("r-project").value,
      offset: state.rawOffset,
    });
    if (!$("r-instrument").dataset.filled) {
      $("r-instrument").innerHTML = '<option value="">All</option>'
        + (d.instruments || []).map((i) => `<option>${esc(i)}</option>`).join("");
      $("r-instrument").dataset.filled = "1";
    }
    state.rawRows = state.rawRows.concat(d.rows || []);
    $("r-counts").innerHTML =
      `${d.total} match${d.total === 1 ? "" : "es"} · showing ${state.rawRows.length}`
      + (d.already_in_project
          ? ` · <span class="muted">${d.already_in_project} already in this project (hidden)</span>`
          : "");
    $("r-more").hidden = state.rawRows.length >= d.total;
    renderRawTable();
    showError("");
  } catch (e) { showError(e.message); }
}

$("r-more").addEventListener("click", () => {
  state.rawOffset = state.rawRows.length;
  runSearch(false);
});

function renderRawTable() {
  let html = "<thead><tr><th></th>"
    + RAW_COLS.map(([, l]) => `<th>${esc(l)}</th>`).join("") + "</tr></thead><tbody>";
  state.rawRows.forEach((r) => {
    const on = state.rawSel.has(r.acq_id) ? " checked" : "";
    html += `<tr><td><input type="checkbox" data-acq="${esc(r.acq_id)}"${on}></td>`
      + RAW_COLS.map(([k]) => `<td title="${esc(r[k])}">${esc(r[k])}</td>`).join("")
      + "</tr>";
  });
  html += "</tbody>";
  $("r-table").innerHTML = state.rawRows.length ? html
    : "<tbody><tr><td class='muted'>Nothing matches yet — type in the search box.</td></tr></tbody>";
  document.querySelectorAll("#r-table input[type=checkbox]").forEach((box) =>
    box.addEventListener("change", () => {
      const id = box.dataset.acq;
      const row = state.rawRows.find((x) => x.acq_id === id);
      if (box.checked) state.rawSel.set(id, row); else state.rawSel.delete(id);
      renderSelCount();
    }));
  renderSelCount();
}

function renderSelCount() {
  const n = state.rawSel.size;
  $("r-selcount").textContent = n
    ? `${n} acquisition${n === 1 ? "" : "s"} selected`
    : "Nothing selected.";
  $("r-go").disabled = true;      // a fresh selection needs a fresh Preview
  $("r-state").textContent = n ? "Preview first, then add." : "";
}

$("r-clearsel").addEventListener("click", () => {
  state.rawSel.clear(); state.rawPlan = [];
  $("r-plan").innerHTML = ""; $("r-plan-msg").textContent = "";
  renderRawTable();
});

function planLinkNames() {
  const out = {};
  document.querySelectorAll("#r-plan input[data-link]").forEach((el) => {
    out[el.dataset.link] = el.value;
  });
  return out;
}

$("r-preview").addEventListener("click", async () => {
  if (!state.rawSel.size) { showError("Tick at least one acquisition."); return; }
  if (!$("r-project").value) { showError("Pick a project first."); return; }
  try {
    const d = await postJSON("/api/import_raw_plan", {
      nas_root: state.nasRoot,
      project: $("r-project").value,
      acq_ids: Array.from(state.rawSel.keys()),
      link_names: planLinkNames(),
    });
    state.rawPlan = d.items || [];
    renderPlan(d);
    showError("");
  } catch (e) { showError(e.message); }
});

function renderPlan(d) {
  const items = d.items || [];
  let html = "<thead><tr><th>Acquisition</th><th>Name in your project</th>"
    + "<th>What happens</th></tr></thead><tbody>";
  items.forEach((it) => {
    const warn = it.status !== "new" ? ' class="has-warn"' : "";
    html += `<tr${warn}><td>${esc(it.acq_id)}</td>`
      + `<td><input type="text" data-link="${esc(it.acq_id)}" `
      + `value="${esc(it.link_name)}" size="30"></td>`
      + `<td class="wrap">${it.status === "new"
          ? "will be added as a hard link"
          : esc(it.note || it.status)}</td></tr>`;
  });
  html += "</tbody>";
  $("r-plan").innerHTML = html;
  // Editing a name invalidates the preview — the collision check was made
  // against the OLD name, and committing on a stale plan is how you overwrite
  // something. Re-preview is one click.
  document.querySelectorAll("#r-plan input[data-link]").forEach((el) =>
    el.addEventListener("input", () => {
      $("r-go").disabled = true;
      $("r-state").textContent = "Name changed — preview again.";
    }));
  const nNew = d.n_new || 0;
  $("r-plan-msg").textContent = nNew
    ? `${nNew} will be added; ${items.length - nNew} skipped.`
    : "Nothing to add — see the reasons above.";
  $("r-go").disabled = nNew === 0;
  $("r-state").textContent = nNew ? `Adds ${nNew} to the project.` : "";
}

$("r-go").addEventListener("click", async () => {
  const creator = $("r-creator").value.trim();
  if (!creator) { showError("Put your name in — it goes in the project's provenance."); return; }
  const btn = $("r-go");
  btn.disabled = true;
  await streamTo("/api/import_raw", {
    nas_root: state.nasRoot,
    project: $("r-project").value,
    acq_ids: Array.from(state.rawSel.keys()),
    link_names: planLinkNames(),
    creator,
  }, $("r-log"), (payload) => {
    // `total` deliberately EXCLUDES the skipped ones. A skip is not a failure —
    // it is "already in this project" or "that name is taken", both of which the
    // researcher chose to see and neither of which needs an alarming modal. The
    // modal's own arithmetic is `total - ok`, so counting skips in it would
    // title a clean run "finished with issues".
    const ok = (payload.linked || 0) + (payload.queued || 0);
    const failedIds = (payload.results || [])
      .filter((r) => r.outcome === "failed").map((r) => r.acq_id);
    window.showCompletionModal({
      ok,
      total: ok + (payload.failed || 0),
      unit: "acquisitions",
      title: "Added to your project",
      titleFail: "Finished — with issues",
      headline: payload.summary,
      failLine: `${payload.failed || 0} could not be added`,
      failedAcqIds: failedIds,
      rows: [
        { label: "Project", value: payload.project_id },
        payload.skipped ? { label: "Skipped",
          value: `${payload.skipped} — already in this project, or the name was `
               + `taken (see the log)` } : null,
        payload.queued ? { label: "Links pending",
          value: `${payload.queued} — your data is registered; the data office `
               + `completes the file links` } : null,
      ].filter(Boolean),
    });
    state.rawSel.clear();
    state.rawPlan = [];
    $("r-plan").innerHTML = "";
    runSearch(true);
    loadProjects();
  });
});

// ----------------------------------------------- add files from my computer

$("l-browse").addEventListener("click", () =>
  window.browseFiles(null, "Choose files to copy into the project", (paths) => {
    // Add to what is already chosen rather than replacing it, so a second trip
    // into another folder extends the set instead of silently discarding it.
    const seen = new Set(state.localFiles);
    (paths || []).forEach((p) => { if (!seen.has(p)) state.localFiles.push(p); });
    state.localOverwrite.clear();
    refreshLocalPlan();
  }));

$("l-clear").addEventListener("click", () => {
  state.localFiles = []; state.localOverwrite.clear();
  $("l-plan").innerHTML = ""; $("l-totals").textContent = "";
  $("l-chosen").textContent = "No files chosen.";
  $("l-go").disabled = true;
});

["l-project", "l-dest"].forEach((id) =>
  $(id).addEventListener("change", refreshLocalPlan));

async function refreshLocalPlan() {
  const n = state.localFiles.length;
  $("l-chosen").textContent = n ? `${n} file${n === 1 ? "" : "s"} chosen.`
                                : "No files chosen.";
  if (!n || !$("l-project").value) {
    $("l-plan").innerHTML = ""; $("l-totals").textContent = "";
    $("l-state").textContent = "";      // clear the "copies N files" promise too
    $("l-go").disabled = true;
    if (n && !$("l-project").value) $("l-totals").textContent = "Pick a project.";
    return;
  }
  try {
    const d = await postJSON("/api/import_local_plan", {
      nas_root: state.nasRoot,
      project: $("l-project").value,
      subfolder: $("l-dest").value,
      sources: state.localFiles,
      overwrite: Array.from(state.localOverwrite),
    });
    renderLocalPlan(d);
    showError("");
  } catch (e) { showError(e.message); }
}

function renderLocalPlan(d) {
  const items = d.items || [], t = d.totals || {};
  let html = "<thead><tr><th>File</th><th>Size</th><th>What happens</th>"
    + "</tr></thead><tbody>";
  items.forEach((it) => {
    const warn = it.status !== "new" ? ' class="has-warn"' : "";
    let what;
    if (it.status === "new") {
      what = it.replaces ? "will REPLACE the existing file" : "will be copied";
    } else if (it.status === "exists") {
      // The house 409 pattern: never silently clobber — name the file and ask.
      what = `${esc(it.note)} `
        + `<button type="button" class="ow" data-name="${esc(it.name)}">Replace it</button>`;
    } else {
      what = esc(it.note);
    }
    html += `<tr${warn}><td class="wrap">${esc(it.name)}</td>`
      + `<td>${it.size ? fmtSize(it.size) : ""}</td>`
      + `<td class="wrap">${what}</td></tr>`;
  });
  html += "</tbody>";
  $("l-plan").innerHTML = html;
  document.querySelectorAll("#l-plan button.ow").forEach((b) =>
    b.addEventListener("click", () => {
      if (!window.confirm(`Replace "${b.dataset.name}" in the project?\n\n`
          + "The current file there is overwritten and is not kept.")) return;
      state.localOverwrite.add(b.dataset.name);
      refreshLocalPlan();
    }));

  const fits = t.fits !== false;
  $("l-totals").innerHTML =
    `${t.count || 0} file${t.count === 1 ? "" : "s"} · ${fmtSize(t.bytes || 0)} `
    + `into <code>${esc(t.subfolder || "the project root")}</code>`
    + (t.free_bytes != null ? ` · ${fmtSize(t.free_bytes)} free on the share` : "")
    + (fits ? "" : ` — <span class="bad">that will not fit.</span>`);
  $("l-go").disabled = !(t.count && fits);
  $("l-state").textContent = t.count && fits
    ? `Copies ${t.count} file${t.count === 1 ? "" : "s"} onto the share.` : "";
}

function fmtSize(n) {
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0, v = n || 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return (i === 0 ? v.toFixed(0) : v.toFixed(1)) + " " + u[i];
}

$("l-go").addEventListener("click", async () => {
  const creator = $("l-creator").value.trim();
  if (!creator) { showError("Put your name in — it goes in the project's provenance."); return; }
  $("l-go").disabled = true;
  await streamTo("/api/import_local", {
    nas_root: state.nasRoot,
    project: $("l-project").value,
    subfolder: $("l-dest").value,
    sources: state.localFiles,
    overwrite: Array.from(state.localOverwrite),
    creator,
  }, $("l-log"), (payload) => {
    // As above: skipped files are not failures (they were already there and the
    // researcher did not confirm a replace), so they stay out of the ok/total
    // arithmetic and are reported on their own line.
    const ok = payload.copied || 0;
    window.showCompletionModal({
      ok,
      total: ok + (payload.failed || 0),
      unit: "files",
      title: "Copied into your project",
      titleFail: "Finished — with issues",
      headline: `${ok} file${ok === 1 ? "" : "s"} copied into the project.`,
      failLine: `${payload.failed || 0} could not be copied`,
      rows: [
        { label: "Into", value: payload.dest_dir },
        payload.skipped ? { label: "Skipped",
          value: `${payload.skipped} — already there, or not a file (see the log)` }
          : null,
      ].filter(Boolean),
    });
    state.localFiles = []; state.localOverwrite.clear();
    refreshLocalPlan();
  });
});

// ------------------------------------------------------------- SSE plumbing

/* The ingest GUI's commit-stream idiom: POST, read the SSE body, append each
 * line to a <pre>, and hand the final `done` payload to the caller. fetch +
 * a manual reader rather than EventSource because the request is a POST with
 * a JSON body. */
async function streamTo(url, body, logEl, onDone) {
  logEl.hidden = false;
  logEl.textContent = "";
  try {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      let msg = `HTTP ${r.status}`;
      try { msg = (await r.json()).error || msg; } catch (e) { /* non-json */ }
      throw new Error(msg);
    }
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop();
      for (const part of parts) {
        const line = part.replace(/^data: /, "").trim();
        if (!line) continue;
        let ev;
        try { ev = JSON.parse(line); } catch (e) { continue; }
        if (ev.kind === "log") {
          const span = document.createElement("span");
          span.className = ev.level;
          span.textContent = (ev.level === "INFO" ? "" : ev.level + ": ") + ev.msg + "\n";
          logEl.appendChild(span);
          logEl.scrollTop = logEl.scrollHeight;
        } else if (ev.kind === "error") {
          showError(ev.msg);
        } else if (ev.kind === "done") {
          onDone(JSON.parse(ev.msg));
        }
      }
    }
    showError("");
  } catch (e) {
    showError(e.message);
  }
}

// ------------------------------------------------------------------- start

(async function boot() {
  try {
    const d = await refreshNasStatus();
    $("nas-root").value = d.nas_root || "";
    state.nasRoot = d.nas_root || "";
    setNasPill(d.valid);
    if (d.valid) await loadProjects();
    else showError("Set the RDM System first — the folder that contains "
                 + "'registries' (usually \\\\gjesus3\\gjesus3\\gjesus3-data).");
  } catch (e) { showError(e.message); }
})();
