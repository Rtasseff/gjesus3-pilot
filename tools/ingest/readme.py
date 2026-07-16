"""Generate README.txt for acquisition folders."""

import os
from pathlib import Path

from . import resources


def get_template_path():
    """Return the path to the README template.

    Resolves from a source checkout AND a frozen PyInstaller bundle
    (sys._MEIPASS-aware) via ingest/resources.py. The old naive
    dirname(dirname(__file__)) path broke inside the frozen exe — it looked for
    README_raw.txt under <_MEIPASS>/templates, where it was never bundled.
    """
    return resources.resource_path("templates", "README_raw.txt")


def generate_readme(acq_id, cfg, summary, dest_dir):
    """Generate README.txt in the destination directory.

    Args:
        acq_id: The ACQ-ID string.
        cfg: Single-case config dict.
        summary: Source summary dict.
        dest_dir: Acquisition folder path.
    """
    template_path = get_template_path()
    if not os.path.exists(template_path):
        # Fail legibly: this was the frozen-exe crash, and a bare Errno 2 on a
        # temp _MEIxxxx path took a production incident to diagnose. Name the
        # real cause so a future bundling regression is self-explaining.
        raise FileNotFoundError(
            f"README template not found at {template_path!r}. In a frozen build "
            f"this means tools/templates/README_raw.txt was not bundled into the "
            f"exe — add it to `datas` in tools/operator/gui/gjesus3_ingest.spec."
        )
    with open(template_path, "r") as f:
        template = f.read()

    study_date = summary.get("study_date", "")
    if study_date and len(study_date) == 8:
        acq_date_fmt = f"{study_date[:4]}-{study_date[4:6]}-{study_date[6:8]}"
    else:
        # The pipeline sets cfg["acquisition_datetime"] (resolved ISO), never a
        # top-level "acquisition_date" — fall back to the date portion of the
        # datetime (the part before "T"); else "unknown".
        acq_dt = cfg.get("acquisition_datetime", "")
        acq_date_fmt = acq_dt.split("T", 1)[0] if acq_dt else "unknown"

    from datetime import datetime, timezone
    reg_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    values = {
        "acq_id": acq_id,
        "data_ecosystem": cfg.get("data_ecosystem", ""),
        "instrument": cfg.get("instrument", ""),
        "instrument_model": cfg.get("instrument_model", ""),
        "operator": cfg.get("operator", ""),
        "data_source": cfg.get("data_source", ""),
        "acquisition_date": acq_date_fmt,
        "registration_date": reg_date,
        "sample_id": cfg.get("sample_id", ""),
        "sample_type": cfg.get("sample_type", ""),
        "original_name": cfg.get("original_name", ""),
        "primary_file_name": cfg.get("primary_file_name", "series/"),
        "file_format": cfg.get("file_format", ".dcm"),
        "file_count": summary.get("file_count", 0),
        "file_size_mb": summary.get("total_size_mb", 0),
        "notes": cfg.get("notes", ""),
    }

    content = template.format(**values)

    readme_path = os.path.join(dest_dir, "README.txt")
    with open(readme_path, "w") as f:
        f.write(content)
