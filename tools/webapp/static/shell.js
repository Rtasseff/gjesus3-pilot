// The web app's shell (tools/webapp/shell.py): the person's menu, and the
// "check, then add" row the ingest pages share inside the web app.
(function () {
  // The person's menu: close on a click elsewhere or Escape.
  const menu = document.querySelector(".gj-user");
  if (menu) {
    document.addEventListener("click", (e) => {
      if (menu.open && !menu.contains(e.target)) menu.open = false;
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && menu.open) { menu.open = false; menu.querySelector("summary").focus(); }
    });
  }

  // "Test run" and "Add to gjesus3". The page's own script still reads its
  // hidden dry-run box when its button is pressed; here the box is set from
  // which of the two buttons was used, before that script runs.
  document.querySelectorAll(".gj-commit").forEach((row) => {
    const add = row.querySelector(".gj-add");
    const test = row.querySelector(".gj-testrun");
    const dry = add && document.getElementById(add.dataset.dry);
    if (!add || !test || !dry) return;
    let testing = false;
    const setDry = (on) => {
      dry.checked = on;
      dry.dispatchEvent(new Event("change"));
    };
    // Capture phase: runs before the page's own click handler on the button.
    add.addEventListener("click", () => setDry(testing), true);
    test.addEventListener("click", () => {
      if (add.disabled) return;
      testing = true;
      try { add.click(); } finally { testing = false; }
    });
    // A test run is possible exactly when adding is (after a preview).
    const sync = () => { test.disabled = add.disabled; };
    new MutationObserver(sync).observe(add, { attributes: true, attributeFilter: ["disabled"] });
    sync();
  });
})();
