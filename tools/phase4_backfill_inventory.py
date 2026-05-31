"""Phase 4 backfill scope inventory.

Walks /raw/ on the NAS, reads each metadata.json sidecar, classifies
acquisitions by sample_type to determine how many need subject: +
condition: block backfill once the Phase 3 sidecar writer ships.

Writes a markdown report to tasks/phase4_backfill_inventory.md.

Usage:
    python tools/phase4_backfill_inventory.py [--nas-root J:/] [--out tasks/phase4_backfill_inventory.md]
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime


def walk_raw(nas_root):
    """Yield (acq_id, metadata_path, metadata_dict_or_None) tuples."""
    raw_root = os.path.join(nas_root, "raw")
    for ecosystem in sorted(os.listdir(raw_root)):
        eco_path = os.path.join(raw_root, ecosystem)
        if not os.path.isdir(eco_path):
            continue
        for year in sorted(os.listdir(eco_path)):
            year_path = os.path.join(eco_path, year)
            if not os.path.isdir(year_path):
                continue
            for month in sorted(os.listdir(year_path)):
                month_path = os.path.join(year_path, month)
                if not os.path.isdir(month_path):
                    continue
                for acq in sorted(os.listdir(month_path)):
                    acq_path = os.path.join(month_path, acq)
                    if not os.path.isdir(acq_path):
                        continue
                    md_path = os.path.join(acq_path, "metadata.json")
                    if not os.path.isfile(md_path):
                        yield acq, md_path, None
                        continue
                    try:
                        with open(md_path, "r", encoding="utf-8") as f:
                            md = json.load(f)
                    except Exception as e:
                        print(f"WARN: failed to read {md_path}: {e}", file=sys.stderr)
                        md = None
                    yield acq, md_path, md


def classify(md):
    """Return (sample_type, instrument, has_subject_block, has_condition_block).

    sample_type from user_supplied or registry; "unknown" if not parseable.
    """
    if md is None:
        return ("missing-sidecar", "unknown", False, False)
    us = md.get("user_supplied", {}) or {}
    sample_type = (us.get("sample_type") or "").strip().lower() or "unset"
    instrument = (us.get("instrument") or "").strip().upper() or "UNKNOWN"
    has_subject = "subject" in md and bool(md.get("subject"))
    has_condition = "condition" in md and bool(md.get("condition"))
    return (sample_type, instrument, has_subject, has_condition)


def categorize_backfill(sample_type):
    """Return one of: 'required' / 'conditional' / 'not-required' / 'unset'."""
    if sample_type in ("organism", "tissue"):
        return "required"
    if sample_type in ("cells",):
        return "conditional"  # required when animal-origin cell line
    if sample_type in ("material", "phantom"):
        return "not-required"
    if sample_type in ("", "unset"):
        return "unset"
    return "unset"


def render_report(rows, nas_root):
    counts_by_instrument = Counter()
    counts_by_sample_type = Counter()
    counts_by_backfill_category = Counter()
    by_inst_sample_type = defaultdict(Counter)
    has_subject_count = 0
    has_condition_count = 0
    missing_sidecar = []

    for acq, md_path, sample_type, instrument, has_subj, has_cond in rows:
        counts_by_instrument[instrument] += 1
        counts_by_sample_type[sample_type] += 1
        counts_by_backfill_category[categorize_backfill(sample_type)] += 1
        by_inst_sample_type[instrument][sample_type] += 1
        if has_subj:
            has_subject_count += 1
        if has_cond:
            has_condition_count += 1
        if sample_type == "missing-sidecar":
            missing_sidecar.append(acq)

    total = sum(counts_by_instrument.values())
    today = datetime.now().strftime("%Y-%m-%d")

    lines = []
    lines.append("# Phase 4 backfill inventory — `subject:` + `condition:` block coverage")
    lines.append("")
    lines.append(f"**Generated:** {today}")
    lines.append(f"**Source:** `{os.path.join(nas_root, 'raw').replace(chr(92), '/')}/` walked by `tools/phase4_backfill_inventory.py`")
    lines.append(f"**Total acquisitions:** {total}")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("This inventory scopes the Phase 4 work in `tasks/tasks.md §3.2`: how many existing acquisitions need `subject:` + `condition:` block backfill once the Phase 3 sidecar writer ships. Per the spec:")
    lines.append("- `subject:` block is REQUIRED for `sample_type ∈ {organism, tissue}` (see [08_METADATA §4.4](../mfb-rdm-docs/08_METADATA.md))")
    lines.append("- `condition:` block is REQUIRED for the same trigger (see [08_METADATA §4.5](../mfb-rdm-docs/08_METADATA.md))")
    lines.append("- For `sample_type = cells`: required when animal-origin (operator judgement until vocab clarifies)")
    lines.append("- Not required for `material` / `phantom`")
    lines.append("")
    lines.append("## Coverage today")
    lines.append("")
    lines.append(f"- Acquisitions with a populated `subject:` block: **{has_subject_count} / {total}**")
    lines.append(f"- Acquisitions with a populated `condition:` block: **{has_condition_count} / {total}**")
    lines.append("")
    lines.append("(Phase 3 writer hasn't shipped yet, so both should currently be 0 — anything above zero is forward-compatible operator-entered data.)")
    lines.append("")
    lines.append("## Backfill scope by category")
    lines.append("")
    lines.append("| Category | Count | Action |")
    lines.append("|---|---|---|")
    for cat in ("required", "conditional", "not-required", "unset"):
        n = counts_by_backfill_category.get(cat, 0)
        if cat == "required":
            action = "**MUST** backfill `subject:` + `condition:` (operator recall from notebooks)"
        elif cat == "conditional":
            action = "Operator judgement: backfill if cell line is animal-origin"
        elif cat == "not-required":
            action = "No action — non-biological sample"
        else:
            action = "Audit — `sample_type` was empty at ingest; revisit before backfill"
        lines.append(f"| {cat} | {n} | {action} |")
    lines.append("")
    lines.append("## By instrument")
    lines.append("")
    lines.append("| Instrument | Total | Required-backfill | Conditional | Not-required | Unset |")
    lines.append("|---|---|---|---|---|---|")
    for inst in sorted(counts_by_instrument.keys()):
        sts = by_inst_sample_type[inst]
        req = sum(n for st, n in sts.items() if categorize_backfill(st) == "required")
        cond = sum(n for st, n in sts.items() if categorize_backfill(st) == "conditional")
        notreq = sum(n for st, n in sts.items() if categorize_backfill(st) == "not-required")
        unset = sum(n for st, n in sts.items() if categorize_backfill(st) == "unset")
        lines.append(f"| {inst} | {counts_by_instrument[inst]} | {req} | {cond} | {notreq} | {unset} |")
    lines.append("")
    lines.append("## Raw distribution by `sample_type`")
    lines.append("")
    lines.append("| sample_type | Count |")
    lines.append("|---|---|")
    for st, n in counts_by_sample_type.most_common():
        lines.append(f"| `{st}` | {n} |")
    lines.append("")
    lines.append("## Raw distribution per (instrument, sample_type)")
    lines.append("")
    lines.append("| Instrument | sample_type | Count |")
    lines.append("|---|---|---|")
    for inst in sorted(by_inst_sample_type.keys()):
        for st, n in sorted(by_inst_sample_type[inst].items(), key=lambda x: -x[1]):
            lines.append(f"| {inst} | `{st}` | {n} |")
    lines.append("")
    if missing_sidecar:
        lines.append("## Acquisitions with missing `metadata.json` sidecar")
        lines.append("")
        for a in missing_sidecar:
            lines.append(f"- `{a}`")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Interpreting this report")
    lines.append("")
    lines.append("The **Required-backfill** column is the headline number. For each of those acquisitions, Phase 4 must:")
    lines.append("1. Reconstruct disease/control state from study notebooks (operator + researcher recall)")
    lines.append("2. Reconstruct subject demographics from the animal-facility-DB (once Phase 1 access lands) OR from researcher recall")
    lines.append("3. Re-write the sidecar with populated `subject:` + `condition:` blocks (either via idempotent re-ingest if staging is available, or via standalone `subject_condition_backfill.py`)")
    lines.append("")
    lines.append("The **Conditional** column needs operator judgement per cell-line whether the underlying organism context warrants the blocks.")
    lines.append("")
    lines.append("The **Unset** column flags rows where `sample_type` itself wasn't populated at ingest — those need a sample_type audit before they can be classified for backfill.")
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--nas-root", default="J:/")
    p.add_argument("--out", default="tasks/phase4_backfill_inventory.md")
    args = p.parse_args()

    rows = []
    for acq, md_path, md in walk_raw(args.nas_root):
        sample_type, instrument, has_subj, has_cond = classify(md)
        rows.append((acq, md_path, sample_type, instrument, has_subj, has_cond))

    report = render_report(rows, args.nas_root)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Wrote {args.out} ({len(rows)} acquisitions walked)")


if __name__ == "__main__":
    main()
