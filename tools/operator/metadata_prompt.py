"""Collect operator-supplied condition/anatomy metadata for ni/mri-ingest.

Phase-3 enrichment writes a `condition:` block (is_control / disease_model /
disease_state / ...) and an `anatomy:` block (is_whole_body / region / ...) into
each acquisition's metadata.json (08_METADATA §4.6-4.7). The per-instrument
templates ship those blocks as NULL SENTINELS (is_control/is_whole_body -> null,
disease_* -> ""), which the pipeline records as "unknown" and WARNs about but
never blocks on.

This module lets the MRI / NI command-line operators fill those values in at
ingest time -- either via CLI flags or, when a flag is omitted, an interactive
prompt -- so the data is captured at the source instead of being backfilled
later. The collected values become `config_builder` overrides
(`condition.<field>` / `anatomy.<field>`) and so apply to EVERY acquisition in
the run.

Design (confirmed with the data office 2026-06-08):

  * is_control is tri-state. A CONTROL (is_control=true) is, by definition, an
    animal with NO disease model, NO perturbation, and NO intervention -- so
    disease_model / disease_state are only asked when is_control is explicitly
    FALSE (a case). See mfb-rdm-docs/08_METADATA.
  * disease_model / disease_state are OPTIONAL even for a case: a blank answer
    leaves the template sentinel in place (the pipeline still ingests, just
    WARNs). Nothing here ever blocks an ingest.
  * is_whole_body is asked on its own. When it is false (a region of interest)
    the UBERON region is NOT prompted here -- it is set later in the per-acq
    metadata override file (/projects/<proj>/metadata/<acq_id>.json).
  * Skipping is always allowed: press enter at any prompt to leave the value
    unset. Non-interactive runs (no TTY, or --no-prompt) skip every prompt.

Pure stdlib; no pipeline imports, so it is trivially unit-testable with an
injected `ask`/`out`.
"""

# Accepted spellings for the tri-state prompts. control/case mirror the
# is_control prompt wording ("true=control / false=case").
_TRUE = {"true", "t", "yes", "y", "1", "control"}
_FALSE = {"false", "f", "no", "n", "0", "case"}

BANNER = (
    "Important metadata requested. Answers will apply to all scans. "
    "Press enter to skip questions."
)
BATCH_NOTE = (
    "Answers will apply to the full batch in the selected directory; skip "
    "questions if the answer is not consistent across all acquisitions."
)


def parse_bool(text):
    """Coerce a prompt/flag answer to True | False | None.

    Blank / None -> None (skip). 'true'/'false' (and the common spellings, plus
    control/case) -> bool. Any other non-blank answer raises ValueError so an
    interactive caller can re-ask and argparse reports a clean error.
    """
    if text is None:
        return None
    s = str(text).strip().lower()
    if s == "":
        return None
    if s in _TRUE:
        return True
    if s in _FALSE:
        return False
    raise ValueError(f"expected 'true' or 'false' (got {text!r})")


def cli_bool(text):
    """argparse `type=` for --is-control / --is-whole-body: strict true/false.

    Unlike parse_bool, a blank is an error here (a flag given with no usable
    value), so the operator can't accidentally pass an empty string.
    """
    value = parse_bool(text)  # raises ValueError on an unrecognized answer
    if value is None:
        raise ValueError("expected 'true' or 'false'")
    return value


def _ask_bool(ask, out, prompt):
    """Prompt until a valid true/false/blank answer. Blank -> None (skip)."""
    while True:
        try:
            raw = ask(prompt)
        except (EOFError, KeyboardInterrupt):
            return None
        try:
            return parse_bool(raw)
        except ValueError:
            out("  please answer 'true' or 'false' (or press enter to skip).")


def _ask_text(ask, prompt):
    """Prompt for a free-text value; blank / EOF -> '' (skip)."""
    try:
        return (ask(prompt) or "").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def collect_overrides(cli, *, is_batch, interactive, ask=input, out=print):
    """Resolve condition/anatomy values from CLI flags + optional prompts.

    Args:
        cli: dict of the CLI-provided values (None where the flag was omitted):
            {is_control: bool|None, disease_model: str|None,
             disease_state: str|None, is_whole_body: bool|None}.
        is_batch: True if the run covers more than one acquisition (only changes
            the banner wording).
        interactive: prompt for the still-missing values when True. Callers pass
            `not no_prompt and sys.stdin.isatty()` so piped / --no-prompt runs
            never block.
        ask / out: injected input / print (for testing).

    Returns:
        A flat dict of `config_builder` overrides (condition.* / anatomy.*),
        containing ONLY the values that were actually supplied. Skipped values
        are omitted, leaving the template's null sentinels intact.
    """
    is_control = cli.get("is_control")
    disease_model = cli.get("disease_model")
    disease_state = cli.get("disease_state")
    is_whole_body = cli.get("is_whole_body")

    # Disease fields are relevant only to a case (is_control == False).
    def _disease_missing():
        return is_control is False and (disease_model is None or disease_state is None)

    need = (
        is_control is None
        or is_whole_body is None
        or _disease_missing()
    )

    if interactive and need:
        out("")
        out(BANNER)
        if is_batch:
            out(BATCH_NOTE)
        out("")
        if is_control is None:
            is_control = _ask_bool(ask, out, "is_control (true=control / false=case): ")
        # Only a case (is_control=False) has a disease model / state.
        if is_control is False:
            if disease_model is None:
                disease_model = _ask_text(ask, "disease_model (optional): ")
            if disease_state is None:
                disease_state = _ask_text(ask, "disease_state (optional): ")
        if is_whole_body is None:
            is_whole_body = _ask_bool(
                ask, out,
                "is_whole_body (true=whole-body / false=region of interest): ",
            )

    overrides = {}
    if is_control is not None:
        overrides["condition.is_control"] = is_control
    if disease_model:  # non-empty string only
        overrides["condition.disease_model"] = disease_model
    if disease_state:
        overrides["condition.disease_state"] = disease_state
    if is_whole_body is not None:
        overrides["anatomy.is_whole_body"] = is_whole_body
    return overrides


def describe(overrides):
    """One-line human summary of what was set (for the operator log), or ''."""
    if not overrides:
        return ""
    parts = []
    if "condition.is_control" in overrides:
        parts.append(f"is_control={overrides['condition.is_control']}")
    if "condition.disease_model" in overrides:
        parts.append(f"disease_model={overrides['condition.disease_model']!r}")
    if "condition.disease_state" in overrides:
        parts.append(f"disease_state={overrides['condition.disease_state']!r}")
    if "anatomy.is_whole_body" in overrides:
        parts.append(f"is_whole_body={overrides['anatomy.is_whole_body']}")
    return ", ".join(parts) + " (applied to all acquisitions in this run)"


# ----------------------------------------------------------------- self-test

if __name__ == "__main__":
    # case with disease answers
    answers = iter(["false", "EAE", "acute", "true"])
    ov = collect_overrides(
        {"is_control": None, "disease_model": None, "disease_state": None,
         "is_whole_body": None},
        is_batch=True, interactive=True,
        ask=lambda _p: next(answers), out=lambda _m: None,
    )
    assert ov == {
        "condition.is_control": False,
        "condition.disease_model": "EAE",
        "condition.disease_state": "acute",
        "anatomy.is_whole_body": True,
    }, ov

    # control -> disease fields are NOT asked (iterator would raise if they were)
    answers = iter(["true", "false"])  # is_control=true, then is_whole_body=false
    ov = collect_overrides(
        {"is_control": None, "disease_model": None, "disease_state": None,
         "is_whole_body": None},
        is_batch=False, interactive=True,
        ask=lambda _p: next(answers), out=lambda _m: None,
    )
    assert ov == {"condition.is_control": True, "anatomy.is_whole_body": False}, ov

    # skip everything (blank answers) -> empty overrides (non-blocking)
    ov = collect_overrides(
        {"is_control": None, "disease_model": None, "disease_state": None,
         "is_whole_body": None},
        is_batch=False, interactive=True,
        ask=lambda _p: "", out=lambda _m: None,
    )
    assert ov == {}, ov

    # non-interactive: CLI values still flow through, no prompts
    ov = collect_overrides(
        {"is_control": False, "disease_model": "APP/PS1", "disease_state": None,
         "is_whole_body": True},
        is_batch=True, interactive=False,
        ask=lambda _p: (_ for _ in ()).throw(AssertionError("must not prompt")),
        out=lambda _m: None,
    )
    assert ov == {
        "condition.is_control": False,
        "condition.disease_model": "APP/PS1",
        "anatomy.is_whole_body": True,
    }, ov

    print("metadata_prompt self-test OK")
