# Nuclear Imaging — folder **value** standard (proposal)

**STATUS: ❓ EVALUATING** — a proposal for the Data Office (Ryan) to accept, amend or reject.
Nothing here is implemented. Raised 2026-08-19 after the PROJ-0056 misattribution
([`CHANGELOG.md`](../../CHANGELOG.md)); the open root-cause item is in
[`tasks/BACKLOG.md`](../../tasks/BACKLOG.md).

**Companion to** [`live_machine_data_layout_and_sync_rules.md`](live_machine_data_layout_and_sync_rules.md),
which describes the layout **as it is**. This describes what we would **ask researchers to type
going forward**. The two disagree on purpose: that document had to survive an archive nobody
governed; this one exists so the next five years do not need surviving.

---

## 1. Why

On 2026-08-19, 15 PROJ-0056 acquisitions were found attributed to three rats that were never in
the scanner. The researcher's working copy nested a per-reconstruction folder — `r1`, `r2`, `r3` —
below the animal, and the subject parser read that level as the animal. `r1` became animal `1`.

The parser was not careless. **It did exactly what §3A of the layout document specifies**, where
the species prefix is documented as `m` (mouse) | **`r` (rat)** | none, with the explicit
instruction *"the parser MUST NOT require `m`"*. `r` is overloaded: it means *rat* in one
researcher's naming and *recon* in another's. Nothing in the grammar can tell them apart.

**And the safety net did not catch it.** §3A's stated rule is *"the facility DB is the validator,
not the folder"* — parse to a candidate `(project, animal)` pair, look it up, accept on a hit and
queue on a miss. But `(0421, 1)` **hits**: animal 1 of protocol 0421 is a real rat, born two years
earlier. The DB can answer *"does this animal exist?"*; it cannot answer *"was this animal in the
scanner that day?"* Existence is not attribution, and every check we had was an existence check.

So the failure was not a bug to fix. It was an **ambiguous input specification** faithfully
executed, with a validator that could not see the difference.

## 2. Scope — forward only

**In scope:** newly acquired NI data, synced from the live Molecubes box under the deferred
live-mode ingest ([`BACKLOG.md`](../../tasks/BACKLOG.md)).

**Explicitly out of scope, and not to be re-litigated:** the `S:\gnuclear` historical archive. It
was researcher-run, predates any platform policy, and was rescued on a best-guess basis in
2026-08 precisely because the alternative was losing it. It has been cleaned up as far as evidence
allows. **This standard is not a reason to re-open it, re-ingest it, or write more code to
re-interpret it.** Where the archive remains ambiguous — see the 4 unresolved PET header conflicts
in `BACKLOG.md` — the answer is a human who was there, or nothing.

## 3. What is fixed, and what is ours to specify

The platform chose the directory structure. We are not proposing to change it — only to specify
the **values** that go into levels that are currently free text.

| Level | Source | Today | Ours to specify? |
|---|---|---|---|
| `<researcher>/` | hand-typed | typo-variants (`maria_g`, `maria g`) | **Yes** — must match the sync roster |
| `<series_or_project>/` | hand-typed | mixes funded-project id, animal-protocol code, free text | **Yes** — leading token |
| `<YYMMDD>/` | hand-typed | 95.5% agree with the machine clock | **No value** — machine timestamp already wins |
| `<subject / session label>/` | hand-typed | free-form; **this is where the defect lived** | **Yes — the one that matters** |
| `<YYYYMMDDhhmmss>_<MODALITY>/` | **machine** | 100% consistent, 3,191/3,191 | Not ours; not needed |
| `recon_0/ … recon_N/` | **machine** | inside the acquisition folder | Not ours |

**One reassurance worth stating plainly:** in the live-machine layout, reconstructions live
*inside* the machine-issued acquisition folder as `recon_N/`. The `r1` level that caused PROJ-0056
was a folder the researcher invented in their own working copy — it does not exist on the box.
**The exact PROJ-0056 collision is therefore structurally impossible in live mode.** This standard
is not about re-fighting that specific bug; it is about the ambiguities that *do* survive into live
mode — missing protocol codes, separator drift, and the `m`/`r`/bare prefix inconsistency.

## 4. The proposal

### 4.1 Subject / session label — the decision that matters

```
<protocol>_<animal>[_<animal>…][_<timepoint>]
```

- **`<protocol>`** — the 4-digit animal-protocol code. **Required.** Today it is "OFTEN OMITTED"
  and recovered from the parent folder, which is also how `1015`-vs-`1025` conflicts arise.
- **`<animal>`** — see the three options below. 1–4 animals (the bed physically holds ≤ 4).
- **`<timepoint>`** — optional, `<N>h` or `d<NN>`.
- **Separator: `_` only.** Today it is `_` or `-` "varies BY PERSON", which is also what makes
  `m6-7` (a pair) indistinguishable from `m10-15` (a range or a pair).

**The animal token — pick one:**

| | Format | Example | Trade-off |
|---|---|---|---|
| **(a) — recommended** | digits only | `0421_230_231` | Unambiguous by construction; nothing can collide with `r`/`recon`/anything. Species already comes from the facility DB, so the prefix is decoration. Shortest to teach. Costs researchers a habit they find meaningful at the bench. |
| (b) | spelled-out prefix | `0421_rat230` | Keeps the bench habit, kills the `r`/recon collision. Costs a longer token and a rule about which prefixes are legal. |
| (c) | prefix always required | `0421_m230` / `0421_rat230` | Most explicit; species is stated twice (folder + DB) and can therefore *disagree*, which is a new failure mode we do not have today. |

I recommend **(a)**. The prefix carries no information the facility DB does not already hold
authoritatively, and every prefix scheme is a new chance for a character to mean two things — which
is the exact defect we are trying to retire. **(b)** is the reasonable compromise if dropping `m`
is a fight not worth having.

### 4.2 Series / project folder

Leading token must be the **4-digit animal-protocol code**; free text may follow after `_`.
`0421` and `0421_tmcao` both pass; `lu_177-dota-ptr-58` does not. This removes the "recover the
project from the parent's leading digits" inference and the typo-conflict class with it.

### 4.3 Researcher folder

Must match a name on the sync roster exactly (the allow-list already exists — §2A of the layout
doc). This is a spelling rule, not a new mechanism.

## 5. Enforcement — refuse, do not guess

The live-mode ingest already plans an **operator dry-run review table**. That is the whole
enforcement point; no new machinery is needed.

- A conforming label parses, resolves, and shows the operator the animal it resolved to.
- A **non-conforming label does not parse at all** — the batch stops and names the offending
  folder. The operator renames and re-runs.
- **No fallback grammar, no best-guess, no "recover from the parent".** The value of this proposal
  is entirely in the refusal; a lenient fallback re-creates today's behaviour.

Rejection costs an operator a rename, measured in seconds. The alternative cost is measured in
years: PROJ-0056 sat wrong from 2023 until an unrelated trial server tripped over it.

## 6. What this does **not** fix

Worth being honest, so the standard is not oversold:

- It cannot detect a **correctly formatted but wrong** animal number — a typo of `230` as `231`
  still parses, still resolves, still misattributes. Closing that needs the procedure-date check
  in §7, not a naming rule.
- It does nothing for the historical archive (§2), by design.
- It does not resolve the 4 open PET header conflicts, which are a console-entry problem, not a
  folder problem.

## 7. The one code change still worth considering (separate decision)

Not required by this proposal, and deliberately kept separate: teach the validator to ask the
facility DB *"does this animal have any procedure logged near this acquisition date?"*

This is **not** guessing at researcher intent — it is a second authoritative record answering a
factual question. It is what settled PROJ-0056: animals 230/231 have `Admin RT +Pet` **and** `CT`
logged on exactly 2023-10-26, 236/237 on exactly 2023-10-27, and the wrongly-named 1/2/3 have
nothing after 2021. It is the only check that catches a well-formed wrong number.

Cost: one DB query per acquisition, read-only, must degrade quietly off-network like every other DB
path. Filed in [`BACKLOG.md`](../../tasks/BACKLOG.md) as MODERATE.

## 8. Open questions

| # | Question | For |
|---|---|---|
| 1 | Animal token — (a) digits, (b) `rat230`, or (c) always-prefixed? | **Ryan** (Data Office call) |
| 2 | Is requiring the protocol code in the subject label acceptable, given it is often omitted today? | Ryan + Unai |
| 3 | Do we enforce for **all** NI users or only the MFB group (the sync is already scoped to Jesus's group)? | Ryan |
| 4 | Who tells the researchers, and does it need a one-page card at the console? | Ryan + Unai |
| 5 | Phantoms and QC runs — keep `phantom…` as a reserved literal that skips the DB link? | Ryan |
