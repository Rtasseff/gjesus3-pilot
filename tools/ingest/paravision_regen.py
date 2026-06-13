"""ParaVision → DICOM regeneration via Dicomifier subprocess + PV-7 workarounds.

Phase 2 of FID→DICOM regeneration (`tasks/tasks.md §3.1`). For ParaVision
exams where the researcher didn't run Bruker's GUI DICOM exporter (no
`pdata/<idx>/dicom/*.dcm` subfolders), regenerate the per-frame DICOMs
from the existing `2dseq` + JCAMP-DX aux files using Dicomifier 2.5.3.

Two confirmed PV-7 bugs require workarounds applied per file (visual
verification 2026-06-01; see `tasks/tasks.md §3.1` findings 1 + 1b):

  1. PixelSpacing axis-order — Dicomifier emits `[col, row]` instead of
     DICOM Part 3's `[row, col]`. Fix: swap.
  2. Window tags — Dicomifier emits `WindowWidth=0` (invalid;
     DICOM PS3.3 C.11.2.1.2 requires width > 0). Fix: delete bogus
     WindowCenter/WindowWidth; set Smallest/LargestImagePixelValue from
     pixel array min/max (matches Bruker convention).

After applying both, the output renders identically to Bruker GUI export
in 3D Slicer / ITK-SNAP.

Public API:

  regenerate_exam_dicoms(exam_path, output_dir, log_fn) -> int
      Run Dicomifier on a single exam, apply workarounds, materialize
      under output_dir as pdata/<idx>/dicom/MRIm<NN>.dcm. Returns the
      count of regenerated DICOMs. Raises RuntimeError on failure.

  prepare_virtual_exam(exam_path, work_dir, log_fn) -> Path
      Build a complete "virtual exam" under work_dir that copies the
      original JCAMP-DX aux files + pdata aux (visu_pars/reco/2dseq) AND
      runs the regeneration. The returned path can be passed to
      `paravision_metadata.load_paravision_exam()` and
      `ingest_raw.copy_mri_paravision()` as if it were a normal
      Bruker-GUI-exported source.

  check_dicomifier_available() -> (bool, version_string_or_None)
      Probe whether `dicomifier` is on PATH. Use this before depending
      on regeneration in an ingest config.

Mapping from Dicomifier flat output → pdata/<idx>/dicom/ structure:

  Each Dicomifier-generated DICOM carries SeriesNumber encoded as
    (exam_number << 16) | pdata_index
  and InstanceNumber = frame number (1-based). The mapping is:
    pdata_index = SeriesNumber & 0xFFFF
    frame_n     = InstanceNumber
  Destination file: <output>/pdata/<pdata_index>/dicom/MRIm<NN>.dcm
  where NN is the frame number zero-padded to 2 digits.

Verified 2026-06-01 against m17 staged source (16 anisotropic series +
3 square series); encoding holds deterministically across all observed
PV-7 cardiac and anatomical sequences.

Standalone use:

    python -m tools.ingest.paravision_regen <exam_path> <output_dir>

  or, from the repo root with the dicomifier-pilot env active:

    python tools/ingest/paravision_regen.py <exam_path> <output_dir>
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# pydicom is required (not optional like in paravision_metadata.py)
import pydicom

from . import jcampdx


DICOMIFIER_BIN = "dicomifier"  # assumed on PATH; conda env's bin dir

# Acquisition methods that are NOT 2D/3D image data and must NOT be run through
# the image-DICOM regeneration path: Dicomifier emits an MR-Spectroscopy object
# (or out-of-range "pixel" data), which the image workarounds below then crash
# on (the int16 struct.error). These need a SEPARATE ingest path (not image
# regeneration) — see tasks/BACKLOG. Matched as a case-insensitive substring of
# the Bruker method / pulse-program name. Extend as new non-image types appear.
_NONIMAGE_METHOD_MARKERS = ("STEAM", "PRESS", "WOBBLE")


def _exam_method_signature(exam_path):
    """Best-effort lower-cased method + pulse-program name for an exam, read from
    its JCAMP-DX `method` (`Method`) + `acqp` (`PULPROG`) files. '' if unreadable."""
    exam_path = Path(exam_path)
    parts = []
    for fname, key in (("method", "Method"), ("acqp", "PULPROG")):
        try:
            parsed = jcampdx.parse_file(exam_path / fname)
            if parsed.get(key):
                parts.append(str(parsed[key]))
        except Exception:
            pass
    return " ".join(parts).lower()


def is_nonimage_exam(exam_path):
    """Return (True, marker) if the exam is a spectroscopy/calibration acquisition
    (STEAM / PRESS / Wobble / ...) that must NOT go through image-DICOM
    regeneration; (False, '') for a normal image exam."""
    sig = _exam_method_signature(exam_path)
    for marker in _NONIMAGE_METHOD_MARKERS:
        if marker.lower() in sig:
            return True, marker
    return False, ""


# Tags we modify; keep this list in sync with the tasks.md spec to make
# the workaround easy to identify in pydicom.dcmread output.
_TAG_PIXEL_SPACING = (0x0028, 0x0030)
_TAG_WINDOW_CENTER = (0x0028, 0x1050)
_TAG_WINDOW_WIDTH = (0x0028, 0x1051)
_TAG_SMALLEST_IMG_PIX = (0x0028, 0x0106)
_TAG_LARGEST_IMG_PIX = (0x0028, 0x0107)


def check_dicomifier_available():
    """Return (True, version) if `dicomifier --version` works; (False, None) otherwise.

    Use this before relying on regeneration in an ingest config — the
    Dicomifier env may not be active on every workstation.
    """
    try:
        r = subprocess.run(
            [DICOMIFIER_BIN, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        ver = (r.stdout or r.stderr).strip()
        if r.returncode == 0:
            return True, ver
        return False, None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False, None


def _apply_workarounds_inplace(dcm_path):
    """Apply both PV-7 workarounds to a Dicomifier-generated DICOM in-place.

    Returns (pdata_idx, frame_n) extracted from the DICOM headers
    (SeriesNumber low 16 bits, InstanceNumber). Used to map this flat-named
    DICOM to its canonical pdata/<idx>/dicom/MRIm<NN>.dcm location.

    Raises RuntimeError if PixelRepresentation is unset (we need it to
    pick SS vs US VR for Smallest/LargestImagePixelValue).
    """
    ds = pydicom.dcmread(str(dcm_path))

    # Workaround 1: swap PixelSpacing[0] and PixelSpacing[1]
    ps = ds.get("PixelSpacing")
    if ps and len(ps) == 2:
        ds.PixelSpacing = [ps[1], ps[0]]

    # Workaround 2: delete bogus Window tags; add Smallest/LargestImagePixelValue
    if "WindowCenter" in ds:
        del ds.WindowCenter
    if "WindowWidth" in ds:
        del ds.WindowWidth

    arr = ds.pixel_array
    # VR is SS for signed int16 (PixelRepresentation=1), US for unsigned (=0).
    pix_repr = ds.get("PixelRepresentation")
    if pix_repr is None:
        raise RuntimeError(
            f"PixelRepresentation tag missing on {dcm_path} — cannot pick "
            f"SS vs US VR for Smallest/LargestImagePixelValue. Likely a "
            f"deeper Dicomifier issue; investigate before continuing."
        )
    vr = "SS" if int(pix_repr) == 1 else "US"
    # Smallest/LargestImagePixelValue are optional display hints valid only for
    # integer image data within the 16-bit SS/US range. Spectroscopy or any
    # out-of-range "pixel" data would overflow the SS/US packing (struct.error)
    # and crash the batch — guard the range and skip these optional tags rather
    # than fail. (Non-image acquisitions should already be filtered upstream by
    # is_nonimage_exam(); this is the per-file backstop.)
    lo, hi = int(arr.min()), int(arr.max())
    vr_lo, vr_hi = (-32768, 32767) if vr == "SS" else (0, 65535)
    if vr_lo <= lo <= vr_hi and vr_lo <= hi <= vr_hi:
        ds.add_new(_TAG_SMALLEST_IMG_PIX, vr, lo)
        ds.add_new(_TAG_LARGEST_IMG_PIX, vr, hi)

    ds.save_as(str(dcm_path))

    # Extract pdata index + frame for the caller's organization step
    sn = int(ds.SeriesNumber)
    pdata_idx = sn & 0xFFFF
    frame_n = int(ds.InstanceNumber)
    return pdata_idx, frame_n


def regenerate_exam_dicoms(exam_path, output_dir, log_fn):
    """Run Dicomifier on one ParaVision exam, apply workarounds, organize output.

    Args:
        exam_path: Path or str to a ParaVision exam folder (e.g. `<study>/29/`).
        output_dir: Path or str where pdata/<idx>/dicom/MRIm<NN>.dcm structure
            will be materialized. The directory is created if it doesn't
            exist; existing files are overwritten.
        log_fn: callable matching ingest_raw.log_fn signature `(msg, level="INFO")`.

    Returns:
        Number of DICOMs successfully regenerated and organized.

    Raises:
        RuntimeError if Dicomifier is unavailable, the subprocess fails,
        or no DICOMs are produced (likely indicates a malformed exam).
    """
    exam_path = Path(exam_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Skip non-image acquisitions (spectroscopy STEAM/PRESS, Wobble, ...) BEFORE
    # spending a Dicomifier run: they are not image data, so image-DICOM
    # regeneration doesn't apply and the workarounds would crash on the output.
    # Raising here is caught by copy_mri_paravision -> WARN + empty .data/
    # placeholder + continue (no batch abort). They need a separate ingest path.
    nonimage, marker = is_nonimage_exam(exam_path)
    if nonimage:
        raise RuntimeError(
            f"{exam_path.name}: non-image acquisition (method matches "
            f"'{marker}' — spectroscopy/calibration). DICOM image regeneration "
            f"is not applicable; this acquisition needs separate handling "
            f"(tasks/BACKLOG). Skipping regeneration."
        )

    ok, ver = check_dicomifier_available()
    if not ok:
        raise RuntimeError(
            "Dicomifier not found on PATH. Install via "
            "`conda install -c conda-forge dicomifier` and ensure the env "
            "is active when running ingest. See tasks/tasks.md §3.1."
        )
    log_fn(f"Running Dicomifier {ver} on {exam_path}")

    with tempfile.TemporaryDirectory(prefix="dicomifier_flat_") as flat_tmp:
        r = subprocess.run(
            [DICOMIFIER_BIN, "to-dicom", "--layout", "flat",
             str(exam_path), flat_tmp],
            capture_output=True, text=True, timeout=600,
        )
        if r.returncode != 0:
            log_fn(
                f"  Dicomifier failed (exit {r.returncode}): "
                f"{r.stderr.strip() or r.stdout.strip()}",
                "ERROR",
            )
            raise RuntimeError(f"Dicomifier failed for {exam_path}")

        flat_files = sorted(f for f in os.listdir(flat_tmp) if f.endswith(".dcm"))
        if not flat_files:
            raise RuntimeError(
                f"Dicomifier produced no DICOMs for {exam_path}. "
                f"Possible causes: malformed exam (missing 2dseq or "
                f"visu_pars), unsupported acquisition type, or a "
                f"Dicomifier upstream bug on this ParaVision version."
            )

        log_fn(f"  Dicomifier produced {len(flat_files)} flat DICOM(s); applying workarounds")
        n_organized = 0
        n_failed = 0
        per_pdata = {}
        for fname in flat_files:
            src = os.path.join(flat_tmp, fname)
            # Per-file backstop: a stray non-image frame (e.g. a spectroscopy
            # object that slipped past is_nonimage_exam) must not abort the whole
            # exam — skip it with a WARN.
            try:
                pdata_idx, frame_n = _apply_workarounds_inplace(src)
            except Exception as e:
                n_failed += 1
                log_fn(f"  Skipping {fname}: workaround failed ({e})", "WARN")
                continue
            per_pdata.setdefault(pdata_idx, 0)
            per_pdata[pdata_idx] += 1
            dicom_dir = output_dir / "pdata" / str(pdata_idx) / "dicom"
            dicom_dir.mkdir(parents=True, exist_ok=True)
            dst = dicom_dir / f"MRIm{str(frame_n).zfill(2)}.dcm"
            shutil.copy2(src, dst)
            n_organized += 1

        if n_organized == 0:
            raise RuntimeError(
                f"All {len(flat_files)} regenerated DICOM(s) failed the "
                f"workarounds for {exam_path} — likely a non-image acquisition; "
                f"needs separate handling (tasks/BACKLOG)."
            )
        summary = ", ".join(f"pdata/{k}: {v}" for k, v in sorted(per_pdata.items()))
        msg = f"  Organized into pdata/<idx>/dicom/: {summary}"
        if n_failed:
            msg += f" ({n_failed} frame(s) skipped)"
        log_fn(msg)
        return n_organized


# Exam-level aux files copied verbatim into the virtual exam (so
# load_paravision_exam's JCAMP-DX parsing works unchanged). Files we
# don't recognize are simply skipped.
_EXAM_AUX_FILES = (
    "acqp", "method", "visu_pars",
    "AdjStatePerScan", "configscan",
    "fid",  # raw k-space; kept so future improvements can re-reconstruct
    "pulseprogram", "specpar",
    "uxnmr.info", "uxnmr.par",
)

# Per-recon aux files (under pdata/<idx>/) — parsed by load_paravision_exam.
_PDATA_AUX_FILES = (
    "visu_pars", "reco", "2dseq",
    "id", "procs", "methreco",
)


def prepare_virtual_exam(exam_path, work_dir, log_fn):
    """Materialize a complete virtual exam under work_dir.

    Output layout matches a normal Bruker-GUI-exported exam:

        <work_dir>/                              <-- exam root
            acqp, method, visu_pars, subject_link (parent file)
            fid, pulseprogram, ...
            pdata/
              <idx>/
                visu_pars, reco, 2dseq, ...
                dicom/
                  MRIm01.dcm  (regenerated + workarounds)
                  ...

    The study-level `subject` file is copied to BOTH the exam root AND
    work_dir.parent (because `load_paravision_exam` reads it from the
    exam's parent dir). This dual-placement avoids needing to set up a
    parent-of-parent scratch hierarchy.

    Args:
        exam_path: original ParaVision exam folder (lacks pdata/<idx>/dicom/).
        work_dir: destination scratch root. Created if missing.
        log_fn: log function.

    Returns:
        Path to the populated work_dir (== the new exam path).

    Raises RuntimeError if regeneration fails.
    """
    exam_path = Path(exam_path)
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    log_fn(f"Preparing virtual exam under {work_dir}")

    # Exam-level aux files
    for aux_name in _EXAM_AUX_FILES:
        src = exam_path / aux_name
        if src.is_file():
            shutil.copy2(src, work_dir / aux_name)

    # Study-level subject file: place it at work_dir.parent / "subject"
    # so that load_paravision_exam(work_dir) finds it via exam.parent.
    study_subj = exam_path.parent / "subject"
    if study_subj.is_file():
        parent = work_dir.parent
        parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(study_subj, parent / "subject")

    # Per-recon aux files
    pdata_root = exam_path / "pdata"
    if pdata_root.is_dir():
        for sub in sorted(pdata_root.iterdir()):
            if not sub.is_dir():
                continue
            idx = sub.name
            out_sub = work_dir / "pdata" / idx
            out_sub.mkdir(parents=True, exist_ok=True)
            for f in _PDATA_AUX_FILES:
                s = sub / f
                if s.is_file():
                    shutil.copy2(s, out_sub / f)

    # Regenerated DICOMs
    n = regenerate_exam_dicoms(exam_path, work_dir, log_fn)
    log_fn(f"Virtual exam ready at {work_dir} ({n} DICOMs across pdata/<idx>/dicom/)")
    return work_dir


# ---------------------------------------------------------------- CLI

def _default_log(msg, level="INFO"):
    print(f"[{level}] {msg}", flush=True)


def _main(argv):
    if len(argv) < 3:
        print("Usage: python paravision_regen.py <exam_path> <output_dir>", file=sys.stderr)
        print(
            "Runs Dicomifier on <exam_path>, applies PV-7 workarounds, "
            "and writes the DICOMs in pdata/<idx>/dicom/ structure under "
            "<output_dir>. Useful for offline testing before wiring into "
            "the ingest pipeline.",
            file=sys.stderr,
        )
        return 2
    exam_path, output_dir = argv[1], argv[2]
    try:
        n = regenerate_exam_dicoms(exam_path, output_dir, _default_log)
    except RuntimeError as e:
        _default_log(str(e), "ERROR")
        return 1
    _default_log(f"Done - {n} DICOMs regenerated and organized.")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
