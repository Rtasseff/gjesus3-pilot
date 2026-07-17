"use strict";

/* completion_modal.js — the "ingest complete" modal shown on a real
 * (non-dry-run) ingest completion, on BOTH the microscopy (/) and MRI (/mri)
 * pages. The end-of-run summary at the bottom of the page was easy to miss;
 * this raises an unmissable, dismissible modal with the run summary.
 *
 * Mirrors the folder-browser modal pattern (a full-screen overlay + a centred
 * card). This controller owns focus + Esc + dismissal; the page scripts call
 * window.showCompletionModal({...}) with the run's numbers. Loaded on both
 * pages before app.js / mri.js, and it self-disables if the markup is absent.
 */

(function () {
  const overlay = document.getElementById("done-overlay");
  if (!overlay) return;                       // page has no modal markup — no-op
  const modal = overlay.querySelector(".done-modal");
  const checkEl = overlay.querySelector(".done-check");
  const titleEl = document.getElementById("done-title");
  const bodyEl = document.getElementById("done-body");
  const closeBtn = document.getElementById("done-close");
  let lastFocus = null;                       // restore focus here on close

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function close() {
    overlay.hidden = true;
    document.removeEventListener("keydown", onKey);
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  function onKey(e) { if (e.key === "Escape") { e.preventDefault(); close(); } }

  closeBtn.addEventListener("click", close);
  // Click the dim backdrop (but not the card) to dismiss.
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });

  // opts: { ok, total, unit?, failedAcqIds?: string[], rows?: [{label, value}] }
  window.showCompletionModal = function (opts) {
    const o = opts || {};
    const total = o.total || 0;
    const ok = o.ok || 0;
    const unit = o.unit || "acquisitions";
    const failed = o.failedAcqIds || [];
    const nFail = failed.length || Math.max(0, total - ok);
    const allOk = nFail === 0;

    modal.classList.toggle("has-fail", !allOk);
    if (checkEl) checkEl.textContent = allOk ? "✓" : "!";
    titleEl.textContent = allOk ? "Ingest complete"
                                : "Ingest finished — with issues";

    let html = `<p class="done-stat">${ok} of ${total} ${esc(unit)} ` +
      `ingested into the RDM System.</p>`;
    if (!allOk) {
      const ids = failed.slice(0, 6).map(esc).join(", ");
      html += `<p class="done-fail">${nFail} did not ingest` +
        (ids ? ` (${ids}${failed.length > 6 ? " …" : ""})` : "") +
        `. See the ingest log below for details.</p>`;
    }
    const rows = (o.rows || []).filter((r) => r && r.value);
    if (rows.length) {
      html += "<dl>" + rows.map((r) =>
        `<dt>${esc(r.label)}</dt><dd>${esc(r.value)}</dd>`).join("") + "</dl>";
    }
    bodyEl.innerHTML = html;

    lastFocus = document.activeElement;
    overlay.hidden = false;
    document.addEventListener("keydown", onKey);
    closeBtn.focus();
  };
})();
