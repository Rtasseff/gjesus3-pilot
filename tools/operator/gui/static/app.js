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

function renderSummary(el, data) {
  el.innerHTML =
    `<span class="new">${data.n_new} new</span> · ` +
    `<span class="skip">${data.n_skipped} already-ingested</span> · ` +
    `${data.n_matched} matched · pattern <code>${esc(data.pattern)}</code>`;
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
  $("#r-table-wrap").innerHTML = "Previewing…";
  $("#r-ingest").disabled = true;
  try {
    const data = await postJSON("/api/preview", {
      instrument: rInstrument.value,
      overrides: currentRecipeOverrides(),
      staging_path: $("#r-staging").value,
      nas_root: nasRoot(),
    });
    lastRunnerCases = data.cases;
    renderSummary($("#r-summary"), data);
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
        overrides: currentRecipeOverrides(),
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

// ================================================================ BUILDER
const bInstrument = $("#b-instrument");

// ---- parse-mode toggle ----
$("#b-parse-mode").addEventListener("change", () => {
  const regex = $("#b-parse-mode").value === "regex";
  $("#b-positional").hidden = regex;
  $("#b-regex").hidden = !regex;
});

// ---- build the override dict from the builder form ----
function builderOverrides() {
  const ov = {};
  const mode = $("#b-parse-mode").value;
  const source = $("#b-source").value;

  if (mode === "positional") {
    const fields = $("#b-fields").value.split(",").map((s) => s.trim()).filter(Boolean);
    const fp = { separator: $("#b-separator").value || "_", fields };
    if (source === "parent_name") fp.source = "parent_name";
    if (fields.length) ov["auto_discover.filename_parse"] = fp;
  } else {
    const pat = $("#b-regex-pat").value.trim();
    if (pat) {
      const fp = { regex: pat };
      fp.source = source; // regex usually pairs with a source choice
      ov["auto_discover.filename_parse"] = fp;
    }
  }

  const levels = $("#b-path-levels").value.split(",").map((s) => s.trim()).filter(Boolean);
  if (levels.length) ov["auto_discover.path_parse"] = { levels };

  const filterPairs = {};
  $("#b-filter").value.split(",").map((s) => s.trim()).filter(Boolean).forEach((p) => {
    const eq = p.indexOf("=");
    if (eq > 0) filterPairs[p.slice(0, eq).trim()] = p.slice(eq + 1).trim();
  });
  if (Object.keys(filterPairs).length) ov["auto_discover.filter"] = filterPairs;

  // field mappings
  $$(".b-map").forEach((inp) => {
    const v = inp.value.trim();
    if (v) ov[inp.dataset.key] = v;
  });

  ov["ingest.auto_create_projects"] = $("#b-auto-create").checked;
  return ov;
}

function renderOverrideJSON() {
  $("#b-override-json").textContent = JSON.stringify(builderOverrides(), null, 2);
}

// ---- discovered.* live grid (a) ----
async function refreshGrid() {
  $("#b-errors").textContent = "";
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
    const keys = data.keys || [];
    if (!data.rows.length) {
      $("#b-grid-wrap").innerHTML = "<p class='muted'>No files matched / parsed. Adjust the parse rules.</p>";
    } else {
      const head = "<tr><th>original_name</th>" +
        keys.map((k) => `<th>discovered.${esc(k)}</th>`).join("") + "</tr>";
      const rows = data.rows.map((row) =>
        "<tr><td>" + esc(row.original_name) + "</td>" +
        keys.map((k) => `<td>${esc(row.discovered[k] ?? "")}</td>`).join("") +
        "</tr>").join("");
      $("#b-grid-wrap").innerHTML = `<table>${head}${rows}</table>`;
    }
    // refresh the chip palette + live examples off the first row
    buildChips(keys);
    updateExamples(data.rows[0] ? data.rows[0].discovered : {});
  } catch (e) {
    $("#b-grid-wrap").innerHTML = "";
    $("#b-errors").textContent = e.message;
  }
}
$("#b-refresh-grid").addEventListener("click", refreshGrid);

// ---- token chips (b) ----
let lastDiscoveredKeys = [];
function buildChips(keys) {
  lastDiscoveredKeys = keys.slice();
  const tokens = keys.map((k) => `\${discovered.${k}}`)
    .concat(["${instrument}", "${acq_id}", "${acq_date}", "${original_name}", "${sample_id}"]);
  $("#b-chips").innerHTML = tokens.map((t) =>
    `<span class="chip" data-token="${esc(t)}">${esc(t)}</span>`).join("");
  $$("#b-chips .chip").forEach((chip) => {
    chip.addEventListener("click", () => insertToken(chip.dataset.token));
  });
}

let focusedMapInput = null;
$$(".b-map").forEach((inp) => {
  inp.addEventListener("focus", () => { focusedMapInput = inp; });
  inp.addEventListener("input", () => {
    renderOverrideJSON();
    updateExamples(null); // re-evaluate with last-known discovered row
  });
});

function insertToken(token) {
  const inp = focusedMapInput || $('.b-map[data-key="link_filename"]');
  if (!inp) return;
  const start = inp.selectionStart ?? inp.value.length;
  const end = inp.selectionEnd ?? inp.value.length;
  inp.value = inp.value.slice(0, start) + token + inp.value.slice(end);
  inp.focus();
  const pos = start + token.length;
  inp.setSelectionRange(pos, pos);
  renderOverrideJSON();
  updateExamples(null);
}

// ---- client-side example resolver (best-effort, mirrors ${...} interpolation)
let lastDiscoveredRow = {};
function updateExamples(discoveredRow) {
  if (discoveredRow) lastDiscoveredRow = discoveredRow;
  const ctx = Object.assign({}, lastDiscoveredRow);
  // synthetic example values for resolver-supplied tokens
  const synth = {
    instrument: bInstrument.value,
    acq_id: `ACQ-YYYYMMDD-${bInstrument.value}-001`,
    acq_date: "YYYYMMDD",
    original_name: ctx.filename || ctx.folder_name || "<original_name>",
    sample_id: "<sample_id>",
  };
  $$(".b-map").forEach((inp) => {
    const ex = inp.parentElement.querySelector(".example");
    if (!ex) return;
    const { text, unresolved } = resolveExample(inp.value, ctx, synth);
    if (!inp.value.trim()) { ex.textContent = ""; ex.classList.remove("bad"); return; }
    ex.textContent = "→ " + text;
    ex.classList.toggle("bad", unresolved);
  });
}

function resolveExample(template, ctx, synth) {
  if (!template) return { text: "", unresolved: false };
  let unresolved = false;
  // ${discovered.x} | ${x}
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

// ---- load template defaults into the builder form ----
async function loadTemplateDefaults() {
  $("#b-errors").textContent = "";
  try {
    const t = await getJSON(`/api/template?instrument=${encodeURIComponent(bInstrument.value)}`);
    if (t.error) { $("#b-errors").textContent = t.error; return; }
    const ad = t.auto_discover || {};
    const fp = ad.filename_parse || {};
    if (fp.regex) {
      $("#b-parse-mode").value = "regex";
      $("#b-regex-pat").value = fp.regex;
    } else {
      $("#b-parse-mode").value = "positional";
      $("#b-separator").value = fp.separator || "_";
      $("#b-fields").value = (fp.fields || []).join(", ");
    }
    $("#b-parse-mode").dispatchEvent(new Event("change"));
    $("#b-source").value = fp.source || "name";
    $("#b-path-levels").value = ((ad.path_parse || {}).levels || []).join(", ");
    $("#b-filter").value = Object.entries(ad.filter || {})
      .map(([k, v]) => `${k}=${v}`).join(", ");

    const reg = t.registry || {};
    setMap("registry.project_hint", reg.project_hint);
    setMap("registry.sample_id", reg.sample_id);
    setMap("registry.operator", reg.operator);
    setMap("registry.notes", reg.notes);
    setMap("link_filename", t.link_filename);
    $("#b-auto-create").checked = !!(t.ingest || {}).auto_create_projects;
    renderOverrideJSON();
  } catch (e) {
    $("#b-errors").textContent = e.message;
  }
}
function setMap(key, val) {
  const inp = $(`.b-map[data-key="${key}"]`);
  if (inp) inp.value = val == null ? "" : String(val);
}
$("#b-load-template").addEventListener("click", loadTemplateDefaults);

// ---- builder full preview (b) ----
async function builderPreview() {
  $("#b-map-summary").innerHTML = "";
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
    if (data.blocking_errors && data.blocking_errors.length) {
      $("#b-errors").textContent = data.blocking_errors.join("\n");
    }
    $("#b-map-table-wrap").innerHTML = renderCasesTable(data.cases);
    if (data.cases[0]) updateExamples(data.cases[0].discovered);
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
    // refresh the runner recipe dropdown so it shows up immediately
    if (rInstrument.value === bInstrument.value) loadRecipes();
  } catch (e) {
    $("#b-save-status").innerHTML = `<span class="bad">${esc(e.message)}</span>`;
  }
});

// initial builder paint
renderOverrideJSON();
