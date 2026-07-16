#!/usr/bin/env python3
"""dicomifier_driver.py — run the `dicomifier` CLI with workaround #3 applied.

Dicomifier 2.5.3 (and current upstream master, checked 2026-07-16) has two
defects in `bruker_to_dicom/modules/image.py::get_pixel_data`, in the branch
handling data stored `disk_reverse_slice_order`:

  1. CRASH on a plain single 3D volume. `mr_image_storage` runs
     `convert.to_2d` on a `VisuCoreDim=3` data set, which synthesizes ONE
     frame group (`FG_SLICE`). `get_pixel_data` then collects the frame
     groups BEFORE the slice group into `volume_groups` — empty — and
     computes `numpy.cumprod([])[-1]` -> IndexError. The volume count for an
     empty `volume_groups` is exactly 1. This is why every one of the 153
     backfillable no-DICOM exams (all single-frame 3D FISP/FcFLASH stored
     reverse-order) fails to convert; multi-frame-group exams sail past.

  2. The slice flip is a NO-OP. `view = numpy.flip(view, axis=1)` rebinds a
     local name to a reversed VIEW and never writes back to
     `data_set["PIXELDATA"]` — so even when the branch doesn't crash, the
     promised re-ordering ("Invert the slice order") never happens.

The patched copy below fixes both: volume count defaults to 1 when there are
no volume groups, and the flip is MATERIALIZED back into PIXELDATA (the data
really is stored in reverse slice order; `convert.to_2d` computes per-slice
ImagePositionPatient in ascending logical order, so serving disk order
unflipped would mirror the volume along z against its recorded geometry).

HOW THE PATCH IS APPLIED. `image.get_pixel_data` is referenced by module-
level converter tables (e.g. `image.ImagePixel`) that bind the FUNCTION
OBJECT at import time, so rebinding the module attribute is not enough. The
function's `__code__` is swapped in place instead — every table that holds
the object sees the fix. Both functions are plain module-level functions
(no closure), and the patched body references only names resolvable in the
original module's globals (`numpy` + builtins), which is what `__code__`
swapping requires. SELF-DISABLING: the swap only happens when the installed
source still contains the two buggy lines; a future fixed Dicomifier runs
stock and a WARN is printed if the source has changed in an unrecognized way.

Usage — exactly like the `dicomifier` CLI (paravision_regen invokes this in
place of the bare binary):

    python tools/ingest/dicomifier_driver.py to-dicom --layout flat <src> <dst>

Same class of issue as the two output-side workarounds already carried by
`paravision_regen.py` (PixelSpacing axis swap, invalid Window tags); an
upstream issue draft accompanies those two.
"""

import inspect
import sys


def _patched_get_pixel_data(data_set, generator, frame_index):
    """ Read the pixel data and return the given frame.
        This function MUST be called before converting VisuCoreDataOffs and
        VisuCoreDataSlope.
    """
    # Verbatim copy of Dicomifier 2.5.3 get_pixel_data with two fixes marked
    # [gjesus3-fix] below. Executes with the ORIGINAL module's globals after
    # the __code__ swap, so `numpy` resolves to the import in image.py.

    if isinstance(data_set["PIXELDATA"], list):
        dtype = {
            "_8BIT_UNSGN_INT": numpy.uint8,  # noqa: F821 — image.py globals
            "_16BIT_SGN_INT": numpy.int16,  # noqa: F821
            "_32BIT_SGN_INT": numpy.int32,  # noqa: F821
            "_32BIT_FLOAT": numpy.single,  # noqa: F821
        }[data_set["VisuCoreWordType"][0]]

        # Read the file
        with open(str(data_set["PIXELDATA"][0]), "rb") as fd:
            data_set["PIXELDATA"] = numpy.fromfile(fd, dtype)  # noqa: F821

        frame_size = data_set["VisuCoreSize"][0]*data_set["VisuCoreSize"][1]
        data_set["PIXELDATA"].resize(
            len(data_set["PIXELDATA"])//frame_size, frame_size)

        if data_set["PIXELDATA"].dtype == numpy.single:  # noqa: F821
            # Map to uint32
            min = numpy.nanmin(data_set["PIXELDATA"])  # noqa: F821
            max = numpy.nanmax(data_set["PIXELDATA"])  # noqa: F821

            # WARNING: whe using float32, all numbers between (2**32-128) and
            # (2**32+256) have the same representation, which can yield to
            # invalid values when converting to integer. Use the immediately
            # inferior value as an upper bound of the integer range.
            scale = numpy.nextafter(  # noqa: F821
                numpy.single(2**32), numpy.single(0)) / (max-min)  # noqa: F821
            data_set["PIXELDATA"] -= min
            data_set["PIXELDATA"] *= scale
            data_set["PIXELDATA"] = data_set["PIXELDATA"].astype(
                numpy.uint32)  # noqa: F821

            data_set["VisuCoreDataOffs"] = [0]*len(data_set["VisuCoreDataOffs"])
            data_set["VisuCoreDataSlope"] = [1]*len(data_set["VisuCoreDataOffs"])

            if "VisuCoreDataOffs" in data_set:
                data_set["VisuCoreDataOffs"] = [
                    x+min for x in data_set["VisuCoreDataOffs"]]
            if "VisuCoreDataSlope" in data_set:
                data_set["VisuCoreDataSlope"] = [
                    x/scale for x in data_set["VisuCoreDataSlope"]]

    if data_set.get("VisuCoreDiskSliceOrder", [None])[0] == "disk_reverse_slice_order":
        # Volumes are always in order, but slice order depends on
        # VisuCoreDiskSliceOrder. Re-order in place, then proceed as in the
        # non-reversed case.

        # Get the frame groups before the slice group
        volume_groups = []
        for group in generator.frame_groups:
            if group[1] != "FG_SLICE":
                volume_groups.append(group)
            else:
                break

        # [gjesus3-fix 1] a plain single 3D volume has NO frame groups before
        # the FG_SLICE group convert.to_2d synthesized: the volume count is 1,
        # not cumprod([])[-1] (IndexError upstream).
        if volume_groups:
            n_volumes = numpy.cumprod(  # noqa: F821
                [x[0] for x in volume_groups])[-1]
        else:
            n_volumes = 1

        # [gjesus3-fix 2] Invert the slice order FOR REAL. Upstream rebinds a
        # local to numpy.flip's returned view and never writes back, so the
        # promised inversion silently never happened. Materialize the flip
        # into PIXELDATA (copy() breaks the overlapping-view aliasing).
        view = data_set["PIXELDATA"].reshape(
            (n_volumes, -1, data_set["PIXELDATA"].shape[-1]))
        view[:] = view[:, ::-1, :].copy()

        # Mark slice order as normal
        data_set["VisuCoreDiskSliceOrder"] = ["disk_normal_slice_order"]

    frame_index = generator.get_linear_index(frame_index)
    frame_data = data_set["PIXELDATA"][frame_index]

    return [bytearray(frame_data.tobytes())]


# The two defective upstream lines; the patch is applied only while BOTH are
# present in the installed source (self-disabling on a future fixed release).
_BUGGY_MARKERS = (
    "numpy.cumprod([x[0] for x in volume_groups])[-1]",
    "view = numpy.flip(view, axis=1)",
)


def apply_patch(log=lambda msg: print(msg, file=sys.stderr)):
    """Swap the fix into the installed Dicomifier if it is still buggy.

    Returns 'patched' | 'not-needed' | 'unrecognized'. 'unrecognized' means
    the installed get_pixel_data matches NEITHER the known-buggy 2.5.3 shape
    nor a shape missing both markers — a WARN, and stock code runs (never
    guess on someone else's pixel path).
    """
    from dicomifier.bruker_to_dicom.modules import image
    src = inspect.getsource(image.get_pixel_data)
    present = [m for m in _BUGGY_MARKERS if m in src]
    if len(present) == len(_BUGGY_MARKERS):
        image.get_pixel_data.__code__ = _patched_get_pixel_data.__code__
        return "patched"
    if not present:
        return "not-needed"
    log("dicomifier_driver: installed get_pixel_data only partially matches "
        "the known-buggy shape — NOT patching; running stock Dicomifier. "
        "Re-validate the regeneration path against this Dicomifier version.")
    return "unrecognized"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    state = apply_patch()
    print(f"dicomifier_driver: workaround #3 state: {state}", file=sys.stderr)
    from dicomifier.__main__ import main as dicomifier_main
    sys.argv = ["dicomifier"] + argv
    return dicomifier_main()


if __name__ == "__main__":
    sys.exit(main())
