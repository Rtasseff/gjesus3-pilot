"""Lightweight parsers for Molecubes Nuclear Imaging XML aux files.

Two flavours observed in Molecubes archives (both serialised by
Boost.Serialization):

1. **Flat key-value** (`acqparams.xml`, `recontemplate.xml`,
   `reconparams.xml`) — a `<_params>` list of `<item>` elements, each
   with `<first>key</first><second>value</second></item>`. We parse
   this into a flat `{key: value}` dict.

2. **Hierarchical** (`protocol.xml`) — a nested object tree with named
   tags (`ProtocolMetadata`, `_study`, `_animal`, etc.). We parse this
   into a recursive nested dict (text content + child elements);
   Boost.Serialization wrapper attributes like `class_id`, `tracking_level`,
   `version`, `object_id` are dropped for readability.

Used by `ni_metadata.py` to build the structured `ni:` sidecar block.
Stdlib only (`xml.etree.ElementTree`); no third-party dependency.
"""

import xml.etree.ElementTree as ET
from pathlib import Path


# Boost-serialization metadata attributes that are noise for our purposes.
_BOOST_ATTR_NOISE = {
    "class_id", "tracking_level", "version", "object_id", "class_id_reference",
}


def _clean(text):
    """Strip whitespace; return '' for None or whitespace-only."""
    if text is None:
        return ""
    s = text.strip()
    return s


def parse_flat_params(xml_path):
    """Parse a Boost-serialized `_params` XML into {key: value}.

    Used for acqparams.xml, recontemplate.xml, and per-recon
    reconparams.xml. Looks for any `<item>` element with `<first>` +
    `<second>` children and emits {first.text: second.text}.

    Returns {} if the file doesn't exist or doesn't parse; never raises.
    """
    p = Path(xml_path)
    if not p.is_file():
        return {}
    try:
        tree = ET.parse(p)
    except ET.ParseError:
        return {}
    root = tree.getroot()
    out = {}
    for item in root.iter("item"):
        first = item.find("first")
        second = item.find("second")
        if first is None or second is None:
            continue
        key = _clean(first.text)
        if not key:
            continue
        out[key] = _clean(second.text)
    return out


def _element_to_dict(el):
    """Recursively convert an ElementTree element to a nested dict.

    Skips Boost-serialization wrapper attributes (`class_id`, etc.).
    Leaf elements (no children) become their text value (string).
    Repeated child tags become a list; unique child tags become scalar.
    """
    children = list(el)
    # Strip Boost noise from attributes; we don't store attributes
    # anywhere — they're all bookkeeping.
    if not children:
        return _clean(el.text)
    # Group children by tag name.
    by_tag = {}
    for child in children:
        by_tag.setdefault(child.tag, []).append(_element_to_dict(child))
    out = {}
    for tag, values in by_tag.items():
        if len(values) == 1:
            out[tag] = values[0]
        else:
            out[tag] = values
    return out


def parse_hierarchical(xml_path):
    """Parse a hierarchical Boost-serialized XML into a nested dict.

    Used for protocol.xml. The root element wrapping (`<boost_serialization>`)
    is stripped — we return the contents of the FIRST meaningful child.

    Returns {} if the file doesn't exist or doesn't parse; never raises.
    """
    p = Path(xml_path)
    if not p.is_file():
        return {}
    try:
        tree = ET.parse(p)
    except ET.ParseError:
        return {}
    root = tree.getroot()
    # boost_serialization is the wrapper; the actual document is its
    # first child (typically `<protocol>`).
    children = list(root)
    if not children:
        return {}
    return _element_to_dict(children[0])
