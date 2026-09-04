"use strict";

/* mri.js — the simple MRI (Bruker ParaVision) ingest page (/mri).
 *
 * A deliberately-small sibling of app.js (the microscopy GUI). MRI has ONE
 * locked convention (the mri_bruker template), so there is no recipe/builder
 * UI — the operator only sets who ran the scanner, the destination project, and
 * (when linking) the project link name. Everything else is template-locked.
 *
 * Talks to: /api/nas_root, /api/listdir (shared), and /api/mri/preview +
 * /api/mri/ingest (MRI-only). Reuses tokenfield.js for the link-name field.
 */

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
    // Kept identical to app.js's copy on purpose: status + body ride along on
    // the Error so a caller can act on a structured refusal. No endpoint this
    // page calls needs it today (recipes are microscopy-only) — the two copies
    // are mirrored so neither becomes the odd one out.
    const err = new Error((data && data.error) || `HTTP ${r.status}`);
    err.status = r.status;
    err.data = data;
    throw err;
  }
  return data;
}

function getJSON(url) { return fetch(url).then((r) => r.json()); }

// ---------------------------------------------------------------- NAS root
const nasInput = $("#nas-root");
const nasStatus = $("#nas-status");

let nasValid = false;   // gates the pull — no point pulling to an unusable NAS
function setNasStatus(valid) {
  nasValid = !!valid;
  nasStatus.textContent = valid ? "OK" : "not found";
  nasStatus.className = "pill " + (valid ? "ok" : "no");
}
async function refreshNas() {
  try {
    const d = await getJSON("/api/nas_root");
    if (d.nas_root && !nasInput.value) nasInput.value = d.nas_root;
    setNasStatus(d.valid);
  } catch (e) { /* non-fatal */ }
}
async function saveNas() {
  try {
    const d = await postJSON("/api/nas_root", { nas_root: nasInput.value });
    setNasStatus(d.valid);
  } catch (e) { setNasStatus(false); }
}
$("#nas-save").addEventListener("click", saveNas);
nasInput.addEventListener("keydown", (e) => { if (e.key === "Enter") saveNas(); });

// ---------------------------------------------------------------- folder browser
// The modal itself (list, navigation, reversible name order) is the SHARED
// component in static/folder_browser.js, loaded by both pages; it exposes
// browseInto(input, title, onPick). This page only wires its own buttons to it.
$("#nas-browse").addEventListener("click", () =>
  browseInto(nasInput, "Select the destination — the RDM System root (gjesus3-data)", () => saveNas()));

// ---------------------------------------------------------------- link field
const MRI = window.MRI || {};
// Bare names of the fixed resolver tokens offered as palette chips (instrument,
// operator, …). Used by resolveExample() so a valid token isn't flagged
// "unresolved" just because this preview can't compute its value.
const LINK_TOKEN_NAMES = new Set(
  (MRI.paletteExtras || []).map((t) => t.replace(/^\$\{|\}$/g, "")));
const linkField = new TokenField($("#link-field"), { onChange: () => updateLinkExample() });
linkField.setValue(MRI.linkDefault || "");
renderPalette($("#link-palette"),
  paletteEntries(MRI.paletteKeys || [], MRI.paletteExtras || []), linkField);
$("#link-reset").addEventListener("click", () => { linkField.setValue(MRI.linkDefault || ""); updateLinkExample(); });

// Live "this is what it will look like" example under a field, mirroring the
// microscopy runner. Resolves ${discovered.*}/${synth} against the first
// previewed scan, set after each preview. Before a preview runs there's no real
// scan to resolve against, so it stays blank. Shared by the link-name field and
// the project-name field.
let sampleCtx = null;   // {ctx: {discovered...}, synth: {sample_id,...}}

function resolveExample(template, sample) {
  if (!template || !sample) return { text: "", unresolved: false };
  let unresolved = false;
  const text = template.replace(/\$\{([^}]+)\}/g, (mm, ref) => {
    ref = ref.trim();
    if (ref.startsWith("discovered.")) {
      const k = ref.slice("discovered.".length);
      if (k in sample.ctx) return sample.ctx[k];
      unresolved = true; return mm;
    }
    if (ref in sample.synth) return sample.synth[ref];
    // A fixed resolver token that resolves at ingest but which this preview
    // can't compute — show a <placeholder>, don't flag it as unresolved.
    if (LINK_TOKEN_NAMES.has(ref)) return "<" + ref + ">";
    unresolved = true; return mm;
  });
  return { text, unresolved };
}

function updateLinkExample() {
  const el = $("#link-example");
  if (!el) return;
  const tpl = linkField.serialize();
  if (!sampleCtx) {
    el.textContent = tpl ? "Preview to see an example link name." : "";
    el.classList.remove("bad");
    return;
  }
  const { text, unresolved } = resolveExample(tpl, sampleCtx);
  el.textContent = text ? "e.g.  " + text : "";
  el.classList.toggle("bad", unresolved);
}

// ---------------------------------------------------------------- project name
const projectMode = $("#project-mode");
const projectFixedWrap = $("#project-fixed-wrap");
const linkFieldset = $("#link-fieldset");
const projectNote = $("#project-note");

// The destination project is built exactly like the link name: fixed text plus
// ${discovered.*} chips, resolved PER SCAN. That is the whole point -- an
// operator pulling a week's work off the scanner has no single static project
// name to type, so a run spanning several protocols needs the name to come from
// each scan's own metadata. The engine has always supported this (the template's
// own default is `AE-biomaGUNE-${discovered.project_code}`); until now only the
// link-name field exposed it.
//
// spacesToHyphens: a project's name IS its folder name (05_PROJECTS "Project
// reference model"), so a typed space becomes a hyphen in front of the operator
// rather than being silently rewritten downstream.
const projectField = new TokenField($("#project-field"), {
  onChange: () => updateProjectExample(),
  spacesToHyphens: true,
});
// Deliberately a NARROWER palette than the link name's. A link name wants
// per-scan UNIQUENESS; a project name wants per-scan GROUPING. Exam / recon /
// sequence chips are withheld here because they differ per acquisition and
// would mint one project per scan. See MRI_PROJECT_PALETTE_KEYS in app.py.
renderPalette($("#project-palette"),
  paletteEntries(MRI.projectPaletteKeys || []), projectField);
$("#project-default").addEventListener("click", () => {
  projectField.setValue(MRI.projectDefault || "");
  updateProjectExample();
});

function updateProjectExample() {
  const el = $("#project-example");
  if (!el) return;
  const tpl = projectField.serialize().trim();
  if (!sampleCtx) {
    el.textContent = tpl ? "Preview to see the project name this produces." : "";
    el.classList.remove("bad");
    return;
  }
  const { text, unresolved } = resolveExample(tpl, sampleCtx);
  el.textContent = text ? "e.g.  " + text : "";
  el.classList.toggle("bad", unresolved);
}

function updateProjectMode() {
  const mode = projectMode.value;
  projectFixedWrap.hidden = mode !== "fixed";
  linkFieldset.hidden = mode === "none";
  // Seed from the locked default rather than an empty box: the operator edits a
  // working expression, and the default stops being invisible.
  if (mode === "fixed" && !projectField.serialize().trim()) {
    projectField.setValue(MRI.projectDefault || "");
  }
  if (mode === "auto") {
    projectNote.textContent =
      "Each scan goes to its own animal-protocol project (AE-biomaGUNE-<NNNN>, from the folder name), auto-created if it doesn’t exist.";
  } else if (mode === "fixed") {
    // Sits BELOW the field, so it must not say "the name below" -- and the
    // paragraph above the field already explains how to build the name. Use the
    // space for the safety net instead: what Preview will show you.
    projectNote.textContent =
      "Preview lists every project this run would file into, with a scan count and a mark on any " +
      "it would create — read it before you ingest.";
  } else {
    projectNote.textContent = "Scans are ingested and registered, but NOT linked into any project (no hard links created).";
  }
  updateProjectExample();
}
projectMode.addEventListener("change", updateProjectMode);
updateProjectMode();

// The project-name template the operator has asked for; "" means no project.
function projectTemplate() {
  const mode = projectMode.value;
  if (mode === "none") return "";
  if (mode === "fixed") return projectField.serialize().trim();
  return MRI.projectDefault || "";
}

// An empty custom name is NOT the same request as "no project", but the config
// cannot tell them apart -- both resolve to a blank `registry.project_name`, so
// an empty box would silently ingest with no links at all. Make the operator say
// which one they meant. Returns "" when the setting is usable.
function projectError() {
  if (projectMode.value !== "fixed") return "";
  if (projectTemplate()) return "";
  return "Type a project name, or click a metadata label to build one \u2014 " +
    "or choose \u201cNo project\u201d if that is what you meant.";
}

// Destination projects the LAST PREVIEW actually resolved, biggest first.
// `c.project` is the preview's Step-9.5 replica: "PROJ-XXXX", "will
// auto-create: <name>", "not found: <name>", or "(no project)".
//
// For an EXISTING project that string is the bare PROJ id, which is not what an
// operator recognises -- so pair it with the canonical name, which the same
// preview already wrote onto `registry_resolved.project_name` (that is the name
// the ingest will use, casing correction included).
function distinctProjects(cases) {
  const seen = new Map();
  (cases || []).forEach((c) => {
    const raw = c.project || "";
    if (!raw || raw === "(no project)") return;
    const e = seen.get(raw) || { n: 0, name: "" };
    e.n += 1;
    if (!e.name) e.name = ((c.registry_resolved || {}).project_name || "").trim();
    seen.set(raw, e);
  });
  return Array.from(seen, ([raw, e]) => {
    const stripped = raw.replace(/^(will auto-create|not found):\s*/, "");
    const resolved = /^PROJ-\d+$/.test(stripped);
    return {
      name: (resolved && e.name) ? e.name : stripped,
      id: resolved ? stripped : "",
      n: e.n,
      create: /^will auto-create:/.test(raw),
      missing: /^not found:/.test(raw),
    };
  }).sort((a, b) => b.n - a.n || a.name.localeCompare(b.name));
}

// Short human label for the chosen destination (for the completion modal).
// Prefers what the preview actually resolved over what the operator typed --
// with a token-valued name those are not the same thing.
function projectDestLabel() {
  if (projectMode.value === "none") return "No project (no links created)";
  const dests = distinctProjects(lastCases);
  if (dests.length === 1) return dests[0].name;
  if (dests.length > 1) {
    const head = dests.slice(0, 3).map((d) => `${d.name} (${d.n})`).join(", ");
    return `${dests.length} projects — ${head}${dests.length > 3 ? ", …" : ""}`;
  }
  return projectTemplate() || "Per animal-protocol code (auto)";
}

// The per-destination breakdown shown under the preview counts. With a
// token-valued project name one run can touch several projects and CREATE
// several -- the operator has to see that list before committing, not after.
function renderProjectSummary(cases) {
  const box = $("#project-summary");
  const dests = distinctProjects(cases);
  const noProj = (cases || []).filter(
    (c) => !c.project || c.project === "(no project)").length;
  if (!dests.length && !noProj) { box.innerHTML = ""; box.style.display = "none"; return; }
  const parts = [];
  if (dests.length) {
    parts.push(dests.length === 1
      ? "All scans file into <strong>1</strong> project:"
      : `Scans file into <strong>${dests.length}</strong> different projects:`);
    parts.push("<ul>" + dests.map((d) => {
      const tag = d.create ? ' <span class="pill">will be created</span>'
        : d.missing ? ' <span class="pill no">does not exist</span>' : "";
      const id = d.id ? ` <span class="muted">${esc(d.id)}</span>` : "";
      return `<li><code>${esc(d.name)}</code>${id} — ${d.n} scan(s)${tag}</li>`;
    }).join("") + "</ul>");
  }
  if (noProj) {
    parts.push(`<span class="muted">${noProj} scan(s) file into no project (no links created).</span>`);
  }
  const nMissing = dests.filter((d) => d.missing).length;
  const nCreate = dests.filter((d) => d.create).length;
  if (nMissing) {
    parts.push(`<strong>⚠ ${nMissing} project(s) above do not exist and will NOT be created</strong> — those scans ingest without a project link.`);
  } else if (nCreate > 3) {
    parts.push(`<strong>⚠ this run would create ${nCreate} new projects.</strong> Read the names above before ingesting.`);
  }
  box.innerHTML = parts.join("<br>");
  box.style.display = "";
}

// ---------------------------------------------------------------- payload
function buildPayload() {
  const mode = projectMode.value;
  const p = {
    staging_path: $("#staging").value.trim(),
    nas_root: nasInput.value.trim(),
    operator: $("#operator").value.trim(),
    project_mode: mode,
    regenerate: $("#regenerate").checked,
  };
  if (mode === "fixed") p.project_name = projectField.serialize().trim();
  if (mode !== "none") p.link_filename = linkField.serialize();
  return p;
}

// ---------------------------------------------------------------- preview
let lastCases = [];

function renderCollisions(cols, existing) {
  const box = $("#collisions");
  const parts = [];
  if (cols && cols.length) {
    parts.push(`<strong>⚠ ${cols.length} link-name collision(s)</strong> — two or more scans would write the SAME link name into the SAME project (one would overwrite the other). Make the link name unique (keep exam/recon/sample), or split the run:`);
    parts.push("<ul>" + cols.map((c) =>
      `<li><code>${esc(c.link_filename)}</code> in <code>${esc(c.project_name)}</code> ← ${c.acq_ids.length} scans: ${esc(c.acq_ids.join(", "))}</li>`
    ).join("") + "</ul>");
  }
  if (existing && existing.length) {
    parts.push(`<strong>⚠ ${existing.length} link target(s) already exist on the RDM System</strong> for a different acquisition — ingesting would collide with a previously-linked scan: ${existing.slice(0, 6).map((e) => `<code>${esc(e.link_filename)}</code>`).join(", ")}${existing.length > 6 ? " …" : ""}`);
  }
  box.innerHTML = parts.join("<br>");
  box.style.display = parts.length ? "" : "none";
}

function renderTable(cases) {
  if (!cases.length) { $("#table-wrap").innerHTML = ""; return; }
  const head = ["ACQ-ID", "Sample", "Project", "Link name", "Exam", "Recon", ""];
  const rows = cases.map((c) => {
    const reg = c.registry_resolved || {};
    const disco = c.discovered || {};
    const warn = (c.warnings && c.warnings.length)
      ? `<span class="pill no" title="${esc(c.warnings.join(' | '))}">${c.warnings.length}⚠</span>` : "";
    return `<tr>
      <td>${esc(c.acq_id)}</td>
      <td>${esc(reg.sample_id || disco.jrc_id || "")}</td>
      <td>${esc(c.project)}</td>
      <td><code>${esc(c.link_filename)}</code></td>
      <td>${esc(disco.mri_exam_number || disco.folder_name || "")}</td>
      <td>${esc(disco.mri_recon_indices || "")}</td>
      <td>${warn}</td></tr>`;
  });
  $("#table-wrap").innerHTML =
    `<table><thead><tr>${head.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead>` +
    `<tbody>${rows.join("")}</tbody></table>`;
}

// "Dropped" = folders that matched the scan pattern but aren't scans. For
// ParaVision that's the housekeeping siblings (AdjResult, subject, …) beside the
// numbered exam folders — expected and harmless. Show them plainly so the
// "N dropped" count never reads as an error.
function renderDropped(dropped) {
  const box = $("#dropped");
  if (!dropped || !dropped.length) { box.innerHTML = ""; box.style.display = "none"; return; }
  const names = dropped.map((d) => esc(d.name)).join(", ");
  box.innerHTML = `<span class="muted">${dropped.length} non-scan folder(s) skipped ` +
    `(normal ParaVision housekeeping, nothing to ingest): ${names}</span>`;
  box.style.display = "";
}

let lastDicomifier = null;   // {available, version} after a preview; null before

function updateDicomifierNote() {
  const el = $("#dicomifier-state");
  el.className = "muted";
  if (!$("#regenerate").checked) {
    el.textContent = "(regeneration off — no-DICOM exams ingest as placeholders)";
  } else if (lastDicomifier === null) {
    el.textContent = "(Preview checks whether Dicomifier is available on this machine)";
  } else if (lastDicomifier.available) {
    el.textContent = `✓ Dicomifier detected (${lastDicomifier.version || "ok"}) — missing DICOMs will be regenerated here.`;
  } else {
    el.textContent = "⚠ Dicomifier NOT detected here — no-DICOM exams ingest as empty placeholders (filled by a later re-ingest). Never blocks.";
  }
}

async function preview() {
  $("#errors").textContent = "";
  $("#summary").innerHTML = "";
  $("#project-summary").style.display = "none";
  $("#collisions").style.display = "none";
  $("#dropped").style.display = "none";
  $("#table-wrap").innerHTML = "";
  $("#warnings").textContent = "";
  $("#ingest").disabled = true;
  const payload = buildPayload();
  if (!payload.staging_path) { $("#errors").textContent = "Pull studies from the scanner first."; return; }
  const projErr = projectError();
  if (projErr) { $("#errors").textContent = projErr; return; }
  $("#preview").disabled = true;
  try {
    const d = await postJSON("/api/mri/preview", payload);
    lastCases = d.cases || [];
    lastDicomifier = { available: d.dicomifier_available, version: d.dicomifier_version };
    updateDicomifierNote();
    // Seed the live link-name example from the first real scan in the preview.
    const first = lastCases[0];
    if (first) {
      const reg = first.registry_resolved || {};
      sampleCtx = {
        ctx: first.discovered || {},
        synth: {
          sample_id: reg.sample_id || "",
          acq_date: first.acq_date || "",
          acq_id: first.acq_id || "",
          original_name: first.original_name || "",
        },
      };
      updateLinkExample();
      updateProjectExample();
    }
    renderProjectSummary(lastCases);
    renderCollisions(d.collisions, d.existing_targets);
    renderDropped(d.dropped);
    renderTable(lastCases);

    let s = `<strong>${d.n_new}</strong> new scan(s) would be ingested`;
    if (d.n_already_ingested) s += `; ${d.n_already_ingested} already ingested (skipped)`;
    if (d.n_dropped) s += `; ${d.n_dropped} non-scan folder(s) skipped`;
    s += `; ${d.n_matched} scanned.`;
    $("#summary").innerHTML = s;

    if (d.warnings && d.warnings.length) $("#warnings").textContent = d.warnings.join("\n");
    const blocking = (d.blocking_errors || []);
    if (blocking.length) {
      $("#errors").innerHTML = "Cannot proceed:<br>" + blocking.map(esc).join("<br>");
    } else if (d.n_new > 0) {
      $("#ingest").disabled = false;
    } else {
      $("#summary").innerHTML += " <em>Nothing new to ingest.</em>";
    }
  } catch (e) {
    $("#errors").textContent = e.message;
  } finally {
    $("#preview").disabled = false;
  }
}
$("#preview").addEventListener("click", preview);

// ---------------------------------------------------------------- ingest (SSE)
function appendLog(el, level, msg) {
  const line = document.createElement("div");
  line.className = "log-line lvl-" + String(level || "INFO").toLowerCase();
  line.textContent = `[${level}] ${msg}`;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
}

// Drain a fetch() SSE stream (POST-based, so EventSource can't be used). Each
// event is `data: {kind,level,msg}\n\n`; dispatch to the supplied handlers.
// Shared by the ingest stream and the SFTP-pull stream.
async function readSSE(resp, handlers) {
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
      if (evt.kind === "log" && handlers.onLog) handlers.onLog(evt.level || "INFO", evt.msg);
      else if (evt.kind === "error" && handlers.onError) handlers.onError(evt.msg);
      else if (evt.kind === "done" && handlers.onDone) handlers.onDone(JSON.parse(evt.msg));
    }
  }
}

async function ingest() {
  const payload = buildPayload();
  payload.dry_run = $("#dry").checked;
  // The source is always a pull into staging — remove it after a clean real ingest.
  payload.cleanup_staging = true;
  if (!payload.operator) { $("#errors").textContent = "Operator is required (who ran the scanner)."; return; }
  const projErr = projectError();
  if (projErr) { $("#errors").textContent = projErr; return; }
  $("#ingest").disabled = true;
  $("#preview").disabled = true;
  $("#log-wrap").hidden = false;
  const logEl = $("#log");
  logEl.innerHTML = "";
  $("#result").innerHTML = "";

  // SSE via fetch + ReadableStream (POST body needed -> can't use EventSource).
  let resp;
  try {
    resp = await fetch("/api/mri/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    appendLog(logEl, "ERROR", e.message);
    $("#ingest").disabled = false; $("#preview").disabled = false; return;
  }
  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`;
    try { const j = await resp.json(); if (j.error) msg = j.error; } catch (e) { /* */ }
    appendLog(logEl, "ERROR", msg);
    $("#ingest").disabled = false; $("#preview").disabled = false; return;
  }

  await readSSE(resp, {
    onLog: (lvl, msg) => appendLog(logEl, lvl, msg),
    onError: (msg) => appendLog(logEl, "ERROR", msg),
    onDone: (r) => {
      const resEl = $("#result");
      if (r.dry_run) {
        resEl.className = "summary dry-done";
        resEl.innerHTML = `✓ DRY RUN COMPLETE — <strong>NOTHING was written to the RDM System.</strong> ` +
          `${r.ok}/${r.total} scans WOULD be ingested. Uncheck “Dry-run” and run again to ingest for real.`;
      } else {
        resEl.className = "summary live-done";
        resEl.innerHTML = `✓ INGEST COMPLETE — <strong>${r.ok}/${r.total} scans written</strong> to ${esc(nasInput.value) || "the RDM System"}.`;
        // A real ingest also raises an unmissable completion modal. Skip a 0-scan run.
        if (r.total > 0 && window.showCompletionModal) {
          showCompletionModal({
            ok: r.ok, total: r.total, unit: "scans",
            failedAcqIds: (r.results || []).filter((x) => !x.ok).map((x) => x.acq_id),
            rows: [
              { label: "Destination", value: nasInput.value || "the RDM System" },
              { label: "Project", value: projectDestLabel() },
            ],
          });
        }
      }
    },
  });
  $("#ingest").disabled = false;
  $("#preview").disabled = false;
}
$("#ingest").addEventListener("click", ingest);

// ---------------------------------------------------------------- dry-run state
const dry = $("#dry");
const commit = $("#commit");
const dryState = $("#dry-state");
const dryBanner = $("#dry-banner");
function updateDryState() {
  const on = dry.checked;
  commit.classList.toggle("safe", on);
  commit.classList.toggle("live", !on);
  dryState.textContent = on ? "Safe — nothing will be written." : "LIVE — Ingest will write to the RDM System.";
  if (dryBanner) dryBanner.hidden = !on;
}
dry.addEventListener("change", updateDryState);
$("#regenerate").addEventListener("change", updateDicomifierNote);

// ---------------------------------------------------------------- SFTP remote pull
// Pull ParaVision study folders off the scanner over SFTP into a staging batch
// (on the NAS by default), then run Preview/Ingest on it — the operator never
// sees or manages the staging path. Read-only on the scanner (download only).
const sftp = {
  status: $("#sftp-status"), controls: $("#sftp-controls"),
  listBtn: $("#sftp-list"), allChk: $("#sftp-all"), count: $("#sftp-count"),
  listWrap: $("#sftp-listwrap"), items: $("#sftp-list-items"),
  search: $("#sftp-search"), selNone: $("#sftp-selnone"),
  pullRow: $("#sftp-pullrow"), pullNote: $("#sftp-pull-note"),
  advanced: $("#sftp-advanced"), stagingRoot: $("#sftp-staging-root"),
  pullBtn: $("#sftp-pull"),
  logWrap: $("#sftp-log-wrap"), log: $("#sftp-log"), result: $("#sftp-result"),
  exams: [],
};

async function sftpInit() {
  let d;
  try { d = await getJSON("/api/sftp_status"); }
  catch (e) { sftp.status.textContent = "Remote pull unavailable."; return; }
  if (d.staging_root && !sftp.stagingRoot.value) sftp.stagingRoot.value = d.staging_root;
  if (d.available) {
    sftp.status.innerHTML = `Scanner <code>${esc(d.host)}</code> — ready. List the studies, tick the ones you want, then pull.`;
    sftp.controls.hidden = false;
  } else if (!d.paramiko) {
    sftp.status.textContent = "Remote pull isn’t available on this machine (the ‘paramiko’ package is missing — ask the data office to install it).";
  } else {
    sftp.status.textContent = "No scanner credentials on this machine (the data office sets up ~/.ssh/gjesus3_mri.cred).";
  }
}

function sftpSelected() {
  return $$(".sftp-row input:checked", sftp.items).map((c) => c.dataset.remote);
}
function sftpUpdatePullBtn() {
  const n = sftpSelected().length;
  sftp.pullBtn.disabled = n === 0;
  sftp.pullBtn.textContent = n ? `Pull ${n} selected` : "Pull selected";
}
function sftpRenderList() {
  const q = sftp.search.value.trim().toLowerCase();
  const rows = sftp.exams
    .filter((e) => !q || e.name.toLowerCase().includes(q))
    .map((e) =>
      `<label class="sftp-row"><input type="checkbox" data-remote="${esc(e.remote)}">` +
      `<span class="sftp-name">${esc(e.name)}</span>` +
      `<span class="pill">${esc(e.version)}</span></label>`);
  sftp.items.innerHTML = rows.join("") || "<div class='fb-empty'>(no matching studies)</div>";
  $$(".sftp-row input", sftp.items).forEach((c) => c.addEventListener("change", sftpUpdatePullBtn));
  sftpUpdatePullBtn();
}
async function sftpList() {
  sftp.listBtn.disabled = true;
  sftp.count.textContent = "Listing…";
  try {
    const d = await postJSON("/api/sftp_listdir", { all: sftp.allChk.checked });
    sftp.exams = d.exams || [];
    sftp.count.textContent = `${d.count} stud${d.count === 1 ? "y" : "ies"}` +
      (d.filter ? ` (MFB only)` : " (all groups)");
    sftp.listWrap.hidden = false;
    sftp.pullRow.hidden = false;
    sftp.advanced.hidden = false;
    const where = (sftp.stagingRoot.value || "").trim();
    sftp.pullNote.textContent = where
      ? "→ staged under " + where + ", then removed automatically after ingest."
      : "";
    sftpRenderList();
  } catch (e) {
    sftp.count.textContent = "";
    sftp.status.textContent = "List failed: " + e.message;
  } finally {
    sftp.listBtn.disabled = false;
  }
}
async function sftpPull() {
  const remotes = sftpSelected();
  if (!remotes.length) return;
  // Validate the DESTINATION before the expensive pull — don't pull GBs only to
  // find at Preview that the NAS is unusable.
  if (!nasValid) {
    sftp.logWrap.hidden = false;
    sftp.result.className = "summary";
    sftp.result.innerHTML = '<span style="color:var(--bad)">⚠ Set a valid ' +
      'destination (the RDM System) at the top of the page first — it must be a folder that ' +
      'contains a <code>registries/</code> subfolder. Fix it, then pull.</span>';
    nasInput.focus();
    return;
  }
  sftp.pullBtn.disabled = true;
  sftp.listBtn.disabled = true;
  sftp.logWrap.hidden = false;
  sftp.log.innerHTML = "";
  sftp.result.innerHTML = "";
  let resp;
  try {
    resp = await fetch("/api/sftp_pull", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        remotes,
        nas_root: nasInput.value.trim(),
        staging_root: sftp.stagingRoot.value.trim(),
      }),
    });
  } catch (e) {
    appendLog(sftp.log, "ERROR", e.message);
    sftp.pullBtn.disabled = false; sftp.listBtn.disabled = false; return;
  }
  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`;
    try { const j = await resp.json(); if (j.error) msg = j.error; } catch (e) { /* */ }
    appendLog(sftp.log, "ERROR", msg);
    sftp.pullBtn.disabled = false; sftp.listBtn.disabled = false; return;
  }
  let pulled = null;
  await readSSE(resp, {
    onLog: (lvl, msg) => appendLog(sftp.log, lvl, msg),
    onError: (msg) => appendLog(sftp.log, "ERROR", msg),
    onDone: (r) => {
      pulled = r;
      $("#staging").value = r.staging_dir;   // internal — drives Preview/Ingest
      sftp.result.className = "summary live-done";
      sftp.result.innerHTML = `✓ Pulled ${r.studies} stud${r.studies === 1 ? "y" : "ies"} ` +
        `(${(r.bytes / 1e6).toFixed(1)} MB). Previewing…`;
    },
  });
  sftp.pullBtn.disabled = false;
  sftp.listBtn.disabled = false;
  // Go straight to the preview so the operator never thinks about staging.
  if (pulled && pulled.staging_dir) preview();
}
sftp.listBtn.addEventListener("click", sftpList);
sftp.allChk.addEventListener("change", () => { if (!sftp.listWrap.hidden) sftpList(); });
sftp.search.addEventListener("input", sftpRenderList);
sftp.selNone.addEventListener("click", () => {
  $$(".sftp-row input:checked", sftp.items).forEach((c) => { c.checked = false; });
  sftpUpdatePullBtn();
});
sftp.pullBtn.addEventListener("click", sftpPull);
$("#sftp-staging-browse").addEventListener("click", () => {
  browseInto(sftp.stagingRoot, "Select where pulled studies are staged", () => {
    const where = (sftp.stagingRoot.value || "").trim();
    sftp.pullNote.textContent = where
      ? "→ staged under " + where + ", then removed automatically after ingest." : "";
  });
});

// ---------------------------------------------------------------- init
refreshNas();
updateDryState();
updateDicomifierNote();
updateLinkExample();
sftpInit();
