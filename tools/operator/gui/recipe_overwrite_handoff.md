# Handoff — let operators overwrite an existing recipe

**Branch:** `feat/gui-browse-sort-and-reload` (this worktree — the browse/reload work is **done + verified**; this is the last item before merge)
**Written:** 2026-08-10 · **Status:** 🔶 not started · **Size:** small — front-end only

## The ask

Operators saving a recipe under a name that already exists get a warning and a
dead end. They want to **save over it**.

## The good news — the backend already does this

`POST /api/save_recipe` (`app.py:830-897`) has supported overwrite since before
this branch. It takes an `overwrite` flag and, when it would clobber, answers:

```
HTTP 409  {"error": "A recipe already exists as 'foo.yaml'. Saving would
                     overwrite it — choose a different name, or resend with
                     overwrite=true to replace it.",
           "exists": true, "file": "foo.yaml"}
```

Resend the same body with `overwrite: true` and it writes. **Nothing on the
server needs to change.** The only reason operators can't do it is that the
front-end never offers the second request.

**Why the flag never reaches the handler:** `postJSON()` (`static/app.js:12-25`)
throws on any non-`ok` status and keeps **only** `data.error` — so `exists` and
`file` are discarded before `#b-save`'s `catch` ever sees them (`app.js:1378-1394`).
The operator gets the sentence "…or resend with overwrite=true", which is written
for an API caller and means nothing to them.

**Note the existing promise.** "Load recipe" already tells them:

> `app.js:1336-1337` — *"Loaded `foo.yaml` — edit and re-save (keep the name to overwrite it, or rename to save a copy)."*

Keeping the name currently produces the 409 error. So this isn't a new feature —
it's making the UI keep a promise it already makes.

## The change

**1 · Let the error carry the response body** — `postJSON()` in `static/app.js`:

```js
if (!r.ok) {
  const err = new Error((data && data.error) || `HTTP ${r.status}`);
  err.status = r.status;
  err.data = data;
  throw err;
}
```

Additive: every existing `catch (e) { … e.message }` behaves exactly as before.
`static/mri.js:23` has its own copy of `postJSON` — the MRI page has no recipes,
so it doesn't need this, but **mirror it anyway** if you touch the shared idiom,
or leave a one-line comment saying why the two differ.

**2 · Offer the overwrite** in the `#b-save` handler (`app.js:1378`): on
`e.status === 409 && e.data && e.data.exists`, ask, and on yes re-issue the
identical POST with `overwrite: true`. Report it as **"Replaced"**, not "Saved",
so the operator knows which of the two things happened.

**3 · The confirm text must say what is actually at risk.** Recipes live in
`recipes_dir()`, which **defaults to the RDM System** (`\\gjesus3\…\recipes`) —
so an overwrite is a **shared** change that hits every operator on that
instrument, not a local one. Name the file and say so, e.g.

> Replace the existing recipe `axioscan_7_my_convention.yaml`?
> It is shared on the RDM System — every operator using it will get the new version.

A plain `window.confirm()` is a perfectly honest way to ship this and is the
recommended default. If you'd rather it match the house style, the repo already
has a modal idiom in `static/completion_modal.js` — that's a nice-to-have, not a
requirement, and it should not grow this task.

## Worth deciding (ask Ryan rather than guessing)

- **Keep a backup of the replaced file?** Cheap insurance, and it fits this
  project's backup-first habit. Safe to drop beside it: `list_recipes()`
  (`app.py:255-283`) only picks up `.json` / `.yaml` / `.yml`, so a
  `foo.yaml.bak` will **not** pollute the recipe picker. Against: it quietly
  accumulates in a shared NAS folder nobody prunes.
- **Distinct names that collide.** `"Study A"` and `"Study/A"` both sanitise to
  `study_a.yaml` (`app.py:850-853`). The 409 message names the *file*, which is
  the honest thing to show — make sure the confirm does too, so an operator who
  thinks they're saving a new recipe sees the filename that's about to be
  replaced rather than the name they typed.

## Test

1. Save a recipe. Save again with the same name → the confirm names the **file**
   and mentions it is shared → **Cancel** leaves the original untouched (check
   the file's mtime and contents) → **OK** replaces it and the status reads
   *Replaced*.
2. Load a recipe, edit it, keep the name, save → replaces cleanly. The
   "keep the name to overwrite it" hint is now true.
3. Save under a genuinely new name → **no** confirm appears (no regression).
4. A name with no usable filename characters → still the plain 400 error, no
   confirm.
5. Both recipe pickers (runner + builder) refresh and show the replaced recipe's
   new description.
6. Non-409 errors (e.g. an unwritable recipes folder) still surface their message
   as before.

## When it's done

Commit on this branch. Then this branch is **ready to merge** — see the review
notes in the session that wrote this handoff for the two small follow-ups on the
folder-browser persistence work. **Delete this file on landing** (the repo's
precedent: temporary handoffs are dropped when the branch merges), and add a
`CHANGELOG.md` row. Rebuilding + redeploying the `.exe` needs Ryan's explicit
go-ahead — build steps in `README.md` §"Freeze to a single `.exe`".
