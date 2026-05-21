"""Read-only probe of a Bruker ParaVision exam folder's metadata.

Standalone utility — not part of the ingest pipeline. Intended to be run
once per representative sample to inform follow-up extraction work
(09_MODALITIES MRI section, 4.5 round-6) by dumping the curated
`discovered.mri_*` subset, the structured `mri:` block, and the full
parsed JCAMP-DX `_raw_metadata` to a JSON snapshot reviewers can grep.

Usage:
    python -m tools.ingest.probe_paravision <path-to-exam-folder> \\
        [--out _probes/<study>__<exam>.json]

Reads metadata only — does not touch image data, does not write to
the source.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import paravision_metadata


def probe(exam_path):
    """Read a ParaVision exam folder and return a JSON-serialisable probe.

    Returns:
        {
          "path", "study_path", "exam_number", "probed_at",
          "discovered": {...},          # curated discovered.mri_*
          "mri_section": {              # structured mri: block
              "subject", "acquisition", "geometry", "reconstruction",
              "_raw_metadata"
          },
          "exposed_field_descriptions": [{key, description}, ...],
        }
    """
    exam = Path(exam_path).resolve()
    discovered, section = paravision_metadata.extract(str(exam))

    return {
        "path": str(exam),
        "study_path": str(exam.parent),
        "exam_number": exam.name,
        "probed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "discovered": discovered,
        "mri_section": section,
        "exposed_field_descriptions": [
            {"key": k, "description": desc}
            for k, _, desc in paravision_metadata.EXPOSED_FIELDS
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "exam_path",
        help="Path to one ParaVision exam folder (e.g. .../<study>/29/)",
    )
    p.add_argument(
        "--out",
        default=None,
        help="Output JSON file (default: _probes/<study>__<exam>.json)",
    )
    args = p.parse_args(argv)

    exam = Path(args.exam_path)
    if not exam.is_dir():
        print(f"ERROR: not a directory: {exam}", file=sys.stderr)
        return 2

    out_path = args.out
    if out_path is None:
        os.makedirs("_probes", exist_ok=True)
        # Use <study-basename>__<exam-basename> to avoid collisions when
        # the same exam number exists across multiple studies.
        tag = f"{exam.parent.name}__{exam.name}.json"
        out_path = os.path.join("_probes", tag)

    result = probe(args.exam_path)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    n_disc = sum(1 for v in result["discovered"].values() if v != "")
    n_total = len(result["discovered"])
    n_recons = len(result["mri_section"]["reconstruction"]["indices_present"])
    raw_keys = sum(
        len(result["mri_section"]["_raw_metadata"][k])
        for k in ("subject", "acqp", "method", "visu_pars")
    )
    print(
        f"Wrote {out_path}\n"
        f"  discovered.mri_*: {n_disc}/{n_total} fields populated\n"
        f"  reconstructions: {n_recons} present "
        f"({','.join(result['mri_section']['reconstruction']['indices_present'])})\n"
        f"  _raw_metadata: {raw_keys} top-level keys across subject/acqp/method/visu_pars"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
