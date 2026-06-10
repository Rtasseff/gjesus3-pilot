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
  } catch (e) { setNasStatus(false); }
}
$("#nas-save").addEventListener("click", saveNas);
getJSON("/api/nas_root").then((d) => { setNasStatus(d.valid); });

function nasRoot() { return nasInput.value.trim(); }

// ---------------------------------------------------------------- folder browse
// A browser <input> can't return a real local path, but this is a LOCAL app, so
// the server pops the OS-native folder picker and hands the path back here.
async function browseInto(input, title) {
  if (!input) return;
  try {
    const data = await postJSON("/api/browse_folder", {
      initial: input.value.trim(), title: title || "",
    });
    if (data.path) {
      input.value = data.path;
      input.dispatchEvent(new Event("input"));
      input.dispatchEvent(new Event("change"));
    } else if (data.error) {
      input.placeholder = data.error;   // headless box: operator types it
    }
  } catch (e) { /* non-fatal — typing the path still works */ }
}
$("#nas-browse").addEventListener("click", async () => {
  await browseInto(nasInput, "Select the destination NAS root (gjesus3-data)");
  if (nasInput.value.trim()) saveNas();
});
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
}
rInstrument.addEventListener("change", loadRecipes);
rRecipe.addEventListener("change", () => {
  const rec = recipesCache.find((r) => r.file === rRecipe.value);
  $("#r-recipe-desc").textContent = rec ? rec.description : "";
});
loadRecipes();

function currentRecipeOverrides() {
  const rec = recipesCache.find((r) => r.file === rRecipe.value);
  return rec ? (rec.overrides || {}) : {};
}

// ---- per-run study metadata (condition block) ----------------------------
// Shown only for instruments whose template carries a condition: block
// (AxioScan tissue; not the cell modes). Values become condition.* overrides
// applied to EVERY acquisition in the run — the GUI equivalent of the
// ni/mri-ingest --is-control / --disease-* flags.
const rIsControl = $("#r-is-control");
let runnerDiscoveredRow = {};
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

// The Researcher box -> registry.researcher (the experiment owner). Blank = use
// the template default (cells resolve it from discovered.researcher; AxioScan
// has only a placeholder, so it should be set here).
function runnerResearcher() {
  const el = $("#r-researcher");
  const v = (el && el.value || "").trim();
  return v ? { "registry.researcher": v } : {};
}

// Recipe overrides + per-run researcher + condition (later wins on overlap).
function runnerOverrides() {
  return Object.assign({}, currentRecipeOverrides(), runnerResearcher(),
                       runnerMetaOverrides());
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

// Files dropped by a parse/filter/validate error — shown prominently, not buried
// in the collapsed log, so the operator sees WHY nothing ingested (#6).
function renderDropped(el, data) {
  if (!el) return;
  const dropped = data.dropped || [];
  if (!dropped.length) { el.innerHTML = ""; return; }
  const shown = dropped.slice(0, 50).map((d) =>
    `<li><code>${esc(d.name)}</code> — ${esc(d.reason)}</li>`).join("");
  const more = dropped.length > 50
    ? `<li>…and ${dropped.length - 50} more</li>` : "";
  el.innerHTML =
    `<h4>${dropped.length} file(s) skipped because of a parse / filter error ` +
    `— these are NOT already ingested:</h4><ul>${shown}${more}</ul>`;
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
  const dry = $("#r-dry").checked;
  $("#r-log-wrap").hidden = false;
  const logEl = $("#r-log");
  logEl.textContent = "";
  $("#r-result").innerHTML = "";
  $("#r-ingest").disabled = true;
  $("#r-preview").disabled = true;

  const rec = recipesCache.find((r) => r.file === rRecipe.value);
  const recipePath = rec ? `tools/operator/recipes/${rec.file}` : "";

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

// "3 · Set the values to record" — the values we have a priority to capture.
// ★ high-priority = the registry person columns + sample id + study metadata.
const REQUIRED_FIELDS = [
  { key: "registry.researcher",           label: "Researcher",       star: true, hint: "who ran the study" },
  { key: "operator",                      label: "Operator",         star: true, hint: "who ran the equipment" },
  { key: "registry.sample_id",            label: "Sample ID",        star: true },
  { key: "_animal_role",                  label: "Animal role",      star: true, type: "select" },
  { key: "condition.disease_model",       label: "disease_model",    star: true, caseOnly: true },
  { key: "condition.disease_state",       label: "disease_state",    star: true, caseOnly: true },
  { key: "registry.sample_type",          label: "Sample type" },
  { key: "registry.acquisition_datetime", label: "Acquisition date" },
  { key: "registry.project_hint",         label: "Project hint" },
  { key: "registry.session_id",           label: "Session ID" },
  { key: "registry.notes",                label: "Notes" },
  { key: "link_filename",                 label: "Project link name" },
];

// Build the "values to record" rows once (token-fields + the Animal-role select).
function buildRequiredGrid() {
  const grid = $("#b-required");
  grid.innerHTML = "";
  REQUIRED_FIELDS.forEach((f) => {
    const row = document.createElement("div");
    row.className = "req-row" + (f.caseOnly ? " case-only" : "");
    row.dataset.key = f.key;
    const star = f.star ? '<span class="star">★</span> ' : "";
    const hint = f.hint ? ` <span class="muted">— ${esc(f.hint)}</span>` : "";
    const lab = document.createElement("div");
    lab.className = "req-label";
    lab.innerHTML = `${star}${esc(f.label)}${hint}`;
    const val = document.createElement("div");
    val.className = "req-val";
    if (f.type === "select") {
      val.innerHTML =
        `<select id="b-is-control">` +
        `<option value="">— skip (set per run) —</option>` +
        `<option value="true">control — no disease model / perturbation / intervention</option>` +
        `<option value="false">case</option></select>`;
    } else {
      const tfEl = document.createElement("div");
      const ex = document.createElement("span");
      ex.className = "example";
      val.append(tfEl, ex);
      const tf = new TokenField(tfEl, {
        onChange: () => { renderOverrideJSON(); updateBuilderExamples(); },
      });
      builderFields[f.key] = tf;
    }
    row.append(lab, val);
    grid.appendChild(row);
  });
  const ic = $("#b-is-control");
  if (ic) {
    ic.addEventListener("change", () => { toggleCaseRows(); renderOverrideJSON(); });
    toggleCaseRows();
  }
}
function toggleCaseRows() {
  const show = $("#b-is-control") && $("#b-is-control").value === "false";
  $$("#b-required .case-only").forEach((r) => { r.hidden = !show; });
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
$("#b-levels-count").addEventListener("input", renderLevels);

// ---- filter rows (section 2) ----
function filterFieldOptions(selected) {
  if (!builderKeys.length) return `<option value="">(show fields first)</option>`;
  return `<option value="">— pick a field —</option>` + builderKeys.map((k) =>
    `<option value="${esc(k)}"${k === selected ? " selected" : ""}>${esc(tfHumanizeRef(k))}</option>`).join("");
}
function addFilterRow(field, value) {
  const wrap = $("#b-filter-rows");
  const row = document.createElement("div");
  row.className = "filter-row";
  const sel = document.createElement("select");
  sel.className = "b-filter-field";
  sel.innerHTML = filterFieldOptions(field);
  const eq = document.createElement("span"); eq.textContent = "=";
  const val = document.createElement("input");
  val.type = "text"; val.className = "b-filter-val"; val.placeholder = "value";
  if (value != null) val.value = value;
  const rm = document.createElement("button");
  rm.type = "button"; rm.className = "rm"; rm.textContent = "×"; rm.title = "remove";
  rm.addEventListener("click", () => { row.remove(); renderOverrideJSON(); });
  [sel, val].forEach((el) => el.addEventListener("input", renderOverrideJSON));
  row.append(sel, eq, val, rm);
  wrap.appendChild(row);
}
function refreshFilterFieldOptions() {
  $$("#b-filter-rows .b-filter-field").forEach((sel) => {
    const cur = sel.value;
    sel.innerHTML = filterFieldOptions(cur);
    sel.value = cur;
  });
}
function builderFilter() {
  const out = {};
  $$("#b-filter-rows .filter-row").forEach((row) => {
    const k = row.querySelector(".b-filter-field").value.trim();
    const v = row.querySelector(".b-filter-val").value.trim();
    if (k) out[k] = v;
  });
  return out;
}
$("#b-filter-add").addEventListener("click", () => addFilterRow());

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
  const filter = builderFilter();
  if (Object.keys(filter).length) ov["auto_discover.filter"] = filter;

  // values to record
  const ic = $("#b-is-control") ? $("#b-is-control").value : "";
  REQUIRED_FIELDS.forEach((f) => {
    if (f.type === "select") return;
    if (f.caseOnly && ic !== "false") return;   // disease only meaningful for a case
    const tf = builderFields[f.key];
    const v = tf ? tf.serialize().trim() : "";
    if (v) ov[f.key] = v;
  });
  if (ic === "true") ov["condition.is_control"] = true;
  else if (ic === "false") ov["condition.is_control"] = false;

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
    refreshFilterFieldOptions();
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
    $("#b-filter-rows").innerHTML = "";
    Object.entries(ad.filter || {}).forEach(([k, v]) => addFilterRow(k, v));
    // values to record
    const reg = t.registry || {};
    setTF("registry.researcher", reg.researcher);
    setTF("operator", t.operator);
    setTF("registry.sample_id", reg.sample_id);
    setTF("registry.sample_type", reg.sample_type);
    setTF("registry.acquisition_datetime", reg.acquisition_datetime);
    setTF("registry.project_hint", reg.project_hint);
    setTF("registry.session_id", reg.session_id);
    setTF("registry.notes", reg.notes);
    setTF("link_filename", t.link_filename);
    $("#b-auto-create").checked = !!(t.ingest || {}).auto_create_projects;
    renderOverrideJSON();
    updateBuilderExamples();
  } catch (e) {
    $("#b-errors").textContent = e.message;
  }
}
$("#b-load-template").addEventListener("click", loadTemplateDefaults);

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
  } catch (e) {
    $("#b-save-status").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
  }
});

// ---- initial builder paint ----
buildRequiredGrid();
renderLevels();
renderOverrideJSON();
