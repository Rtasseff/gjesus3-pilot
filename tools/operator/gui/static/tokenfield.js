"use strict";

/* tokenfield.js — ONE reusable "field token" widget, used everywhere a value can
 * reference a discovered field (#7/#14/#18: "pick one solution to solve
 * everywhere").
 *
 * A TokenField is a contenteditable box that mixes free text with ATOMIC field
 * chips. A chip displays a friendly label ("objective mag") but carries the real
 * token ("${discovered.czi_objective_mag}"); it inserts/drops/clicks in as one
 * object and DELETES as one object — you can't break it into a stray "$" or "{".
 *
 *   const tf = new TokenField(el, { onChange: () => ... });
 *   tf.setValue("Slide ${discovered.sample_id} (${discovered.stain})");
 *   tf.serialize();   // -> the template string the backend expects
 *
 * Palette chips (the list of available fields) are rendered by renderPalette();
 * clicking or dragging one inserts a chip into the LAST focused TokenField.
 */

// ---- friendly labels -------------------------------------------------------
// Strip the instrument prefix + underscores so operators see "objective mag",
// not "${discovered.czi_objective_mag}". The chip keeps the real token on hover.
const _FIELD_PREFIXES = ["czi_", "ni_", "mri_", "dicom_"];

function humanizeRef(ref) {
  // ref is the inside of ${...}: "discovered.czi_objective_mag", "sample_id", …
  let s = ref.trim();
  if (s.startsWith("discovered.")) s = s.slice("discovered.".length);
  for (const p of _FIELD_PREFIXES) {
    if (s.startsWith(p)) { s = s.slice(p.length); break; }
  }
  return s.replace(/_/g, " ");
}

function humanizeToken(token) {
  const m = /^\$\{([^}]+)\}$/.exec(token);
  return m ? humanizeRef(m[1]) : token;
}

// ---- pure template <-> segment helpers (unit-testable without a DOM) --------
// A segment is {text:"..."} or {token:"${...}", label:"..."}.
function parseTemplate(tmpl) {
  const segs = [];
  if (tmpl == null) return segs;
  const re = /\$\{([^}]+)\}/g;
  let last = 0, m;
  while ((m = re.exec(tmpl)) !== null) {
    if (m.index > last) segs.push({ text: tmpl.slice(last, m.index) });
    segs.push({ token: m[0], label: humanizeRef(m[1]) });
    last = m.index + m[0].length;
  }
  if (last < tmpl.length) segs.push({ text: tmpl.slice(last) });
  return segs;
}

function segmentsToTemplate(segs) {
  return segs.map((s) => (s.token != null ? s.token : s.text)).join("");
}

// Export the pure helpers for a node-side unit test (no-op in the browser).
if (typeof module !== "undefined" && module.exports) {
  module.exports = { parseTemplate, segmentsToTemplate, humanizeRef, humanizeToken };
}

// ---- DOM widget (browser only) ---------------------------------------------
if (typeof document !== "undefined") {

  function makeChip(token, label) {
    const chip = document.createElement("span");
    chip.className = "token";
    chip.setAttribute("contenteditable", "false");
    chip.dataset.token = token;
    chip.title = token;                       // hover shows the real ${...}
    chip.textContent = label != null ? label : humanizeToken(token);
    return chip;
  }

  // Insert a DOM node at the current caret if it sits inside `container`,
  // otherwise append to the end. Leaves the caret right after the node.
  function insertNodeAtCaret(container, node) {
    const sel = window.getSelection();
    let range = null;
    if (sel && sel.rangeCount) {
      const r = sel.getRangeAt(0);
      if (container.contains(r.commonAncestorContainer)) range = r;
    }
    if (!range) {
      container.appendChild(node);
    } else {
      range.deleteContents();
      range.insertNode(node);
    }
    // caret after the node
    const after = document.createRange();
    after.setStartAfter(node);
    after.collapse(true);
    if (sel) { sel.removeAllRanges(); sel.addRange(after); }
  }

  // Track the TokenField the operator last interacted with, so a palette click
  // knows where to insert.
  let _activeField = null;

  class TokenField {
    constructor(el, opts = {}) {
      this.el = el;
      this.onChange = opts.onChange || null;
      el.setAttribute("contenteditable", "true");
      el.setAttribute("role", "textbox");
      el.classList.add("tokenfield");
      if (opts.placeholder) el.dataset.placeholder = opts.placeholder;

      el.addEventListener("focus", () => { _activeField = this; });
      el.addEventListener("input", () => this._changed());

      // Atomic delete: if the caret sits just after / before a chip, remove the
      // WHOLE chip (Chromium mostly does this for contenteditable=false, but we
      // guarantee it across the Backspace/Delete edge cases).
      el.addEventListener("keydown", (e) => this._onKeydown(e));

      // Plain-text paste only (never inherit rich HTML / nested editables).
      el.addEventListener("paste", (e) => {
        e.preventDefault();
        const t = (e.clipboardData || window.clipboardData).getData("text");
        document.execCommand("insertText", false, t);
      });

      // Accept palette chips dropped anywhere in the box (at the drop point).
      el.addEventListener("dragover", (e) => {
        if (e.dataTransfer && Array.from(e.dataTransfer.types).includes("application/x-gj-token")) {
          e.preventDefault();
          el.classList.add("drop-target");
        }
      });
      el.addEventListener("dragleave", () => el.classList.remove("drop-target"));
      el.addEventListener("drop", (e) => {
        const token = e.dataTransfer.getData("application/x-gj-token");
        if (!token) return;
        e.preventDefault();
        el.classList.remove("drop-target");
        _activeField = this;
        // place caret at the drop point if the browser can resolve it
        const pos = (document.caretRangeFromPoint && document.caretRangeFromPoint(e.clientX, e.clientY));
        if (pos && el.contains(pos.commonAncestorContainer)) {
          const sel = window.getSelection();
          sel.removeAllRanges(); sel.addRange(pos);
        } else {
          el.focus();
        }
        this.insertToken(token);
      });
    }

    _changed() {
      this._syncEmpty();
      if (this.onChange) this.onChange(this.serialize());
    }

    _syncEmpty() {
      // Toggle a class so CSS can show the placeholder when truly empty.
      const empty = this.serialize().trim() === "";
      this.el.classList.toggle("is-empty", empty);
    }

    _onKeydown(e) {
      if (e.key !== "Backspace" && e.key !== "Delete") return;
      const sel = window.getSelection();
      if (!sel || !sel.isCollapsed || !sel.rangeCount) return;
      const r = sel.getRangeAt(0);
      const node = r.startContainer;
      const off = r.startOffset;
      let chip = null;
      if (e.key === "Backspace") {
        if (node === this.el && off > 0) chip = this.el.childNodes[off - 1];
        else if (node.nodeType === Node.TEXT_NODE && off === 0) chip = node.previousSibling;
      } else { // Delete
        if (node === this.el && off < this.el.childNodes.length) chip = this.el.childNodes[off];
        else if (node.nodeType === Node.TEXT_NODE && off === node.nodeValue.length) chip = node.nextSibling;
      }
      if (chip && chip.nodeType === Node.ELEMENT_NODE && chip.classList.contains("token")) {
        e.preventDefault();
        chip.remove();
        this._changed();
      }
    }

    focus() { this.el.focus(); _activeField = this; }

    insertToken(token, label) {
      this.el.focus();
      _activeField = this;
      insertNodeAtCaret(this.el, makeChip(token, label));
      this._changed();
    }

    // Children -> template string (text verbatim, chips -> their ${...} token).
    serialize() {
      let out = "";
      this.el.childNodes.forEach((n) => {
        if (n.nodeType === Node.TEXT_NODE) out += n.nodeValue;
        else if (n.nodeType === Node.ELEMENT_NODE) {
          if (n.dataset && n.dataset.token) out += n.dataset.token;
          else if (n.tagName === "BR") { /* ignore stray line breaks */ }
          else out += n.textContent;
        }
      });
      return out.replace(/ /g, " ");   // nbsp -> normal space
    }

    setValue(tmpl) {
      this.el.innerHTML = "";
      for (const seg of parseTemplate(tmpl)) {
        if (seg.token != null) this.el.appendChild(makeChip(seg.token, seg.label));
        else this.el.appendChild(document.createTextNode(seg.text));
      }
      this._syncEmpty();
    }
  }

  // Render a palette of available fields as clickable + draggable chips. Each
  // entry is {token, label}. Clicking inserts into the active TokenField.
  function renderPalette(container, entries, fallbackField) {
    container.innerHTML = "";
    if (!entries.length) {
      container.innerHTML = "<span class='muted'>No fields yet — set the source folder and Show fields.</span>";
      return;
    }
    entries.forEach(({ token, label }) => {
      const chip = document.createElement("span");
      chip.className = "palette-chip";
      chip.textContent = label;
      chip.title = token;
      chip.setAttribute("draggable", "true");
      chip.addEventListener("click", () => {
        const target = _activeField || fallbackField;
        if (target) target.insertToken(token, label);
      });
      chip.addEventListener("dragstart", (e) => {
        e.dataTransfer.setData("application/x-gj-token", token);
        e.dataTransfer.setData("text/plain", token);
        e.dataTransfer.effectAllowed = "copy";
      });
      container.appendChild(chip);
    });
  }

  // Build palette entries from discovered keys (+ a few resolver-supplied ones).
  function paletteEntries(keys, extras = []) {
    const base = (keys || []).map((k) => ({
      token: `\${discovered.${k}}`, label: humanizeRef(k),
    }));
    const ex = extras.map((t) => ({ token: t, label: humanizeToken(t) }));
    return base.concat(ex);
  }

  window.TokenField = TokenField;
  window.renderPalette = renderPalette;
  window.paletteEntries = paletteEntries;
  window.tfHumanizeRef = humanizeRef;
}
