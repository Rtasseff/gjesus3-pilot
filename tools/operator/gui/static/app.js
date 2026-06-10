"use strict";

// ---------------------------------------------------------------- helpers
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = null;
  try { data = await r.json(); } catch (e) { /* non-json */ }
  if (!r.ok) {
    const msg = (data && data.error) || `HTTP ${r.status}`;
    throw new Error(msg);
  }
  return data;
}

function getJSON(url) {
  return fetch(url).then((r) => r.json());
}

// Controlled sample_type vocabulary <option>s, injected by the page from
// window.SAMPLE_TYPES (06_REGISTRIES §2.4).
function sampleTypeOptions() {
  return (window.SAMPLE_TYPES || []).map((s) =>
    `<option value="${esc(s.value)}">${esc(s.label)}</option>`).join("");
}

// ---------------------------------------------------------------- tabs
$$(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".tab").forEach((b) => b.classList.toggle("active", b === btn));
    const tab = btn.dataset.tab;
    $$(".tabpane").forEach((p) =>
      p.classList.toggle("active", p.id === `tab-${tab}`));
  });
});

// ---------------------------------------------------------------- NAS root
const nasInput = $("#nas-root");
const nasStatus = $("#nas-status");

function setNasStatus(valid) {
  nasStatus.textContent = valid ? "valid" : "not found";
  nasStatus.className = "pill " + (valid ? "ok" : "no");
}
async function saveNas() {
  try {
    const data = await postJSON("/api/nas_root", { nas_root: nasInput.value });
    setNasStatus(data.valid);
    loadRecipesDir();   // the default recipes folder (<NAS>/recipes) follows the NAS
  } catch (e) { setNasStatus(false); }
}
$("#nas-save").addEventListener("click", saveNas);
getJSON("/api/nas_root").then((d) => { setNasStatus(d.valid); });

function nasRoot() { return nasInput.value.trim(); }

// ---------------------------------------------------------------- recipes folder
// Where saved recipes (YAML) live. Defaults to <NAS>/recipes on shared storage so
// every operator reads/writes the same set; persisted + overridable.
const recipesDirInput = $("#recipes-dir");
const recipesStatus = $("#recipes-status");
function setRecipesStatus(d) {
  recipesStatus.textContent = d.is_default ? "default" : (d.exists ? "set" : "new");
  recipesStatus.className = "pill " + (d.exists ? "ok" : "");
}
async function loadRecipesDir() {
  try {
    const d = await getJSON("/api/recipes_dir");
    recipesDirInput.value = d.recipes_dir || "";
    recipesDirInput.placeholder = d.default || "<NAS>\\recipes";
    setRecipesStatus(d);
  } catch (e) { /* non-fatal */ }
}
async function saveRecipesDir() {
  try {
    const d = await postJSON("/api/recipes_dir", { recipes_dir: recipesDirInput.value });
    recipesDirInput.value = d.recipes_dir || "";
    setRecipesStatus(d);
    loadRecipes();   // re-list recipes from the new location
  } catch (e) { /* non-fatal */ }
}
$("#recipes-save").addEventListener("click", saveRecipesDir);
$("#recipes-browse").addEventListener("click", () =>
  browseInto(recipesDirInput, "Select the folder to keep recipes in", () => saveRecipesDir()));
loadRecipesDir();

// ---------------------------------------------------------------- folder browse
// In-page folder browser. Unlike the OS folder-only dialog (which made every
// folder look empty), this shows folders AND greyed files for context: click a
// folder to open it, then "Use this folder". A LOCAL app, so /api/listdir lists
// the local filesystem.
const fb = {
  overlay: $("#fb-overlay"), list: $("#fb-list"), pathInp: $("#fb-path"),
  drives: $("#fb-drives"), err: $("#fb-error"), title: $("#fb-title"),
  target: null, cur: "", parent: null, onPick: null,
};

function browseInto(input, title, onPick) {
  if (!input) return;
  fb.target = input;
  fb.onPick = onPick || null;
  fb.title.textContent = title || "Select a folder";
  fb.err.textContent = "";
  fb.overlay.hidden = false;
  fbLoad(input.value.trim() || "");
}

function joinPath(base, name) {
  if (!base) return name;
  const sep = base.includes("\\") ? "\\" : "/";
  return base.replace(/[\\/]+$/, "") + sep + name;
}

async function fbLoad(path) {
  fb.err.textContent = "";
  fb.list.innerHTML = "<div class='fb-empty'>Loading…</div>";
  let data;
  try {
    data = await postJSON("/api/listdir", { path });
  } catch (e) {
    fb.list.innerHTML = "";
    fb.err.textContent = e.message;
    return;
  }
  fb.cur = data.path;
  fb.parent = data.parent || null;
  fb.pathInp.value = data.path;
  $("#fb-up").disabled = !fb.parent;

  fb.drives.innerHTML = (data.drives || []).map((d) =>
    `<span class="fb-drive" data-path="${esc(d)}">${esc(d)}</span>`).join("");
  $$("#fb-drives .fb-drive").forEach((el) =>
    el.addEventListener("click", () => fbLoad(el.dataset.path)));

  const items = [];
  if (fb.parent) {
    items.push(`<div class="fb-item dir" data-path="${esc(fb.parent)}"><span class="ic">↑</span><span>.. (up)</span></div>`);
  }
  (data.entries || []).forEach((e) => {
    if (e.is_dir) {
      items.push(`<div class="fb-item dir" data-name="${esc(e.name)}"><span class="ic">📁</span><span>${esc(e.name)}</span></div>`);
    } else {
      items.push(`<div class="fb-item file"><span class="ic">📄</span><span>${esc(e.name)}</span></div>`);
    }
  });
  fb.list.innerHTML = items.length ? items.join("") : "<div class='fb-empty'>(empty folder)</div>";
  if (data.truncated) fb.list.insertAdjacentHTML("beforeend", "<div class='fb-empty'>…list truncated (very large folder).</div>");

  $$("#fb-list .fb-item.dir").forEach((el) => {
    el.addEventListener("click", () =>
      fbLoad(el.dataset.path || joinPath(fb.cur, el.dataset.name)));
  });
  if (data.error) fb.err.textContent = data.error;
}

function fbClose() { fb.overlay.hidden = true; fb.target = null; fb.onPick = null; }
function fbSelect() {
  const chosen = fb.cur, input = fb.target, cb = fb.onPick;
  fbClose();
  if (input) {
    input.value = chosen;
    input.dispatchEvent(new Event("input"));
    input.dispatchEvent(new Event("change"));
  }
  if (cb) cb(chosen);
}

$("#fb-up").addEventListener("click", () => { if (fb.parent) fbLoad(fb.parent); });
$("#fb-go").addEventListener("click", () => fbLoad(fb.pathInp.value.trim()));
fb.pathInp.addEventListener("keydown", (e) => { if (e.key === "Enter") fbLoad(fb.pathInp.value.trim()); });
$("#fb-select").addEventListener("click", fbSelect);
$("#fb-close").addEventListener("click", fbClose);
$("#fb-cancel").addEventListener("click", fbClose);
fb.overlay.addEventListener("click", (e) => { if (e.target === fb.overlay) fbClose(); });

$("#nas-browse").addEventListener("click", () =>
  browseInto(nasInput, "Select the destination NAS root (gjesus3-data)", () => saveNas()));
$("#r-browse").addEventListener("click", () =>
  browseInto($("#r-staging"), "Select the source folder to ingest"));
$("#b-browse").addEventListener("click", () =>
  browseInto($("#b-staging"), "Select an example source folder"));

// ============================================================ RECIPE RUNNER
const rInstrument = $("#r-instrument");
const rRecipe = $("#r-recipe");
let recipesCache = [];
let lastRunnerCases = [];

async function loadRecipes() {
  const inst = rInstrument.value;
  recipesCache = await getJSON(`/api/recipes?instrument=${encodeURIComponent(inst)}`);
  rRecipe.innerHTML = '<option value="">— pick a recipe —</option>' +
    recipesCache.map((r) =>
      `<option value="${esc(r.file)}">${esc(r.name)}</option>`).join("");
  $("#r-recipe-desc").textContent = "";
  loadGaps();
}
rInstrument.addEventListener("change", loadRecipes);
rRecipe.addEventListener("change", () => {
  const rec = recipesCache.find((r) => r.file === rRecipe.value);
  $("#r-recipe-desc").textContent = rec ? rec.description : "";
  loadGaps();
});

function currentRecipeOverrides() {
  const rec = recipesCache.find((r) => r.file === rRecipe.value);
  return rec ? (rec.overrides || {}) : {};
}

// ---- recipe gaps: critical fields the recipe leaves blank, filled per batch --
// The runner asks the backend which CRITICAL_FIELDS are unset in the chosen
// recipe and renders a REQUIRED input for each — a token-field (metadata labels
// + free text), or the sample_type dropdown — filled per batch.
let runnerDiscoveredRow = {};    // first parsed row, shared for live examples
let runnerGapMeta = [];          // [{key,label,kind,hint}] from /api/recipe_gaps
let runnerKeys = [];             // discovered keys (for the runner filter dropdown)
const runnerGapFields = {};      // key -> TokenField
const runnerGapSelects = {};     // key -> <select> (sample_type)

async function loadGaps() {
  updateFilterPanel();   // show/hide the runner filter for this recipe
  const grid = $("#r-gaps-grid");
  Object.keys(runnerGapFields).forEach((k) => delete runnerGapFields[k]);
  Object.keys(runnerGapSelects).forEach((k) => delete runnerGapSelects[k]);
  try {
    const data = await postJSON("/api/recipe_gaps", {
      instrument: rInstrument.value, overrides: currentRecipeOverrides(),
    });
    runnerGapMeta = data.gaps || [];
  } catch (e) { runnerGapMeta = []; }

  if (!runnerGapMeta.length) { $("#r-gaps").hidden = true; grid.innerHTML = ""; return; }
  $("#r-gaps").hidden = false;
  grid.innerHTML = "";
  runnerGapMeta.forEach((f) => {
    const row = document.createElement("div");
    row.className = "req-row"; row.dataset.key = f.key;
    const lab = document.createElement("div"); lab.className = "req-label";
    lab.innerHTML = (f.required ? '<span class="star">★</span> ' : "") + esc(f.label) +
      (f.hint ? ` <span class="muted">— ${esc(f.hint)}</span>` : "") +
      (f.required ? "" : ' <span class="muted">(optional)</span>');
    const val = document.createElement("div"); val.className = "req-val";
    if (f.kind === "sampletype") {
      const sel = document.createElement("select");
      const skip = f.required ? "— pick a sample type —" : "— skip / leave blank —";
      sel.innerHTML = `<option value="">${skip}</option>` + sampleTypeOptions();
      runnerGapSelects[f.key] = sel; val.append(sel);
    } else {
      const tfEl = document.createElement("div");
      const ex = document.createElement("span"); ex.className = "example";
      val.append(tfEl, ex);
      runnerGapFields[f.key] = new TokenField(tfEl, { onChange: updateGapExamples });
    }
    row.append(lab, val); grid.appendChild(row);
  });
  updateGapExamples();
}

function runnerGapOverrides() {
  const ov = {};
  runnerGapMeta.forEach((f) => {
    if (f.kind === "sampletype") {
      const sel = runnerGapSelects[f.key];
      if (sel && sel.value) ov[f.key] = sel.value;
    } else {
      const tf = runnerGapFields[f.key];
      const v = tf ? tf.serialize().trim() : "";
      if (v) ov[f.key] = v;
    }
  });
  return ov;
}

function gapsMissing() {
  return runnerGapMeta.some((f) => {
    if (!f.required) return false;          // optional gaps never block ingest
    if (f.kind === "sampletype") {
      const sel = runnerGapSelects[f.key];
      return !(sel && sel.value);
    }
    const tf = runnerGapFields[f.key];
    return !(tf && tf.serialize().trim());
  });
}

function updateGapExamples() {
  const ctx = runnerDiscoveredRow || {};
  $$("#r-gaps-grid .req-row").forEach((row) => {
    const tf = runnerGapFields[row.dataset.key];
    const ex = row.querySelector(".example");
    if (!tf || !ex) return;
    const val = tf.serialize();
    if (!val.includes("${")) { ex.textContent = ""; ex.classList.remove("bad"); return; }
    const { text, unresolved } = resolveExample(val, ctx, {});
    ex.textContent = "→ " + text;
    ex.classList.toggle("bad", unresolved);
  });
}

async function loadGapFields() {
  $("#r-gaps-palette").innerHTML = "Loading…";
  try {
    const data = await postJSON("/api/discovered", {
      instrument: rInstrument.value, overrides: currentRecipeOverrides(),
      staging_path: $("#r-staging").value, nas_root: nasRoot(), limit: 5,
    });
    runnerDiscoveredRow = (data.rows && data.rows[0]) ? data.rows[0].discovered : {};
    runnerKeys = data.keys || [];
    renderPalette($("#r-gaps-palette"), paletteEntries(runnerKeys),
                  Object.values(runnerGapFields)[0]);
    runnerFilterUI.refresh();   // populate the filter field dropdowns too
    updateGapExamples();
  } catch (e) {
    $("#r-gaps-palette").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
  }
}
$("#r-gaps-load").addEventListener("click", loadGapFields);

// runner filter — same UI as the builder, shown only when the recipe sets none.
const runnerFilterUI = makeFilterBuilder("#r-filter-rows", () => runnerKeys, null);
$("#r-filter-add").addEventListener("click", () => runnerFilterUI.addRow());
function updateFilterPanel() {
  const rf = currentRecipeOverrides()["auto_discover.filter"];
  const hasRecipeFilter = rf && typeof rf === "object" && Object.keys(rf).length > 0;
  $("#r-filter").hidden = false;                 // the filter section is always visible
  $("#r-filter-recipe").hidden = !hasRecipeFilter;
  $("#r-filter-edit").hidden = hasRecipeFilter;
  if (hasRecipeFilter) {
    runnerFilterUI.clear();                      // drop any stale runner rows — recipe wins
    $("#r-filter-recipe").innerHTML = "This recipe filters to " +
      Object.entries(rf).map(([k, v]) =>
        `<code>${esc(tfHumanizeRef(k))} = ${esc(v)}</code>`).join(" <b>AND</b> ") +
      " — edit it in the builder.";
  }
}
function runnerFilter() {
  // Only the runner's OWN rows count, and only when the recipe sets no filter
  // (otherwise the recipe's filter applies and must not be overridden).
  if ($("#r-filter-edit").hidden) return {};
  const f = runnerFilterUI.collect();
  return Object.keys(f).length ? { "auto_discover.filter": f } : {};
}

loadRecipes();

// ---- per-run study metadata (condition block) ----------------------------
// Shown only for instruments whose template carries a condition: block
// (AxioScan tissue; not the cell modes). Values become condition.* overrides
// applied to EVERY acquisition in the run — the GUI equivalent of the
// ni/mri-ingest --is-control / --disease-* flags.
const rIsControl = $("#r-is-control");
// disease_model / disease_state are token-fields: free text + atomic field chips.
const dmField = new TokenField($("#r-disease-model"), { onChange: updateMetaExamples });
const dsField = new TokenField($("#r-disease-state"), { onChange: updateMetaExamples });

async function updateMetaPanel() {
  try {
    const t = await getJSON(`/api/template?instrument=${encodeURIComponent(rInstrument.value)}`);
    $("#r-meta").hidden = !(t && t.condition);
  } catch (e) {
    $("#r-meta").hidden = true;
  }
}
rInstrument.addEventListener("change", updateMetaPanel);
updateMetaPanel();

rIsControl.addEventListener("change", () => {
  // disease_model / disease_state are only meaningful for a case.
  $("#r-meta-case").hidden = rIsControl.value !== "false";
  updateMetaExamples();
});

function runnerMetaOverrides() {
  const ov = {};
  const ic = rIsControl.value;            // "", "true", "false"
  if (ic === "true") {
    ov["condition.is_control"] = true;    // control -> no disease fields
  } else if (ic === "false") {
    ov["condition.is_control"] = false;
    const dm = dmField.serialize().trim();
    const ds = dsField.serialize().trim();
    if (dm) ov["condition.disease_model"] = dm;
    if (ds) ov["condition.disease_state"] = ds;
  }
  return ov;                               // "" -> {} (skip, non-blocking)
}

// Recipe overrides + per-batch gap fills + per-batch filter + condition.
function runnerOverrides() {
  return Object.assign({}, currentRecipeOverrides(), runnerGapOverrides(),
                       runnerFilter(), runnerMetaOverrides());
}

async function loadMetaFields() {
  $("#r-meta-chips").innerHTML = "Loading…";
  try {
    const data = await postJSON("/api/discovered", {
      instrument: rInstrument.value,
      overrides: currentRecipeOverrides(),
      staging_path: $("#r-staging").value,
      nas_root: nasRoot(),
      limit: 5,
    });
    runnerDiscoveredRow = (data.rows && data.rows[0]) ? data.rows[0].discovered : {};
    renderPalette($("#r-meta-chips"), paletteEntries(data.keys || []), dmField);
    updateMetaExamples();
  } catch (e) {
    $("#r-meta-chips").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
  }
}
$("#r-meta-load-fields").addEventListener("click", loadMetaFields);

// Live resolved example for the disease token-fields (reuses resolveExample).
function updateMetaExamples() {
  const ctx = runnerDiscoveredRow || {};
  [[dmField, "#r-dm-ex"], [dsField, "#r-ds-ex"]].forEach(([fld, exSel]) => {
    const ex = $(exSel);
    if (!fld || !ex) return;
    const val = fld.serialize();
    if (!val.includes("${")) { ex.textContent = ""; ex.classList.remove("bad"); return; }
    const { text, unresolved } = resolveExample(val, ctx, {});
    ex.textContent = "→ " + text;
    ex.classList.toggle("bad", unresolved);
  });
}

function renderSummary(el, data) {
  // already-ingested (benign dedup) and dropped-on-error are NOW distinct — a
  // parse failure must never read as "already ingested" (#6).
  const already = (data.n_already_ingested != null) ? data.n_already_ingested
                                                     : (data.n_skipped || 0);
  const dropped = data.n_dropped || 0;
  let s =
    `<span class="new">${data.n_new} new</span> · ` +
    `<span class="skip">${already} already-ingested</span>`;
  if (dropped) s += ` · <span class="drop">${dropped} skipped (errors)</span>`;
  s += ` · ${data.n_matched} matched · pattern <code>${esc(data.pattern)}</code>`;
  el.innerHTML = s;
}

// Files dropped by a parse/filter/validate error — shown prominently (not buried
// in the collapsed log) so the operator sees WHY nothing ingested (#6). Summarised
// BY REASON (the same reason usually repeats across many files) rather than
// listing every file; the full per-file list stays in the Warnings / log.
function renderDropped(el, data) {
  if (!el) return;
  const dropped = data.dropped || [];
  if (!dropped.length) { el.innerHTML = ""; return; }
  const byReason = new Map();
  dropped.forEach((d) => byReason.set(d.reason, (byReason.get(d.reason) || 0) + 1));
  const reasons = [...byReason.entries()].sort((a, b) => b[1] - a[1]);
  const shown = reasons.slice(0, 5).map(([reason, n]) =>
    `<li>${n} × ${esc(reason)}</li>`).join("");
  const more = reasons.length > 5
    ? `<li>…and ${reasons.length - 5} more reason(s)</li>` : "";
  el.innerHTML =
    `<h4>${dropped.length} file(s) skipped because of a parse / filter error — ` +
    `these are NOT already ingested. ` +
    `<span class="muted">Full per-file list in Warnings / log.</span></h4>` +
    `<ul>${shown}${more}</ul>`;
}

function renderCasesTable(cases) {
  if (!cases.length) return "<p class='muted'>No new acquisitions to ingest (all matched files are already in the registry, or none matched).</p>";
  // Columns: acq_id, project, link_filename, then a compact resolved registry
  // row (key columns), then warnings.
  const regKeys = [];
  cases.forEach((c) => Object.keys(c.registry_resolved || {}).forEach((k) => {
    if (!regKeys.includes(k)) regKeys.push(k);
  }));
  const head =
    "<tr><th>#</th><th>acq_id (preview)</th><th>project</th><th>link name</th>" +
    regKeys.map((k) => `<th>${esc(k)}</th>`).join("") +
    "<th>warnings</th></tr>";
  const rows = cases.map((c, i) => {
    const warn = (c.warnings || []).length;
    const reg = regKeys.map((k) =>
      `<td>${esc((c.registry_resolved || {})[k] ?? "")}</td>`).join("");
    return `<tr class="${warn ? "has-warn" : ""}">` +
      `<td>${i + 1}</td>` +
      `<td>${esc(c.acq_id)}</td>` +
      `<td>${esc(c.project)}</td>` +
      `<td>${esc(c.link_filename)}</td>` +
      reg +
      `<td class="wrap">${warn ? esc((c.warnings || []).join(" / ")) : ""}</td>` +
      "</tr>";
  }).join("");
  return `<table>${head}${rows}</table>`;
}

async function runnerPreview() {
  $("#r-errors").textContent = "";
  $("#r-summary").innerHTML = "";
  $("#r-dropped").innerHTML = "";
  if (gapsMissing()) {
    $("#r-errors").textContent = "Fill in the required per-batch values first (the recipe leaves some blank).";
    $("#r-table-wrap").innerHTML = "";
    return;
  }
  $("#r-table-wrap").innerHTML = "Previewing…";
  $("#r-ingest").disabled = true;
  try {
    const data = await postJSON("/api/preview", {
      instrument: rInstrument.value,
      overrides: runnerOverrides(),
      staging_path: $("#r-staging").value,
      nas_root: nasRoot(),
    });
    lastRunnerCases = data.cases;
    renderSummary($("#r-summary"), data);
    renderDropped($("#r-dropped"), data);
    if (data.blocking_errors && data.blocking_errors.length) {
      $("#r-errors").textContent = data.blocking_errors.join("\n");
    }
    $("#r-table-wrap").innerHTML = renderCasesTable(data.cases);
    $("#r-warnings").textContent = (data.warnings || []).join("\n");
    $("#r-warnings-wrap").style.display = (data.warnings || []).length ? "" : "none";
    $("#r-ingest").disabled = data.cases.length === 0;
  } catch (e) {
    $("#r-table-wrap").innerHTML = "";
    $("#r-errors").textContent = e.message;
  }
}
$("#r-preview").addEventListener("click", runnerPreview);

// ---- ingest (SSE streaming log) ----
function appendLog(pre, level, msg) {
  const span = document.createElement("span");
  span.className = level;
  span.textContent = `${level}: ${msg}\n`;
  pre.appendChild(span);
  pre.scrollTop = pre.scrollHeight;
}

async function runnerIngest() {
  if (gapsMissing()) {
    $("#r-errors").textContent = "Fill in the required per-batch values first (the recipe leaves some blank).";
    return;
  }
  const dry = $("#r-dry").checked;
  $("#r-log-wrap").hidden = false;
  const logEl = $("#r-log");
  logEl.textContent = "";
  $("#r-result").innerHTML = "";
  $("#r-ingest").disabled = true;
  $("#r-preview").disabled = true;

  const rec = recipesCache.find((r) => r.file === rRecipe.value);
  const recipePath = rec ? (rec.path || rec.file) : "";

  // SSE via fetch + ReadableStream (POST body needed -> can't use EventSource).
  let resp;
  try {
    resp = await fetch("/api/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        instrument: rInstrument.value,
        overrides: runnerOverrides(),
        staging_path: $("#r-staging").value,
        nas_root: nasRoot(),
        dry_run: dry,
        recipe_path: recipePath,
      }),
    });
  } catch (e) {
    appendLog(logEl, "ERROR", e.message);
    $("#r-ingest").disabled = false; $("#r-preview").disabled = false;
    return;
  }
  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`;
    try { const j = await resp.json(); if (j.error) msg = j.error; } catch (e) {}
    appendLog(logEl, "ERROR", msg);
    $("#r-ingest").disabled = false; $("#r-preview").disabled = false;
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const line = chunk.replace(/^data: /, "");
      if (!line.trim()) continue;
      let evt;
      try { evt = JSON.parse(line); } catch (e) { continue; }
      if (evt.kind === "log") {
        appendLog(logEl, evt.level || "INFO", evt.msg);
      } else if (evt.kind === "error") {
        appendLog(logEl, "ERROR", evt.msg);
      } else if (evt.kind === "done") {
        const r = JSON.parse(evt.msg);
        $("#r-result").innerHTML =
          `<span class="new">${r.ok}/${r.total} ${r.dry_run ? "would ingest" : "ingested"}</span>` +
          (r.dry_run ? " (dry-run — nothing written)" : "");
      }
    }
  }
  $("#r-ingest").disabled = false;
  $("#r-preview").disabled = false;
}
$("#r-ingest").addEventListener("click", runnerIngest);

// ---- dry-run state (OFF by default; make LIVE-vs-SAFE loud) (#8) ----
const rDry = $("#r-dry");
const rCommit = $("#r-commit");
const rDryState = $("#r-dry-state");
function updateDryState() {
  const dry = rDry.checked;
  rCommit.classList.toggle("safe", dry);
  rCommit.classList.toggle("live", !dry);
  rDryState.textContent = dry
    ? "Safe — nothing will be written."
    : "LIVE — Ingest will write to the NAS.";
}
rDry.addEventListener("change", updateDryState);
updateDryState();

// ================================================================ BUILDER
const bInstrument = $("#b-instrument");
let builderKeys = [];           // discovered keys from the last "Show fields"
let builderDiscoveredRow = {};  // first parsed row, for live "→ example" lines
const builderFields = {};       // field key -> TokenField (token rows only)
const builderSelects = {};      // field key -> <select> (controlled-vocab rows)

// "3 · Set the values to record" — the values we have a priority to capture.
// ★ high-priority = the registry person columns + sample id.
//
// NOTE: study-design metadata (Animal role / is_control, disease_model,
// disease_state) is deliberately NOT here. It varies per animal/group, so it
// can't be baked into a reusable naming-convention recipe (a cohort is rarely
// all-control or all-case). It's captured per-run in the Runner instead; the
// per-acquisition "derive is_control from a metadata label" rule is a planned
// next revision (tasks/BACKLOG.md).
// `gap: true` marks the fields that are SELF-CONTAINED in the recipe: the builder
// saves them explicitly (value OR an explicit blank), so leaving one blank is a
// real blank that the Runner prompts for per batch — it does NOT silently fall
// back to the template default. Must match the backend CRITICAL_FIELDS keys.
// Non-gap fields (acq date / session / notes) still fall back to the template.
const REQUIRED_FIELDS = [
  { key: "registry.researcher",           label: "Researcher",       star: true, hint: "who ran the study", gap: true },
  { key: "operator",                      label: "Operator",         star: true, hint: "who ran the equipment", gap: true },
  { key: "registry.sample_id",            label: "Sample ID",        star: true, gap: true },
  { key: "registry.sample_type",          label: "Sample type",      type: "select", gap: true },
  { key: "registry.acquisition_datetime", label: "Acquisition date" },
  { key: "registry.project_hint",         label: "Project hint",     gap: true },
  { key: "registry.session_id",           label: "Session ID" },
  { key: "registry.notes",                label: "Notes" },
  { key: "link_filename",                 label: "Project link name", gap: true },
];

// Build the "values to record" rows once (all token-fields).
function buildRequiredGrid() {
  const grid = $("#b-required");
  grid.innerHTML = "";
  REQUIRED_FIELDS.forEach((f) => {
    const row = document.createElement("div");
    row.className = "req-row";
    row.dataset.key = f.key;
    const star = f.star ? '<span class="star">★</span> ' : "";
    const hint = f.hint ? ` <span class="muted">— ${esc(f.hint)}</span>` : "";
    const lab = document.createElement("div");
    lab.className = "req-label";
    lab.innerHTML = `${star}${esc(f.label)}${hint}`;
    const val = document.createElement("div");
    val.className = "req-val";
    if (f.type === "select") {
      // controlled vocabulary (sample_type) — skip or pick, never free text
      const sel = document.createElement("select");
      sel.innerHTML = '<option value="">— skip / leave blank —</option>' + sampleTypeOptions();
      sel.addEventListener("change", renderOverrideJSON);
      builderSelects[f.key] = sel;
      val.append(sel);
    } else {
      const tfEl = document.createElement("div");
      const ex = document.createElement("span");
      ex.className = "example";
      val.append(tfEl, ex);
      builderFields[f.key] = new TokenField(tfEl, {
        onChange: () => { renderOverrideJSON(); updateBuilderExamples(); },
      });
    }
    row.append(lab, val);
    grid.appendChild(row);
  });
  // Project link name is critical and must never be left blank — default it to
  // the always-present original_name (operators can change it).
  builderFields["link_filename"].setValue("${original_name}");
}

// ---- folder levels (section 1) ----
function renderLevels() {
  const n = Math.max(0, Math.min(8, parseInt($("#b-levels-count").value, 10) || 0));
  const wrap = $("#b-levels");
  const prev = $$("#b-levels .level-label").map((inp) => inp.value);  // preserve
  wrap.innerHTML = "";
  for (let i = 0; i < n; i++) {
    const lab = document.createElement("label");
    lab.textContent = `metadata label for sub-folder ${i + 1}`;
    const inp = document.createElement("input");
    inp.type = "text";
    inp.className = "level-label";
    inp.placeholder = "e.g. researcher / cell_line / experiment";
    if (prev[i]) inp.value = prev[i];
    inp.addEventListener("input", renderOverrideJSON);
    lab.appendChild(inp);
    wrap.appendChild(lab);
  }
  renderOverrideJSON();
}
// Level names for path_parse: blanks become folder_N so the LEVEL COUNT always
// matches the folder depth (a mismatched count is what the preview flags).
function builderLevelLabels() {
  return $$("#b-levels .level-label").map((inp, i) => inp.value.trim() || `folder_${i + 1}`);
}
$("#b-levels-count").addEventListener("input", () => { renderLevels(); loadLayoutDebounced(); });

// ---- shared filter builder (Builder section 2 + Runner when the recipe sets no
// filter). label = value rows joined by AND, with + / ×. getKeys() supplies the
// available metadata-label keys; onChange (optional) fires on any edit.
function makeFilterBuilder(rowsSel, getKeys, onChange) {
  const fire = () => { if (onChange) onChange(); };
  function fieldOptions(selected) {
    const keys = getKeys() || [];
    if (!keys.length) return '<option value="">(show metadata labels first)</option>';
    return '<option value="">— pick a metadata label —</option>' + keys.map((k) =>
      `<option value="${esc(k)}"${k === selected ? " selected" : ""}>${esc(tfHumanizeRef(k))}</option>`).join("");
  }
  function addRow(field, value) {
    const row = document.createElement("div"); row.className = "filter-row";
    const sel = document.createElement("select"); sel.className = "f-field";
    sel.innerHTML = fieldOptions(field);
    const eq = document.createElement("span"); eq.textContent = "=";
    const val = document.createElement("input");
    val.type = "text"; val.className = "f-val"; val.placeholder = "value";
    if (value != null) val.value = value;
    const rm = document.createElement("button");
    rm.type = "button"; rm.className = "rm"; rm.textContent = "×"; rm.title = "remove";
    rm.addEventListener("click", () => { row.remove(); fire(); });
    [sel, val].forEach((el) => el.addEventListener("input", fire));
    row.append(sel, eq, val, rm);
    $(rowsSel).appendChild(row);
  }
  function refresh() {
    $$(`${rowsSel} .f-field`).forEach((sel) => {
      const cur = sel.value; sel.innerHTML = fieldOptions(cur); sel.value = cur;
    });
  }
  function collect() {
    const out = {};
    $$(`${rowsSel} .filter-row`).forEach((row) => {
      const k = row.querySelector(".f-field").value.trim();
      const v = row.querySelector(".f-val").value.trim();
      if (k) out[k] = v;
    });
    return out;
  }
  function clear() { $(rowsSel).innerHTML = ""; }
  return { addRow, refresh, collect, clear };
}

const builderFilterUI = makeFilterBuilder("#b-filter-rows", () => builderKeys, renderOverrideJSON);
$("#b-filter-add").addEventListener("click", () => builderFilterUI.addRow());

// ---- example-layout preview (section 1): show the operator their REAL folders ----
// Probes the example source folder ANCHORED to the chosen "Folder levels" count
// (N) — shows a real data path exactly N deep (refreshing as N changes) instead
// of chasing the deepest, possibly irrelevant, sub-folder. Also splits example
// file names into chunks so the "File-name metadata labels" count is obvious.
let builderLayout = null;
function currentLevels() {
  return Math.max(0, parseInt($("#b-levels-count").value, 10) || 0);
}
function debounce(fn, ms) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

async function loadLayout() {
  const path = $("#b-staging").value.trim();
  const box = $("#b-layout");
  if (!path) { box.innerHTML = ""; builderLayout = null; renderFileExamples(); return; }
  box.innerHTML = "<span class='muted'>Reading example folder…</span>";
  try {
    const data = await postJSON("/api/sample_layout", {
      path, levels: currentLevels(), instrument: bInstrument.value,
    });
    builderLayout = data;
    renderLayout();
    renderFileExamples();
  } catch (e) {
    box.innerHTML = `<span class="bad">${esc(e.message)}</span>`;
    builderLayout = null; renderFileExamples();
  }
}
const loadLayoutDebounced = debounce(loadLayout, 250);

function renderLayout() {
  const box = $("#b-layout");
  const d = builderLayout;
  if (!d) { box.innerHTML = ""; return; }
  if (d.error) { box.innerHTML = `<span class="muted">${esc(d.error)}</span>`; return; }

  // No data path at exactly the chosen depth — point them at the real depth.
  if (!d.match) {
    let msg = `No <code>${esc(d.ext)}</code> files exactly <strong>${d.levels}</strong> folder level${d.levels === 1 ? "" : "s"} below the source.`;
    if (d.file_depths && d.file_depths.length) {
      const list = d.file_depths.join(" or ");
      msg += ` Your files are <strong>${list}</strong> level${d.file_depths.length === 1 && d.file_depths[0] === 1 ? "" : "s"} down — set "Folder levels before the files" to match.`;
    }
    box.innerHTML = `<div class="layout-tree warn">${msg}</div>`;
    return;
  }

  const lines = [
    `<div class="lt-row"><span class="lt-ic">📁</span><strong>${esc(d.root)}</strong> <span class="muted">— your source folder</span></div>`,
  ];
  d.chain.forEach((name, i) => {
    lines.push(`<div class="lt-row" style="padding-left:${(i + 1) * 1.2}rem">` +
      `<span class="lt-ic">📁</span>${esc(name)} <span class="muted">— sub-folder ${i + 1}</span></div>`);
  });
  const filesIndent = (d.chain.length + 1) * 1.2;
  (d.files || []).forEach((f) => {
    lines.push(`<div class="lt-row lt-file" style="padding-left:${filesIndent}rem">` +
      `<span class="lt-ic">📄</span>${esc(f)}</div>`);
  });
  const note = d.levels === 0
    ? `Example: files sit directly in the source folder.`
    : `Example data path at ${d.levels} folder level${d.levels === 1 ? "" : "s"} deep.`;
  box.innerHTML = `<div class="layout-tree">${lines.join("")}</div><div class="muted lt-note">${note}</div>`;
}

function renderFileExamples() {
  const box = $("#b-file-examples");
  if (!box) return;
  const d = builderLayout;
  if (!d || d.error || !(d.files || []).length) { box.innerHTML = ""; return; }
  const sep = $("#b-separator").value || "_";
  const rows = d.files.map((f) => {
    const base = f.replace(/\.[^.]+$/, "");
    const parts = sep ? base.split(sep) : [base];
    const chips = parts.map((p) => `<span class="chunk">${esc(p)}</span>`)
      .join(`<span class="sep">${esc(sep)}</span>`);
    return `<div class="fe-row"><code>${esc(f)}</code>` +
      `<div class="fe-split">${chips} <span class="muted">(${parts.length} chunk${parts.length > 1 ? "s" : ""})</span></div></div>`;
  }).join("");
  box.innerHTML =
    `<div class="muted">Example files split on "<code>${esc(sep)}</code>" — give one metadata label per chunk:</div>${rows}`;
}

$("#b-staging").addEventListener("change", loadLayout);
$("#b-separator").addEventListener("input", () => { renderFileExamples(); renderOverrideJSON(); });
$("#b-fields").addEventListener("input", renderOverrideJSON);
bInstrument.addEventListener("change", () => { if ($("#b-staging").value.trim()) loadLayout(); });

// ---- assemble the override dict ----
function builderOverrides() {
  const ov = {};
  // file-name labels -> positional filename_parse (regex dropped from the GUI)
  const fields = $("#b-fields").value.split(",").map((s) => s.trim()).filter(Boolean);
  if (fields.length) {
    ov["auto_discover.filename_parse"] = { separator: $("#b-separator").value || "_", fields };
  }
  // folder levels -> path_parse; pin a recursive pattern so deep files are found
  if ($$("#b-levels .level-label").length > 0) {
    ov["auto_discover.path_parse"] = { levels: builderLevelLabels() };
    ov["auto_discover.pattern"] = "**/*.czi";
  }
  const filter = builderFilterUI.collect();
  if (Object.keys(filter).length) ov["auto_discover.filter"] = filter;

  // values to record. gap fields are SELF-CONTAINED: emitted explicitly even when
  // blank (an explicit "" overrides the template default -> a real blank the
  // Runner prompts for). Non-gap fields are emitted only when filled (else they
  // fall back to the template default).
  REQUIRED_FIELDS.forEach((f) => {
    let v;
    if (f.type === "select") {
      const sel = builderSelects[f.key];
      v = sel ? sel.value : "";
    } else {
      const tf = builderFields[f.key];
      v = tf ? tf.serialize().trim() : "";
    }
    if (v || f.gap) ov[f.key] = v;
  });

  ov["ingest.auto_create_projects"] = $("#b-auto-create").checked;
  return ov;
}

function renderOverrideJSON() {
  $("#b-override-json").textContent = JSON.stringify(builderOverrides(), null, 2);
}

// ---- live "→ example" lines for the value boxes ----
function updateBuilderExamples() {
  const ctx = Object.assign({}, builderDiscoveredRow);
  const synth = {
    instrument: bInstrument.value,
    acq_id: `ACQ-YYYYMMDD-${bInstrument.value}-001`,
    acq_date: "YYYYMMDD",
    original_name: ctx.filename || ctx.folder_name || "<original_name>",
    sample_id: "<sample_id>",
  };
  $$("#b-required .req-row").forEach((row) => {
    const tf = builderFields[row.dataset.key];
    const ex = row.querySelector(".example");
    if (!tf || !ex) return;
    const val = tf.serialize();
    if (!val.trim()) { ex.textContent = ""; ex.classList.remove("bad"); return; }
    const { text, unresolved } = resolveExample(val, ctx, synth);
    ex.textContent = "→ " + text;
    ex.classList.toggle("bad", unresolved);
  });
}

function resolveExample(template, ctx, synth) {
  if (!template) return { text: "", unresolved: false };
  let unresolved = false;
  const out = template.replace(/\$\{([^}]+)\}/g, (m, ref) => {
    ref = ref.trim();
    if (ref.startsWith("discovered.")) {
      const k = ref.slice("discovered.".length);
      if (k in ctx) return ctx[k];
      unresolved = true; return m;
    }
    if (ref in synth) return synth[ref];
    if (ref in ctx) return ctx[ref];
    unresolved = true; return m;
  });
  return { text: out, unresolved };
}

// ---- "Show the fields this produces" (section 1) ----
async function refreshGrid() {
  $("#b-errors").textContent = "";
  $("#b-dropped").innerHTML = "";
  $("#b-grid-wrap").innerHTML = "Loading…";
  renderOverrideJSON();
  try {
    const data = await postJSON("/api/discovered", {
      instrument: bInstrument.value,
      overrides: builderOverrides(),
      staging_path: $("#b-staging").value,
      nas_root: nasRoot(),
      limit: 25,
    });
    builderKeys = data.keys || [];
    builderDiscoveredRow = data.rows[0] ? data.rows[0].discovered : {};
    renderDropped($("#b-dropped"), data);   // path-level / parse problems, up top
    if (!data.rows.length) {
      $("#b-grid-wrap").innerHTML =
        "<p class='muted'>No files parsed. Check the folder levels + labels against your example folder (the box above lists why files were skipped).</p>";
    } else {
      const head = "<tr><th>file</th>" +
        builderKeys.map((k) => `<th>${esc(tfHumanizeRef(k))}</th>`).join("") + "</tr>";
      const rows = data.rows.map((row) =>
        "<tr><td>" + esc(row.original_name) + "</td>" +
        builderKeys.map((k) => `<td>${esc(row.discovered[k] ?? "")}</td>`).join("") +
        "</tr>").join("");
      $("#b-grid-wrap").innerHTML = `<table>${head}${rows}</table>`;
    }
    // palette of friendly field chips + resolver extras; refresh dependent UIs
    renderPalette($("#b-palette"),
      paletteEntries(builderKeys, ["${acq_id}", "${acq_date}", "${original_name}"]),
      builderFields["registry.sample_id"]);
    $("#b-palette-hint").hidden = !builderKeys.length;
    builderFilterUI.refresh();
    updateBuilderExamples();
  } catch (e) {
    $("#b-grid-wrap").innerHTML = "";
    $("#b-errors").textContent = e.message;
  }
}
$("#b-refresh-grid").addEventListener("click", refreshGrid);

// ---- load template defaults into the builder ----
function setTF(key, val) {
  const tf = builderFields[key];
  if (!tf) return;
  let s = (val == null) ? "" : String(val);
  if (/^<.*>$/.test(s.trim())) s = "";   // a "<set per batch>" placeholder -> empty
  tf.setValue(s);
}
function setSelect(key, val) {
  const sel = builderSelects[key];
  if (sel) sel.value = (val == null) ? "" : String(val);  // non-vocab -> stays skip
}
async function loadTemplateDefaults() {
  $("#b-errors").textContent = "";
  try {
    const t = await getJSON(`/api/template?instrument=${encodeURIComponent(bInstrument.value)}`);
    if (t.error) { $("#b-errors").textContent = t.error; return; }
    const ad = t.auto_discover || {};
    const fp = ad.filename_parse || {};
    if (fp.regex) {
      $("#b-fields").value = "";
      $("#b-errors").textContent =
        "Note: this template parses names with a regex, which the builder doesn't edit. " +
        "The values below are still loaded; describe the name layout with the separator + labels above to change it.";
    } else {
      $("#b-separator").value = fp.separator || "_";
      $("#b-fields").value = (fp.fields || []).join(", ");
    }
    // folder levels
    const levels = (ad.path_parse || {}).levels || [];
    $("#b-levels-count").value = levels.length;
    renderLevels();
    $$("#b-levels .level-label").forEach((inp, i) => { if (levels[i]) inp.value = levels[i]; });
    // filter
    builderFilterUI.clear();
    Object.entries(ad.filter || {}).forEach(([k, v]) => builderFilterUI.addRow(k, v));
    // values to record
    const reg = t.registry || {};
    setTF("registry.researcher", reg.researcher);
    setTF("operator", t.operator);
    setTF("registry.sample_id", reg.sample_id);
    setSelect("registry.sample_type", reg.sample_type);
    setTF("registry.acquisition_datetime", reg.acquisition_datetime);
    setTF("registry.project_hint", reg.project_hint);
    setTF("registry.session_id", reg.session_id);
    setTF("registry.notes", reg.notes);
    setTF("link_filename", t.link_filename);
    if (!builderFields["link_filename"].serialize().trim()) {
      builderFields["link_filename"].setValue("${original_name}");  // never blank
    }
    $("#b-auto-create").checked = !!(t.ingest || {}).auto_create_projects;
    renderOverrideJSON();
    updateBuilderExamples();
  } catch (e) {
    $("#b-errors").textContent = e.message;
  }
}
$("#b-load-template").addEventListener("click", loadTemplateDefaults);
// Start from the instrument's convention so blanking a field is a DELIBERATE
// choice (-> prompt in the Runner), not the default state of an empty builder.
bInstrument.addEventListener("change", loadTemplateDefaults);

// ---- start from an existing recipe (builder) ----
// Apply a saved recipe's flat override dict onto the builder widgets, ON TOP of
// the already-loaded template defaults — so the builder shows the recipe's
// EFFECTIVE config: template values for anything the recipe doesn't override, and
// the recipe's own values (including a deliberate blank gap -> "prompt in runner")
// for what it does. Only keys actually present in the override dict are touched,
// which mirrors how config_builder merges template + overrides at ingest time.
function applyOverridesToBuilder(ov) {
  ov = ov || {};
  if ("auto_discover.filename_parse" in ov) {
    const fp = ov["auto_discover.filename_parse"] || {};
    if (fp.regex) {
      $("#b-fields").value = "";
      $("#b-errors").textContent =
        "Note: this recipe parses names with a regex, which the builder doesn't edit. " +
        "Describe the name layout with the separator + labels above to change it.";
    } else {
      $("#b-separator").value = fp.separator || "_";
      $("#b-fields").value = (fp.fields || []).join(", ");
    }
  }
  if ("auto_discover.path_parse" in ov) {
    const levels = (ov["auto_discover.path_parse"] || {}).levels || [];
    $("#b-levels-count").value = levels.length;
    renderLevels();
    $$("#b-levels .level-label").forEach((inp, i) => { if (levels[i]) inp.value = levels[i]; });
  }
  if ("auto_discover.filter" in ov) {
    builderFilterUI.clear();
    Object.entries(ov["auto_discover.filter"] || {}).forEach(([k, v]) => builderFilterUI.addRow(k, v));
  }
  REQUIRED_FIELDS.forEach((f) => {
    if (!(f.key in ov)) return;                 // omitted -> keep the template default
    if (f.type === "select") setSelect(f.key, ov[f.key]);
    else setTF(f.key, ov[f.key]);               // explicit "" -> a real blank (gap)
  });
  if ("ingest.auto_create_projects" in ov) {
    $("#b-auto-create").checked = !!ov["ingest.auto_create_projects"];
  }
  renderOverrideJSON();
  updateBuilderExamples();
}

const bRecipe = $("#b-recipe");
let builderRecipesCache = [];

async function loadBuilderRecipes() {
  const cur = bRecipe.value;
  try {
    builderRecipesCache = await getJSON(
      `/api/recipes?instrument=${encodeURIComponent(bInstrument.value)}`);
  } catch (e) { builderRecipesCache = []; }
  bRecipe.innerHTML = '<option value="">— none —</option>' +
    builderRecipesCache.map((r) =>
      `<option value="${esc(r.file)}">${esc(r.name)}</option>`).join("");
  // Keep the selection if it survived a reload (e.g. after a re-save).
  if (builderRecipesCache.some((r) => r.file === cur)) bRecipe.value = cur;
}

async function loadRecipeIntoBuilder() {
  const rec = builderRecipesCache.find((r) => r.file === bRecipe.value);
  if (!rec) {
    $("#b-save-status").innerHTML = '<span class="muted">Pick a recipe to load first.</span>';
    return;
  }
  await loadTemplateDefaults();                   // base = the locked instrument convention
  applyOverridesToBuilder(rec.overrides || {});   // overlay the recipe on top
  $("#b-recipe-name").value = rec.name || "";
  $("#b-recipe-desc").value = rec.description || "";
  $("#b-save-status").innerHTML =
    `<span class="new">Loaded</span> <code>${esc(rec.file)}</code> — edit and re-save ` +
    "(keep the name to overwrite it, or rename to save a copy).";
  if ($("#b-staging").value.trim()) loadLayout();
}
$("#b-load-recipe").addEventListener("click", loadRecipeIntoBuilder);
// Refresh the builder's recipe list when the instrument changes (it's filtered
// by instrument, same as the runner's).
bInstrument.addEventListener("change", loadBuilderRecipes);

// ---- "Preview example" (section 3) ----
async function builderPreview() {
  $("#b-map-summary").innerHTML = "";
  $("#b-map-dropped").innerHTML = "";
  $("#b-map-table-wrap").innerHTML = "Previewing…";
  renderOverrideJSON();
  try {
    const data = await postJSON("/api/preview", {
      instrument: bInstrument.value,
      overrides: builderOverrides(),
      staging_path: $("#b-staging").value,
      nas_root: nasRoot(),
    });
    renderSummary($("#b-map-summary"), data);
    renderDropped($("#b-map-dropped"), data);
    if (data.blocking_errors && data.blocking_errors.length) {
      $("#b-errors").textContent = data.blocking_errors.join("\n");
    }
    $("#b-map-table-wrap").innerHTML = renderCasesTable(data.cases);
    if (data.cases[0]) { builderDiscoveredRow = data.cases[0].discovered; updateBuilderExamples(); }
  } catch (e) {
    $("#b-map-table-wrap").innerHTML = "";
    $("#b-errors").textContent = e.message;
  }
}
$("#b-preview").addEventListener("click", builderPreview);

// ---- save recipe ----
$("#b-save").addEventListener("click", async () => {
  $("#b-save-status").textContent = "";
  try {
    const data = await postJSON("/api/save_recipe", {
      instrument: bInstrument.value,
      name: $("#b-recipe-name").value,
      description: $("#b-recipe-desc").value,
      overrides: builderOverrides(),
    });
    $("#b-save-status").innerHTML =
      `<span class="new">Saved</span> ${esc(data.file)} → ${esc(data.path)}`;
    if (rInstrument.value === bInstrument.value) loadRecipes();
    loadBuilderRecipes();   // surface the new/updated recipe in the builder picker
  } catch (e) {
    $("#b-save-status").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
  }
});

// ---- initial builder paint ----
buildRequiredGrid();
renderLevels();
renderOverrideJSON();
updateBuilderExamples();
loadTemplateDefaults();   // seed from the default instrument's convention
loadBuilderRecipes();     // populate the "start from a saved recipe" picker
