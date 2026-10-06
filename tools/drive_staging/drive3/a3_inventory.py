"""A3 step 1 -- inventory every segmentation-relevant file on drive 3 (read-only; manifest only).

Selects, from the coordinator's manifest (drive3_manifest.csv, 621,969 rows):
  * every file under Otros\\Segmentaciones ITK SNAP (the folder the hub flagged, all 41,728 files,
    so the folder is accounted for in full), and
  * anywhere on the drive: label-capable formats (.nii/.nii.gz/.mha/.nrrd/.hdr/.img), MetaImage
    split volumes (.mhd/.raw), PMOD VOIs (.voi/.voistat), ITK-SNAP / Amira label descriptors,
    Amira files, meshes (.vtk/.stl), microscopy annotations (.ndpa, QuPath .qpdata/.qpproj) and the
    trained segmentation models (.h5 under Seg_models).
Each row gets a first role guess from its name and folder. The final label/image decision for
NIfTI/MetaImage files is made from the voxel census in a3_headers.py (a name is never enough:
'MPAflow_m203_0619.nii.gz' turns out to be a mask, 'Time10_m160_0619.nii.gz' too).

Output: D:\\projects\\gjesus3\\drive3_analysis\\a3\\a3_inventory.csv
"""
import os
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a3_common as C  # noqa: E402

LABEL_FMT = {".nii", ".nii.gz", ".mha", ".nrrd", ".seg.nrrd", ".hdr", ".img"}
OTHER_FMT = {".voi": "voi_pmod", ".voistat": "aux_voistat", ".label": "label_descriptor_itksnap",
             ".labels": "amira_labelfield", ".am": "amira_data", ".hx": "amira_project",
             ".vtk": "mesh", ".stl": "mesh", ".ndpa": "annotation_ndp", ".qpdata": "annotation_qupath",
             ".qpproj": "annotation_qupath_project"}
ITK_FOLDER = "Otros\\Segmentaciones ITK SNAP\\"

# Names that are images, not labels (confirmed by the census, used only as a first guess)
IMAGE_NAME = re.compile(r"(?i)^(ID\d+_)?(Cine_|Velocity_map|\d+_Planning|\d+_Localizer|Localizer|Planning|FLASH|RARE|"
                        r"T2_|T1_|SUV|CT[-_ ]|PET|IRENE_|m\d+[-_]ct|m\d+_suv|CineMPA|Cine|.*_FF\.nii\.gz$|"
                        r"m\d+_\d+\.nii$|grasas)")
LABEL_NAME = re.compile(r"(?i)(segm|sgement|segmet|segment|mask|label|massventric|_seg\b|seg_|voi|roi|"
                        r"MPAflow|FlowMPA|PA_flujo|PA_Flujo|^time\s*\d+|^T\d+-m|^Time\s*\d+[-_ ]|body\d+)")
PHASE_RE = [re.compile(r"(?i)time[\s_-]*(\d{1,2})(?!\d)"), re.compile(r"(?i)flujo_(?:time_?)?(\d{1,2})(?!\d)"),
            re.compile(r"(?i)^T(\d{1,2})-m"), re.compile(r"(?i)-t(\d{1,2})-segment")]
READER_HINTS = [("MJ", re.compile(r"(?i)(^MJ[_-]|[-_]MJ\.nii|An[aá]lisis MJ|MJ Experimento|_MJ\\|\\MJ[-_ ])")),
                ("IAZ", re.compile(r"(?i)(^IAZ_|IAZ_MJ)")),
                ("IRE", re.compile(r"(?i)(_IRE\.nii|_IRE_|segm_IRE)")),
                ("IF", re.compile(r"(?i)_IF\.nii")),
                ("Ermal", re.compile(r"(?i)ermal")),
                ("JRC", re.compile(r"(?i)Segmentation by JRC")),
                ("Unai", re.compile(r"(?i)Analisis Unai")),
                ("Lucia", re.compile(r"(?i)Luc[ií]a")),
                ("Irati", re.compile(r"(?i)Irati")),
                ("kevin", re.compile(r"(?i)kevin")),
                ("Ehsam", re.compile(r"(?i)Ehsam"))]


def role_guess(relpath, name, ext):
    low = relpath.lower()
    if C.is_junk(name):
        return "junk"
    if ext in (".mhd", ".raw"):
        nl = name.lower()
        # 2019 rat folder: model output and its post-processed / hand-modified versions are MetaImage LABELS
        if nl.startswith(("pred_", "postprocessed_", "modificated_")):
            return "metaimage_label?"
        if nl.startswith("time_") or "flujo" in nl or "\\split" in low:
            return "image_split"
        return "metaimage_unknown?"
    if ext == ".h5":
        return "model_weights"
    if ext in OTHER_FMT:
        return OTHER_FMT[ext]
    if ext in (".filtered", ".opening") and "amira" in low:
        return "amira_intermediate"
    if ext in LABEL_FMT:
        if "\\predict_slicer\\" in low or name.lower().endswith("_cardiac_segmentation.mha"):
            return "nifti_model_prediction?"
        if LABEL_NAME.search(name):
            return "nifti_label?"
        if IMAGE_NAME.search(name):
            return "nifti_image?"
        return "nifti_unknown?"
    if "\\dicom\\" in low and ext == "":
        return "image_dicom_source"   # Philips export: IM_nnnn images, XX_/PS_ private objects
    if name.upper() == "DICOMDIR":
        return "image_dicom_index"
    if ext == ".cache":
        return "aux_cache"
    if ext == ".pdf":
        return "document"
    return "other"


def phase_of(name):
    for rx in PHASE_RE:
        m = rx.search(name)
        if m:
            return m.group(1)
    return ""


def main():
    rows = C.read_csv_dicts(C.MANIFEST)
    out = []
    for r in rows:
        rel = r["relpath"]
        name = rel.rsplit("\\", 1)[-1]
        ext = C.ext_of(name)
        in_itk = rel.startswith(ITK_FOLDER)
        selected = in_itk or (not C.is_junk(name) and (
            ext in LABEL_FMT or ext in OTHER_FMT or ext in (".mhd", ".raw")
            or (ext == ".h5" and "seg_models" in rel.lower())
            or (ext in (".filtered", ".opening") and "amira" in rel.lower())))
        if not selected:
            continue
        studies = C.study_tokens(rel)
        sessions = C.session_tokens(rel)
        readers = [k for k, rx in READER_HINTS if rx.search(rel)]
        out.append({
            "relpath": rel, "size": r["size"], "mtime": r["mtime"], "birthtime": r["birthtime"],
            "sha256": r["sha256"], "top": rel.split("\\")[0], "name": name, "ext": ext,
            "in_itk_snap_folder": "Y" if in_itk else "N",
            "role_guess": role_guess(rel, name, ext),
            "phase_from_name": phase_of(name),
            "study_tokens": ";".join(dict.fromkeys(studies)),
            "session_tokens": ";".join(dict.fromkeys(sessions)),
            "project_codes_in_path": ";".join(dict.fromkeys(C.project_codes_in_path(rel))),
            "reader_hints": ";".join(readers),
            "parent": rel.rsplit("\\", 1)[0] if "\\" in rel else "",
        })
    path = C.write_csv(os.path.join(C.OUT_DIR, "a3_inventory.csv"), out)
    from collections import Counter
    c = Counter(o["role_guess"] for o in out)
    print(f"wrote {path}: {len(out)} rows")
    for k, v in c.most_common():
        print(f"  {k:28s} {v}")


if __name__ == "__main__":
    main()
