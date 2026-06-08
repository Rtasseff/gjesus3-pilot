"""enrichment.py — build the non-blocking preclinical enrichment blocks.

Phase 3 (08_METADATA §4.4 subject / §4.5 condition / §4.6 anatomy, non-blocking
model §4.7). Called from ingest_raw.py Step 8.5 with the resolved per-case
config; returns (subject, condition, anatomy) dicts (or None when a block does
not apply to this sample_type) ready to nest in metadata.json.

Trigger rules:
    sample_type ∈ {organism, tissue}  -> subject + condition
    sample_type == organism           -> + anatomy
    anything else (cells/material/...) -> all three None

NON-BLOCKING (the hard rule): nothing here ever raises on missing data. Every
unknown is written as an explicit sentinel (null / "" / "unknown" / "pending-
db") and surfaced as a WARN. A DB miss queues the acquisition to the pending
list for later superuser recovery; the ingest still succeeds.

The animal-DB lookup is injectable (`lookup_fn`) so the branchy logic is
unit-testable without a live database.
"""

from . import resolver, subject_id, pending

# animal_db lives at tools/animal_db.py (top-level, like create_project); it
# imports cleanly even without pymysql / credentials (fail-soft by design).
import animal_db


# Sidecar field order for the subject block (08_METADATA §4.4.2).
SUBJECT_ORDER = [
    "facility_animal_id", "species", "strain", "sex", "date_of_birth",
    "age_at_acquisition", "genotype", "weight_at_acquisition_g", "cohort_id",
    "procedures", "source",
]


def _default_log(msg, level="INFO"):
    print(f"[enrichment] {level}: {msg}")


def _acq_for_age(acq_dt_iso, acq_date):
    """Pick the best acquisition date for age derivation.

    Prefer the ISO datetime; fall back to converting the YYYYMMDD ACQ-ID
    prefix to an ISO date; else "".
    """
    if acq_dt_iso:
        return acq_dt_iso
    if acq_date and len(acq_date) == 8 and acq_date.isdigit():
        return f"{acq_date[:4]}-{acq_date[4:6]}-{acq_date[6:8]}"
    return ""


def _subject_placeholder(source, facility_animal_id=""):
    """A fully-sentinel subject block — required fields blank, never omitted."""
    return {
        "facility_animal_id": facility_animal_id or "",
        "species": "",
        "strain": "",
        "sex": "unknown",
        "date_of_birth": None,
        "age_at_acquisition": "",
        "genotype": "",
        "weight_at_acquisition_g": None,
        "cohort_id": "",
        "procedures": [],
        "source": source,
    }


def _finalize_subject(subj, acq_for_age, source):
    """Overlay a (DB or operator) subject dict onto the sentinel template,
    derive age_at_acquisition from date_of_birth when absent, and return the
    block in canonical field order."""
    base = _subject_placeholder(source, subj.get("facility_animal_id", ""))
    for k in base:
        if k in subj and subj[k] is not None:
            base[k] = subj[k]
    base["source"] = source
    # Preserve the documented sentinel for fields whose "unknown" value is not
    # empty-string: an explicit operator `sex: NA` resolves to "" but the
    # sentinel for sex is "unknown".
    if not base.get("sex"):
        base["sex"] = "unknown"
    # Age derivation is best-effort + NON-BLOCKING: age_iso8601 returns None on
    # an unparseable date_of_birth, and we guard anyway so build_enrichment can
    # never raise (08_METADATA §4.7) regardless of operator input.
    if base.get("date_of_birth") and not base.get("age_at_acquisition"):
        try:
            base["age_at_acquisition"] = animal_db.age_iso8601(
                base["date_of_birth"], acq_for_age) or ""
        except Exception:
            base["age_at_acquisition"] = ""
    return {k: base[k] for k in SUBJECT_ORDER}


def _subject_from_operator(block, discovered, acq_for_age):
    """Build a subject block from an explicit operator `subject:` YAML block.

    Overrides the DB; resolves ${discovered.*} leniently; source defaults to
    operator-entered.
    """
    resolved = {}
    for k in ("facility_animal_id", "species", "strain", "sex",
              "date_of_birth", "age_at_acquisition", "genotype", "cohort_id"):
        if k in block:
            resolved[k] = resolver._resolve_text_lenient(
                block.get(k), discovered, f"subject.{k}")
    if "weight_at_acquisition_g" in block:
        resolved["weight_at_acquisition_g"] = resolver.to_number(
            block.get("weight_at_acquisition_g"))
    if "procedures" in block:
        procs = block.get("procedures")
        resolved["procedures"] = procs if isinstance(procs, list) else []
    src = "operator-entered"
    if block.get("source"):
        src = resolver._resolve_text_lenient(
            block.get("source"), discovered, "subject.source") or "operator-entered"
    return _finalize_subject(resolved, acq_for_age, src)


def _build_subject(cfg_single, discovered, acq_for_age, acq_id,
                   canonical_path, registries_dir, dry_run, lookup_fn, log):
    # 1. Explicit operator override wins.
    op_block = cfg_single.get("subject")
    if op_block:
        subj = _subject_from_operator(op_block, discovered, acq_for_age)
        log(f"subject: operator-entered ({subj.get('facility_animal_id') or 'no id'})")
        return subj

    # 2. Animal-facility DB lookup.
    if cfg_single.get("subject_from_db"):
        lookup_block = cfg_single.get("subject_lookup") or {}

        alias = ""
        if lookup_block.get("project_alias"):
            try:
                alias = resolver.resolve_value(lookup_block["project_alias"], discovered)
            except resolver.ResolverError:
                alias = ""
        if not alias:
            alias = subject_id.project_alias_from_hint(cfg_single.get("project_hint", ""))

        code_str = ""
        if lookup_block.get("animal_code"):
            try:
                code_str = resolver.resolve_value(lookup_block["animal_code"], discovered)
            except resolver.ResolverError:
                code_str = ""
        code, _organ = subject_id.parse_animal_short_code(code_str)

        if code is None:
            log(f"subject: could not parse an animal code from {code_str!r} "
                f"(alias={alias!r}); writing source=unknown (no DB lookup).", "WARN")
            return _subject_placeholder("unknown")

        res = lookup_fn(alias, code)
        if res.status == "found":
            fa = res.subject.get("facility_animal_id")
            log(f"subject: DB hit {fa}")
            return _finalize_subject(res.subject, acq_for_age, "animal-facility-db")

        # not_found (db-miss) | unreachable (no-credentials) -> pending.
        fa_id = animal_db.compose_subject_id(code, alias)
        reason = res.reason or "db-miss"
        log(f"subject: DB {res.status} ({reason}) for {fa_id}; writing "
            f"source=pending-db and queueing for recovery.", "WARN")
        if not dry_run and registries_dir:
            try:
                sidecar = (canonical_path.rstrip("/") + "/metadata.json") if canonical_path else ""
                pending.append_pending(registries_dir, acq_id, sidecar, fa_id, reason)
            except Exception as e:  # pending list must never break ingest
                log(f"subject: could not append to pending list: {e}", "WARN")
        return _subject_placeholder("pending-db", fa_id)

    # 3. No source configured for an organism/tissue acq.
    log("subject: no subject_from_db flag and no operator subject: block; "
        "writing source=unknown.", "WARN")
    return _subject_placeholder("unknown")


def _build_condition(cfg_single, discovered, log):
    out = resolver.resolve_condition_block(cfg_single.get("condition"), discovered)
    is_control = out.get("is_control")
    if is_control is None:
        log("condition: is_control is null (unknown) - set it once per batch "
            "when known (true=control / false=case).", "WARN")
    elif is_control is False:
        # A case: disease_model / disease_state characterize it, so an empty
        # value is worth a (non-blocking) reminder. A CONTROL, by definition,
        # has no disease model / perturbation / intervention, so its empty
        # disease fields are correct and must NOT warn (08_METADATA).
        if not out.get("disease_model"):
            log("condition: disease_model is empty (case with no disease model "
                "recorded).", "WARN")
        if not out.get("disease_state"):
            log("condition: disease_state is empty (case with no disease state "
                "recorded).", "WARN")
    return out


def _build_anatomy(cfg_single, discovered, log):
    out = resolver.resolve_anatomy_block(cfg_single.get("anatomy"), discovered)
    if out.get("is_whole_body") is None:
        log("anatomy: is_whole_body is null (unknown) - set it once per batch "
            "when known (true=whole-body / false=region of interest).", "WARN")
    elif out.get("is_whole_body") is False and not out.get("region"):
        log("anatomy: is_whole_body=false but no UBERON region given.", "WARN")
    return out


def build_enrichment(cfg_single, *, acq_id, acq_date, acq_dt_iso="",
                     canonical_path="", registries_dir="", dry_run=False,
                     lookup_fn=None, log=None):
    """Return (subject, condition, anatomy) for this case, or None per block.

    Pure orchestration over the resolver + animal-DB fetch + pending list. Never
    raises on missing data (08_METADATA §4.7). `lookup_fn` defaults to
    animal_db.lookup and is injectable for tests.
    """
    log = log or _default_log
    if lookup_fn is None:
        lookup_fn = animal_db.lookup

    sample_type = (cfg_single.get("sample_type") or "").strip().lower()
    discovered = cfg_single.get("discovered") or {}
    acq_for_age = _acq_for_age(acq_dt_iso, acq_date)

    subject = condition = anatomy = None
    if sample_type in ("organism", "tissue"):
        subject = _build_subject(
            cfg_single, discovered, acq_for_age, acq_id,
            canonical_path, registries_dir, dry_run, lookup_fn, log,
        )
        condition = _build_condition(cfg_single, discovered, log)
    if sample_type == "organism":
        anatomy = _build_anatomy(cfg_single, discovered, log)
    return subject, condition, anatomy
