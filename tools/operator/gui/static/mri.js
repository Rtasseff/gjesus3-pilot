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
  if (!r.ok) throw new Error((data && data.error) || `HTTP ${r.status}`);
  return data;
}

function getJSON(url) { return fetch(url).then((r) => r.json()); }

// ---------------------------------------------------------------- NAS root
const nasInput = $("#nas-root");
const nasStatus = $("#nas-status");

let nasValid = false;   // gates the pull — no point pulling to an unusable NAS
function setNasStatus(valid) {
  nasValid = !!valid;
  nasStatus.textContent = valid ? "OK" : "not a NAS root";
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
// Same component as the microscopy page (app.js): a modal over /api/listdir
// that shows folders + greyed files so the operator confirms the right place.
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
  try { data = await postJSON("/api/listdir", { path }); }
  catch (e) { fb.list.innerHTML = ""; fb.err.textContent = e.message; return; }
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

// ---------------------------------------------------------------- link field
const MRI = window.MRI || {};
const linkField = new TokenField($("#link-field"), { onChange: () => updateLinkExample() });
linkField.setValue(MRI.linkDefault || "");
renderPalette($("#link-palette"),
  paletteEntries(MRI.paletteKeys || [], MRI.paletteExtras || []), linkField);
$("#link-reset").addEventListener("click", () => { linkField.setValue(MRI.linkDefault || ""); updateLinkExample(); });

// Live "this is what the link name will look like" example under the field,
// mirroring the microscopy runner. Resolves ${discovered.*}/${synth} against the
// first previewed scan (sampleCtx), set after each preview. Before a preview
// runs there's no real scan to resolve against, so it stays blank.
let linkSampleCtx = null;   // {ctx: {discovered...}, synth: {sample_id,...}}

function resolveLinkExample(template, sample) {
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
    unresolved = true; return mm;
  });
  return { text, unresolved };
}

function updateLinkExample() {
  const el = $("#link-example");
  if (!el) return;
  const tpl = linkField.serialize();
  if (!linkSampleCtx) {
    el.textContent = tpl ? "Preview to see an example link name." : "";
    el.classList.remove("bad");
    return;
  }
  const { text, unresolved } = resolveLinkExample(tpl, linkSampleCtx);
  el.textContent = text ? "e.g.  " + text : "";
  el.classList.toggle("bad", unresolved);
}

// ---------------------------------------------------------------- project mode
const projectMode = $("#project-mode");
const projectFixedWrap = $("#project-fixed-wrap");
const projectHint = $("#project-hint");
const linkFieldset = $("#link-fieldset");
const projectNote = $("#project-note");

function updateProjectMode() {
  const mode = projectMode.value;
  projectFixedWrap.hidden = mode !== "fixed";
  linkFieldset.hidden = mode === "none";
  if (mode === "auto") {
    projectNote.textContent =
      "Each scan goes to its own animal-protocol project (ae-biomegune-<NNNN>, from the folder name), auto-created if it doesn’t exist.";
  } else if (mode === "fixed") {
    projectNote.textContent = "All scans in this run link into the one project you name.";
  } else {
    projectNote.textContent = "Scans are ingested and registered, but NOT linked into any project (no hard links created).";
  }
}
projectMode.addEventListener("change", updateProjectMode);
updateProjectMode();

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
  if (mode === "fixed") p.project_hint = projectHint.value.trim();
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
      `<li><code>${esc(c.link_filename)}</code> in <code>${esc(c.project_hint)}</code> ← ${c.acq_ids.length} scans: ${esc(c.acq_ids.join(", "))}</li>`
    ).join("") + "</ul>");
  }
  if (existing && existing.length) {
    parts.push(`<strong>⚠ ${existing.length} link target(s) already exist on the NAS</strong> for a different acquisition — ingesting would collide with a previously-linked scan: ${existing.slice(0, 6).map((e) => `<code>${esc(e.link_filename)}</code>`).join(", ")}${existing.length > 6 ? " …" : ""}`);
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
  $("#collisions").style.display = "none";
  $("#dropped").style.display = "none";
  $("#table-wrap").innerHTML = "";
  $("#warnings").textContent = "";
  $("#ingest").disabled = true;
  const payload = buildPayload();
  if (!payload.staging_path) { $("#errors").textContent = "Pull studies from the scanner first."; return; }
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
      linkSampleCtx = {
        ctx: first.discovered || {},
        synth: {
          sample_id: reg.sample_id || "",
          acq_date: first.acq_date || "",
          acq_id: first.acq_id || "",
          original_name: first.original_name || "",
        },
      };
      updateLinkExample();
    }
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
        resEl.innerHTML = `✓ DRY RUN COMPLETE — <strong>NOTHING was written to the NAS.</strong> ` +
          `${r.ok}/${r.total} scans WOULD be ingested. Uncheck “Dry-run” and run again to ingest for real.`;
      } else {
        resEl.className = "summary live-done";
        resEl.innerHTML = `✓ INGEST COMPLETE — <strong>${r.ok}/${r.total} scans written</strong> to ${esc(nasInput.value || "the NAS")}.`;
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
  dryState.textContent = on ? "Safe — nothing will be written." : "LIVE — Ingest will write to the NAS.";
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
      'destination NAS at the top of the page first — it must be a folder that ' +
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
