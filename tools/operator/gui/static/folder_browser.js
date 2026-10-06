"use strict";

/* folder_browser.js — the in-page folder browser modal, shared by ALL pages.
 *
 * Was copy-pasted into app.js (microscopy) and mri.js; the two copies were
 * near-verbatim and drifting was only a matter of time, so the component lives
 * here once and every page loads it — the ingest app's two pages and the
 * Project Manager. Each page still owns its own copy of the MARKUP
 * (#fb-overlay … in index.html / mri.html / manager index.html) — same ids on
 * all of them. Its backend counterpart is tools/filebrowse.py.
 *
 * TWO MODES, one component:
 *
 *   browseInto(inputEl, "Select the source folder", (chosenPath) => { … });
 *     pick a FOLDER. Files are listed greyed, for context only. This is what
 *     every ingest field uses and its behaviour is unchanged.
 *
 *   browseFiles(inputEl, "Choose files to copy", (paths) => { … });
 *     pick FILES. Files get checkboxes; folders still navigate. The selection
 *     is a BASKET that survives navigation, so files can be gathered from more
 *     than one folder in a single trip — which is what someone assembling
 *     "the files I want in my project" actually does. `inputEl` may be null
 *     (there is nothing sensible to write into a single text box); the chosen
 *     paths arrive through the callback.
 *
 * Unlike the OS folder-only dialog (which made every folder look empty), this
 * lists folders AND files. A LOCAL app, so /api/listdir lists the local
 * filesystem.
 *
 * SORT ORDER. The header strip flips the name order. Instrument source folders
 * are named by date (…\AxioScan\20260522), so Z->A is newest-first — which is
 * what the operator wants nearly every time. The flag is sent to the BACKEND
 * (which sorts before it caps the list at _BROWSE_LIMIT); reversing the
 * received list here would silently show the wrong end of a huge folder. The
 * choice sticks for the session and, when the browser allows it, across
 * restarts of the app (localStorage) — so it is a click once, not once a day.
 *
 * WHERE IT OPENS. In order: the target box's own value; else the folder that
 * button was last left in (remembered per target, across restarts); else the
 * home folder. Operators click down the same tree every morning, so reopening
 * there is the difference between one click and five. A remembered folder that
 * has since gone away falls back to home SILENTLY and is forgotten — a stale
 * memory is not the operator's mistake and must not look like an error.
 *
 * Exposes: window.browseInto and window.browseFiles. Deliberately declares
 * NOTHING else in global scope — app.js and mri.js already define $, esc,
 * postJSON there.
 */
(function () {
  const q = (sel) => document.querySelector(sel);
  const qa = (sel) => Array.from(document.querySelectorAll(sel));

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  async function listdir(path, desc, withSize) {
    const r = await fetch("/api/listdir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, desc, with_size: !!withSize }),
    });
    let data = null;
    try { data = await r.json(); } catch (e) { /* non-json */ }
    if (!r.ok) throw new Error((data && data.error) || `HTTP ${r.status}`);
    return data;
  }

  // ---- persisted preferences (best-effort; a blocked localStorage is fine) ----
  const SORT_KEY = "gj3.folderBrowser.sortDesc";
  const LASTDIR_KEY = "gj3.folderBrowser.lastDir";

  function loadSortDesc() {
    try { return window.localStorage.getItem(SORT_KEY) === "1"; } catch (e) { return false; }
  }
  function saveSortDesc(v) {
    try { window.localStorage.setItem(SORT_KEY, v ? "1" : "0"); } catch (e) { /* ignore */ }
  }

  // Last folder each Browse… button was left in, remembered PER TARGET
  // (`{inputId: path}`). Per-target matters: the same modal serves the source
  // folder, the RDM System root, the recipes folder and the MRI staging folder,
  // and one shared memory would send an operator browsing for a day folder to
  // whichever of those they last looked at.
  function loadLastDirs() {
    try { return JSON.parse(window.localStorage.getItem(LASTDIR_KEY) || "{}") || {}; }
    catch (e) { return {}; }
  }
  function targetKey() {
    return (fb.target && fb.target.id) || "_";
  }
  function rememberDir(key, path) {
    if (!key || !path) return;
    try {
      const all = loadLastDirs();
      all[key] = path;
      window.localStorage.setItem(LASTDIR_KEY, JSON.stringify(all));
    } catch (e) { /* ignore */ }
  }
  function forgetDir(key) {
    try {
      const all = loadLastDirs();
      delete all[key];
      window.localStorage.setItem(LASTDIR_KEY, JSON.stringify(all));
    } catch (e) { /* ignore */ }
  }

  const fb = {
    overlay: q("#fb-overlay"), list: q("#fb-list"), pathInp: q("#fb-path"),
    drives: q("#fb-drives"), err: q("#fb-error"), title: q("#fb-title"),
    sortBtn: q("#fb-sort"), sortArrow: q("#fb-sort-arrow"),
    selectBtn: q("#fb-select"), hint: q(".fb-foot .muted"),
    target: null, cur: "", parent: null, onPick: null,
    sortDesc: loadSortDesc(),
    // File-pick mode. `picked` is a Map(path -> {name, size}) that SURVIVES
    // navigation, so files can be gathered from several folders in one trip.
    files: false, picked: new Map(),
  };
  if (!fb.overlay) return;   // page without the browser markup — nothing to wire

  // The folder-mode wording, captured once so file mode can borrow the footer
  // and folder mode can always put it back.
  const FOLDER_LABEL = fb.selectBtn ? fb.selectBtn.textContent : "Use this folder";
  const FOLDER_HINT = fb.hint ? fb.hint.textContent : "";

  function open_(input, title, onPick, files) {
    fb.target = input || null;
    fb.onPick = onPick || null;
    fb.files = !!files;
    fb.picked = new Map();
    fb.title.textContent = title || (files ? "Choose files" : "Select a folder");
    fb.err.textContent = "";
    fb.overlay.hidden = false;
    renderFoot();
    // Where to open. The box's own value wins — it is the most specific thing
    // the user has said. Otherwise reopen where this button was last left,
    // which across app restarts saves re-clicking down the same tree every
    // morning. Falling through to "" lets the backend pick the home folder.
    const own = input && input.value ? input.value.trim() : "";
    if (own) { fbLoad(own); return; }
    const remembered = loadLastDirs()[targetKey()];
    // `remembered: true` — a folder that has since been moved, renamed or
    // unmounted must NOT greet the user with an error; it silently drops back
    // to the home folder and the stale memory is discarded.
    if (remembered) fbLoad(remembered, { remembered: true });
    else fbLoad("");
  }

  function browseInto(input, title, onPick) {
    if (!input) return;                    // folder mode writes into a box
    open_(input, title, onPick, false);
  }

  function browseFiles(input, title, onPick) {
    open_(input, title || "Choose files", onPick, true);
  }

  function fmtSize(n) {
    if (n == null) return "";
    const u = ["B", "KB", "MB", "GB", "TB"];
    let i = 0, v = n;
    while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
    return (i === 0 ? v.toFixed(0) : v.toFixed(1)) + " " + u[i];
  }

  function renderFoot() {
    if (!fb.selectBtn) return;
    if (!fb.files) {
      fb.selectBtn.textContent = FOLDER_LABEL;
      fb.selectBtn.disabled = false;
      if (fb.hint) fb.hint.textContent = FOLDER_HINT;
      return;
    }
    const n = fb.picked.size;
    fb.selectBtn.textContent = n ? `Use these ${n} file${n === 1 ? "" : "s"}`
                                 : "Use these files";
    fb.selectBtn.disabled = n === 0;
    if (fb.hint) {
      fb.hint.textContent = n
        ? `${n} file${n === 1 ? "" : "s"} chosen — you can keep browsing; the list is kept.`
        : "Click a folder to open it. Tick the files you want.";
    }
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

  async function fbLoad(path, opts) {
    const remembered = !!(opts && opts.remembered);
    // Pin the target NOW: closing the modal mid-load nulls fb.target, and the
    // memory must land under the button that asked for this listing.
    const key = targetKey();
    fb.err.textContent = "";
    fb.list.innerHTML = "<div class='fb-empty'>Loading…</div>";
    renderSortHeader();
    let data;
    try {
      data = await listdir(path, fb.sortDesc, fb.files);
    } catch (e) {
      fb.list.innerHTML = "";
      if (remembered) { forgetDir(key); fbLoad(""); return; }   // stale memory: just go home
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
      } else if (fb.files) {
        // File-pick mode: a tickable row. `checked` is read from the basket so
        // navigating away and back does not lose what was already chosen.
        const full = joinPath(fb.cur, e.name);
        const on = fb.picked.has(full) ? " checked" : "";
        items.push(`<label class="fb-item pick" data-name="${esc(e.name)}" data-size="${e.size == null ? "" : e.size}">` +
          `<input type="checkbox"${on}><span class="ic">📄</span>` +
          `<span class="fb-fname">${esc(e.name)}</span>` +
          `<span class="fb-fsize muted">${esc(fmtSize(e.size))}</span></label>`);
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
    qa("#fb-list .fb-item.pick").forEach((el) => {
      const box = el.querySelector("input");
      box.addEventListener("change", () => {
        const full = joinPath(fb.cur, el.dataset.name);
        if (box.checked) {
          fb.picked.set(full, { name: el.dataset.name,
                                size: el.dataset.size === "" ? null : +el.dataset.size });
        } else {
          fb.picked.delete(full);
        }
        renderFoot();
      });
    });
    if (data.error) {
      // A missing folder is answered with the home folder AND an error string.
      // For a remembered path that is not the operator's mistake — drop the
      // stale memory and show the home folder without an alarming message.
      if (remembered) forgetDir(key);
      else fb.err.textContent = data.error;
    } else {
      // Reopen here next time this button is used.
      rememberDir(key, data.path);
    }
  }

  function fbClose() {
    fb.overlay.hidden = true;
    fb.target = null; fb.onPick = null;
    fb.files = false; fb.picked = new Map();
    renderFoot();                      // always hand the modal back in folder mode
  }

  function fbSelect() {
    const input = fb.target, cb = fb.onPick, files = fb.files;
    const chosen = files ? Array.from(fb.picked.keys()) : fb.cur;
    if (files && !chosen.length) return;    // the button is disabled anyway
    fbClose();
    if (input && !files) {
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
  window.browseFiles = browseFiles;
})();
