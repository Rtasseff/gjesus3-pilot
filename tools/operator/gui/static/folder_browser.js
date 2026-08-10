"use strict";

/* folder_browser.js — the in-page folder browser modal, shared by BOTH pages.
 *
 * Was copy-pasted into app.js (microscopy) and mri.js; the two copies were
 * near-verbatim and drifting was only a matter of time, so the component lives
 * here once and both pages load it. Each page still owns its own copy of the
 * MARKUP (#fb-overlay … in index.html / mri.html) — same ids on both.
 *
 *   browseInto(inputEl, "Select the source folder", (chosenPath) => { … });
 *
 * Unlike the OS folder-only dialog (which made every folder look empty), this
 * lists folders AND greyed files for context: click a folder to open it, then
 * "Use this folder". A LOCAL app, so /api/listdir lists the local filesystem.
 *
 * SORT ORDER. The header strip flips the name order. Instrument source folders
 * are named by date (…\AxioScan\20260522), so Z->A is newest-first — which is
 * what the operator wants nearly every time. The flag is sent to the BACKEND
 * (which sorts before it caps the list at _BROWSE_LIMIT); reversing the
 * received list here would silently show the wrong end of a huge folder. The
 * choice sticks for the session and, when the browser allows it, across
 * restarts of the app (localStorage) — so it is a click once, not once a day.
 *
 * Exposes: window.browseInto. Deliberately declares NOTHING in global scope
 * beyond that — app.js and mri.js already define $, esc, postJSON there.
 */
(function () {
  const q = (sel) => document.querySelector(sel);
  const qa = (sel) => Array.from(document.querySelectorAll(sel));

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  async function listdir(path, desc) {
    const r = await fetch("/api/listdir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, desc }),
    });
    let data = null;
    try { data = await r.json(); } catch (e) { /* non-json */ }
    if (!r.ok) throw new Error((data && data.error) || `HTTP ${r.status}`);
    return data;
  }

  // ---- sort order (persisted best-effort; a blocked localStorage is fine) ----
  const SORT_KEY = "gj3.folderBrowser.sortDesc";
  function loadSortDesc() {
    try { return window.localStorage.getItem(SORT_KEY) === "1"; } catch (e) { return false; }
  }
  function saveSortDesc(v) {
    try { window.localStorage.setItem(SORT_KEY, v ? "1" : "0"); } catch (e) { /* ignore */ }
  }

  const fb = {
    overlay: q("#fb-overlay"), list: q("#fb-list"), pathInp: q("#fb-path"),
    drives: q("#fb-drives"), err: q("#fb-error"), title: q("#fb-title"),
    sortBtn: q("#fb-sort"), sortArrow: q("#fb-sort-arrow"),
    target: null, cur: "", parent: null, onPick: null,
    sortDesc: loadSortDesc(),
  };
  if (!fb.overlay) return;   // page without the browser markup — nothing to wire

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

  function renderSortHeader() {
    if (!fb.sortArrow) return;
    fb.sortArrow.textContent = fb.sortDesc ? "▼" : "▲";
    if (fb.sortBtn) {
      fb.sortBtn.title = fb.sortDesc
        ? "Sorted Z→A (newest first for date-named folders) — click for A→Z"
        : "Sorted A→Z — click for Z→A (newest first for date-named folders)";
    }
  }

  async function fbLoad(path) {
    fb.err.textContent = "";
    fb.list.innerHTML = "<div class='fb-empty'>Loading…</div>";
    renderSortHeader();
    let data;
    try {
      data = await listdir(path, fb.sortDesc);
    } catch (e) {
      fb.list.innerHTML = "";
      fb.err.textContent = e.message;
      return;
    }
    fb.cur = data.path;
    fb.parent = data.parent || null;
    fb.pathInp.value = data.path;
    q("#fb-up").disabled = !fb.parent;

    fb.drives.innerHTML = (data.drives || []).map((d) =>
      `<span class="fb-drive" data-path="${esc(d)}">${esc(d)}</span>`).join("");
    qa("#fb-drives .fb-drive").forEach((el) =>
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

    qa("#fb-list .fb-item.dir").forEach((el) => {
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

  q("#fb-up").addEventListener("click", () => { if (fb.parent) fbLoad(fb.parent); });
  q("#fb-go").addEventListener("click", () => fbLoad(fb.pathInp.value.trim()));
  fb.pathInp.addEventListener("keydown", (e) => { if (e.key === "Enter") fbLoad(fb.pathInp.value.trim()); });
  q("#fb-select").addEventListener("click", fbSelect);
  q("#fb-close").addEventListener("click", fbClose);
  q("#fb-cancel").addEventListener("click", fbClose);
  fb.overlay.addEventListener("click", (e) => { if (e.target === fb.overlay) fbClose(); });
  if (fb.sortBtn) {
    fb.sortBtn.addEventListener("click", () => {
      fb.sortDesc = !fb.sortDesc;
      saveSortDesc(fb.sortDesc);
      // Re-fetch: the backend sorts BEFORE capping, so this is the only way a
      // >3000-entry folder shows its real other end. One round trip on a local
      // Flask app.
      fbLoad(fb.cur || fb.pathInp.value.trim());
    });
  }
  renderSortHeader();

  window.browseInto = browseInto;
})();
