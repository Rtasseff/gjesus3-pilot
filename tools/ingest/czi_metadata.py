"""Extract metadata from a Zeiss `.czi` file's embedded XML.

Two outputs:

  1. A `discovered.czi_*` flat dict — a curated subset of fields that are
     useful enough for cross-acquisition queries to be referenceable from
     the YAML `registry:` block. Defined by EXPOSED_FIELDS at the bottom
     of this module.

  2. A structured `microscopy:` section for the metadata.json sidecar,
     organized in 5 buckets (geometry, instrument, acquisition, mosaic,
     document_info), preserving everything we currently surface from the
     embedded XML.

Library: `czifile` (pure Python, already in requirements.txt). We only
read the metadata XML — never image pixels — so JPEG-XR compression
support is irrelevant here. The library/route decision is documented in
[10_TOOLS §2.1.3].

Adding a new exposed field is a one-line edit at the bottom of this
file. After editing, also update the matching table in 09_MODALITIES.md
so config authors know what's available.
"""

import os
from xml.etree import ElementTree as ET


# ------------------------------------------------------------------ helpers

def _xml_to_dict(elem):
    """Convert an ElementTree element into a nested dict.

    Same shape as probe_czi.py: attributes go under @attrs, text under
    #text, repeated children become lists. Kept independent of probe_czi
    so callers don't need that module.
    """
    node = {}
    if elem.attrib:
        node["@attrs"] = dict(elem.attrib)
    text = (elem.text or "").strip()
    if text:
        node["#text"] = text
    for child in elem:
        sub = _xml_to_dict(child)
        existing = node.get(child.tag)
        if existing is None:
            node[child.tag] = sub
        elif isinstance(existing, list):
            existing.append(sub)
        else:
            node[child.tag] = [existing, sub]
    return node


def _text(node, *path):
    """Walk a dot-path and return the leaf's #text, or '' if anything is missing."""
    cur = node
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return ""
        cur = cur[p]
    if isinstance(cur, dict):
        return cur.get("#text", "")
    return "" if cur is None else str(cur)


def _attr(node, *path_then_attr):
    """Walk a path to a node and return @attrs[<last>], or ''."""
    *path, attr = path_then_attr
    cur = node
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return ""
        cur = cur[p]
    if not isinstance(cur, dict):
        return ""
    return cur.get("@attrs", {}).get(attr, "")


def _sub(node, *path):
    """Walk a path and return the dict sub-node, or {} if missing."""
    cur = node
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return {}
        cur = cur[p]
    return cur if isinstance(cur, dict) else {}


def _as_list(value):
    """Normalize a child that may be dict, list, or absent into a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


# ------------------------------------------------------------------ XML loading

def load_xml_dict(czi_path):
    """Open a .czi file via czifile, parse its embedded metadata XML.

    Returns the dict-shaped equivalent of the XML root (an ImageDocument
    with a single Metadata child). Raises RuntimeError if czifile isn't
    installed.
    """
    try:
        import czifile  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "czifile is not installed. Run: pip install czifile"
        ) from e
    with czifile.CziFile(czi_path) as czi:
        meta_xml = czi.metadata()
    if isinstance(meta_xml, bytes):
        meta_xml = meta_xml.decode("utf-8", errors="replace")
    root = ET.fromstring(meta_xml)
    return _xml_to_dict(root)


# ------------------------------------------------------------------ buckets

def _build_geometry(md):
    img = _sub(md, "Information", "Image")
    return {
        "size_x":               _text(img, "SizeX"),
        "size_y":               _text(img, "SizeY"),
        "size_z":               _text(img, "SizeZ"),
        "size_c":               _text(img, "SizeC"),
        "size_t":               _text(img, "SizeT"),
        "size_s":               _text(img, "SizeS"),  # scenes
        "size_m":               _text(img, "SizeM"),  # tiles (mosaic)
        "pixel_type":           _text(img, "PixelType"),
        "component_bit_count":  _text(img, "ComponentBitCount"),
        "compression":          _text(img, "OriginalCompressionMethod"),
        "pixel_size_x_um":      _pixel_size_um(md, "X"),
        "pixel_size_y_um":      _pixel_size_um(md, "Y"),
        "pixel_size_z_um":      _pixel_size_um(md, "Z"),
    }


def _pixel_size_um(md, axis):
    """Pull a pixel size for a given axis from Scaling.Items.Distance.

    CZI stores Distance.Value in meters (the DefaultUnitFormat shown in
    ZEN is just a display hint). We convert to µm.
    """
    distances = _as_list(_sub(md, "Scaling", "Items").get("Distance"))
    for d in distances:
        if isinstance(d, dict) and d.get("@attrs", {}).get("Id") == axis:
            try:
                return f"{float(_text(d, 'Value')) * 1e6:.5g}"
            except (TypeError, ValueError):
                return ""
    return ""


def _build_instrument(md):
    instr = _sub(md, "Information", "Instrument")
    microscope = _sub(instr, "Microscopes", "Microscope")
    # Some CZI files have multiple microscopes; pick the first if a list.
    if isinstance(_sub(instr, "Microscopes").get("Microscope"), list):
        microscope = _as_list(instr["Microscopes"]["Microscope"])[0]

    objectives = _as_list(_sub(instr, "Objectives").get("Objective"))
    obj_list = []
    for o in objectives:
        if not isinstance(o, dict):
            continue
        obj_list.append({
            "id":             _attr(o, "Id"),
            "name":           _attr(o, "Name"),
            "nominal_mag":    _text(o, "NominalMagnification"),
            "lens_na":        _text(o, "LensNA"),
            "immersion":      _text(o, "Immersion"),
            "working_distance": _text(o, "WorkingDistance"),
            "model":          _text(o, "Manufacturer", "Model"),
        })

    return {
        "microscope_name":      _attr(microscope, "Name"),
        "microscope_type":      _text(microscope, "Type"),
        "microscope_user_id":   _text(microscope, "UserDefinedName"),
        "objectives":           obj_list,
        # Channels (one entry per acquisition channel) live under Image.
        "channels":             _build_channels(md),
        "detectors_present":    _truthy_list(instr, "Detectors", "Detector"),
        "light_sources_present": _truthy_list(instr, "LightSources", "LightSource"),
    }


def _truthy_list(node, *path):
    """Return list of @Id values of all children at the given path; [] if absent."""
    items = _as_list(_sub(node, *path[:-1]).get(path[-1]))
    return [_attr(i, "Id") for i in items if isinstance(i, dict)]


def _build_channels(md):
    chans = _as_list(_sub(md, "Information", "Image", "Dimensions", "Channels").get("Channel"))
    out = []
    for c in chans:
        if not isinstance(c, dict):
            continue
        out.append({
            "id":               _attr(c, "Id"),
            "name":             _attr(c, "Name"),
            "fluor":            _text(c, "Fluor"),
            "color":            _text(c, "Color"),
            "acquisition_mode": _text(c, "AcquisitionMode"),
            "contrast_method":  _text(c, "ContrastMethod"),
            "illumination":     _text(c, "IlluminationType"),
            "exposure_us":      _text(c, "ExposureTime"),
            "binning":          _text(c, "DetectorSettings", "Binning"),
            "detector_id":      _attr(c, "DetectorSettings", "Detector", "Id"),
            "excitation_nm":    _text(c, "ExcitationWavelength"),
            "emission_nm":      _text(c, "EmissionWavelength"),
        })
    return out


def _build_acquisition(md):
    img = _sub(md, "Information", "Image")
    return {
        "acquisition_datetime": _text(img, "AcquisitionDateAndTime"),
        "acquisition_duration_ms": _text(img, "AcquisitionDuration"),
        "compression_params":   _text(img, "CurrentCompressionParameters"),
    }


def _build_mosaic(md):
    img = _sub(md, "Information", "Image")
    return {
        "scene_count":   _text(img, "SizeS"),
        "tile_count":    _text(img, "SizeM"),
        # Focus map / scene bounds / tile positions live across multiple
        # XML branches and depend on the scan; we currently surface only
        # the counts. Detailed bounds can be added once we have a
        # use-case driving them.
    }


def _build_document_info(md):
    doc = _sub(md, "Information", "Document")
    app = _sub(md, "Information", "Application")
    custom = _sub(md, "CustomAttributes")
    return {
        "creation_date":   _text(doc, "CreationDate"),
        "user_name":       _text(doc, "UserName"),
        "title":           _text(doc, "Title"),
        "comments":        _text(doc, "Comments") or _text(doc, "Description"),
        "keywords":        _text(doc, "Keywords"),
        "application_name":    _text(app, "Name"),
        "application_version": _text(app, "Version"),
        "application_build":   _text(app, "BuildId"),
        # Custom attributes — present only if the user added key/value
        # pairs in ZEN. Surfaced as keys-only so we don't bloat the
        # sidecar; a future task can flatten if researchers start using
        # this seriously.
        "custom_attribute_keys": [k for k in custom if not k.startswith("@") and k != "#text"],
    }


# ------------------------------------------------------------------ public API

def build_microscopy_section(md):
    """Build the structured `microscopy:` block for the sidecar."""
    return {
        "geometry":      _build_geometry(md),
        "instrument":    _build_instrument(md),
        "acquisition":   _build_acquisition(md),
        "mosaic":        _build_mosaic(md),
        "document_info": _build_document_info(md),
    }


# Curated subset surfaced as `discovered.czi_*` so YAML configs can
# reference them. Each entry: (discovered_key, getter_fn(md) -> str,
# human-readable description). Adding a field here means adding a row
# to the table in 09_MODALITIES.md §1.1 (per CLAUDE.md cross-ref rule).
EXPOSED_FIELDS = [
    ("czi_acquisition_datetime",
        lambda md: _text(md, "Information", "Image", "AcquisitionDateAndTime"),
        "Full ISO timestamp from the .czi (preferred over folder date)"),
    ("czi_microscope_name",
        lambda md: _attr(md, "Information", "Instrument", "Microscopes", "Microscope", "Name"),
        "Microscope @Name (e.g. 'Axioscan 7')"),
    ("czi_microscope_type",
        lambda md: _text(md, "Information", "Instrument", "Microscopes", "Microscope", "Type"),
        "Microscope geometry type (e.g. 'Upright', 'Inverted')"),
    ("czi_objective_name",
        lambda md: _attr(_first_objective(md), "Name"),
        "First objective's @Name (e.g. 'Plan-Apochromat 20x/0.8 M27')"),
    ("czi_objective_mag",
        lambda md: _text(_first_objective(md), "NominalMagnification"),
        "First objective's nominal magnification, no units (e.g. '20')"),
    ("czi_objective_na",
        lambda md: _text(_first_objective(md), "LensNA"),
        "First objective's numerical aperture (e.g. '0.8')"),
    ("czi_pixel_size_x_um",
        lambda md: _pixel_size_um(md, "X"),
        "Physical pixel size along X, in µm"),
    ("czi_pixel_size_y_um",
        lambda md: _pixel_size_um(md, "Y"),
        "Physical pixel size along Y, in µm"),
    ("czi_size_x",
        lambda md: _text(md, "Information", "Image", "SizeX"),
        "Image width in pixels"),
    ("czi_size_y",
        lambda md: _text(md, "Information", "Image", "SizeY"),
        "Image height in pixels"),
    ("czi_size_c",
        lambda md: _text(md, "Information", "Image", "SizeC"),
        "Number of channels"),
    ("czi_size_z",
        lambda md: _text(md, "Information", "Image", "SizeZ"),
        "Number of Z slices (empty for 2D scans)"),
    ("czi_size_t",
        lambda md: _text(md, "Information", "Image", "SizeT"),
        "Number of timepoints (empty for single-shot)"),
    ("czi_scene_count",
        lambda md: _text(md, "Information", "Image", "SizeS"),
        "Number of scenes (regions) in the slide"),
    ("czi_tile_count",
        lambda md: _text(md, "Information", "Image", "SizeM"),
        "Number of mosaic tiles (high for whole-slide scans)"),
    ("czi_pixel_type",
        lambda md: _text(md, "Information", "Image", "PixelType"),
        "Pixel encoding (e.g. 'Bgr24', 'Gray16')"),
    ("czi_compression",
        lambda md: _text(md, "Information", "Image", "OriginalCompressionMethod"),
        "Original compression (often 'JpegXr' for WSI)"),
    ("czi_acquisition_mode",
        lambda md: _channel_field(md, 0, "AcquisitionMode"),
        "First channel acquisition mode (e.g. 'WideField', 'LaserScanningConfocal')"),
    ("czi_contrast_method",
        lambda md: _channel_field(md, 0, "ContrastMethod"),
        "First channel contrast method (e.g. 'Brightfield', 'Fluorescence')"),
    ("czi_user",
        lambda md: _text(md, "Information", "Document", "UserName"),
        "ZEN account that captured the image (often a generic instrument account)"),
    ("czi_zen_version",
        lambda md: _text(md, "Information", "Application", "Version"),
        "ZEN software version that produced the file"),
]


def _first_objective(md):
    objs = _as_list(_sub(md, "Information", "Instrument", "Objectives").get("Objective"))
    return objs[0] if objs and isinstance(objs[0], dict) else {}


def _channel_field(md, index, field):
    chans = _as_list(_sub(md, "Information", "Image", "Dimensions", "Channels").get("Channel"))
    if 0 <= index < len(chans) and isinstance(chans[index], dict):
        return _text(chans[index], field)
    return ""


def build_discovered_subset(md):
    """Pluck the curated `discovered.czi_*` dict from the parsed XML."""
    return {key: fn(md) for key, fn, _desc in EXPOSED_FIELDS}


def extract(czi_path):
    """One-shot: open a .czi, return (discovered_subset, microscopy_section).

    Raises RuntimeError if czifile isn't installed. Other parse errors
    propagate; callers should decide whether to swallow them per case.
    """
    md_root = load_xml_dict(czi_path)
    md = _sub(md_root, "Metadata")
    return build_discovered_subset(md), build_microscopy_section(md)
