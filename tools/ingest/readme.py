"""Generate README.txt for acquisition folders."""

import os
from pathlib import Path


def get_template_path():
    """Return path to the README template."""
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "templates",
        "README_raw.txt",
    )


def generate_readme(acq_id, cfg, summary, dest_dir):
    """Generate README.txt in the destination directory.

    Args:
        acq_id: The ACQ-ID string.
        cfg: Single-case config dict.
        summary: Source summary dict.
        dest_dir: Acquisition folder path.
    """
    template_path = get_template_path()
    with open(template_path, "r") as f:
        template = f.read()

    study_date = summary.get("study_date", "")
    if study_date and len(study_date) == 8:
        acq_date_fmt = f"{study_date[:4]}-{study_date[4:6]}-{study_date[6:8]}"
    else:
        acq_date_fmt = cfg.get("acquisition_date", "unknown")

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
