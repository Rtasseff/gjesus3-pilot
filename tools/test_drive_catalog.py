#!/usr/bin/env python3
"""test_drive_catalog.py — class rules, instrument fingerprint and CZI metadata reading of
tools/drive_staging/catalog.py (2026-09-29). No network, no NAS, no staged data: a synthetic .czi
is built in a temp dir.

Run:  python tools/test_drive_catalog.py
"""
import io
import os
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "drive_staging"))

import catalog as cat  # noqa: E402

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok:   {msg}")


def make_czi(xml, pos=1000, tail=500, header=True):
    """Bytes of a minimal CZI: file header, filler, then the metadata segment at `pos`."""
    head = bytearray(160)
    if header:
        head[:10] = b"ZISRAWFILE"
    struct.pack_into("<q", head, 92, pos)
    body = bytearray(head) + bytes(pos - 160)
    seg = bytearray(b"ZISRAWMETADATA".ljust(32, b"\0")) + struct.pack("<ii", len(xml), 0) + bytes(248) + xml
    return bytes(body + seg + bytes(tail))


def xml_for(serials=(), keys=(), stand="Axio Observer.Z1 / 7", hw=True, exp=True):
    devs = "".join(f'<Device Id="d{i}" SerialNumber="{s}"/>' for i, s in enumerate(serials))
    sk = "".join(f'<StandCharacteristic Key="{k}"/>' for k in keys)
    hws = f"<HardwareSetting><Configuration>{devs}<StandSpecification>{sk}</StandSpecification></Configuration></HardwareSetting>" if hw else ""
    return (f'<?xml version="1.0" encoding="UTF-8"?><ImageDocument><Metadata>'
            f'<Information><Application><Name>ZEN</Name><Version>3.5</Version></Application>'
            f'<Image><AcquisitionDateAndTime>2024-10-02T09:15:00</AcquisitionDateAndTime>'
            f'<Dimensions><Channels><Channel><AcquisitionMode>WideField</AcquisitionMode></Channel></Channels></Dimensions></Image>'
            f'<Instrument><Microscopes><Microscope Id="m" Name="{stand}"><System>LSM 800</System></Microscope></Microscopes>'
            f'<Objectives><Objective Name="Plan-Apo 20x"><NominalMagnification>20</NominalMagnification></Objective></Objectives>'
            f'</Instrument><User><DisplayName>zeiss</DisplayName></User></Information>'
            f'{"<Experiment/>" if exp else ""}{hws}</Metadata></ImageDocument>').encode("utf-8")


def main():
    print("path_class")
    pc = cat.path_class
    check(pc("Cell observer\\x\\$RECYCLE.BIN\\a.czi") == "system", "recycle bin -> system, even a .czi")
    check(pc("a\\.DS_Store") == "system" and pc("a\\~$doc.docx") == "system" and pc("a\\x.tmp") == "system", "DS_Store / Office lock / .tmp -> system")
    check(pc("Install Western Digital Software for Windows.exe") == "software", ".exe -> software")
    check(pc("Tools\\Fiji.app\\plugins\\a.txt") == "software", "anything under Fiji.app -> software")
    check(pc("Origin\\Crack\\readme.txt") == "software", "folder containing 'Crack' -> software")
    check(pc("LEONE.zip") == "archive" and pc("x\\a.tar.gz") == "archive", "archives")
    check(pc("a\\b.preview.czi") == "czi-preview" and pc("a\\b.czi") == "czi", ".preview.czi vs .czi")
    check(pc("a\\b.lsm") == "lsm" and pc("a\\b.TIF") == "tif" and pc("a\\b.tiff") == "tif", "lsm / tif")
    check(pc("a\\b.nii.gz") == "volume" and pc("a\\2dseq") == "volume" and pc("a\\b.jcamp") == "volume", "volume files")
    check(pc("a\\b.gz") == "other", "bare .gz -> other")
    check(pc("a\\v.raw", frozenset({"a\\v"})) == "volume" and pc("a\\w.raw") == "other", ".raw is volume only next to a .mhd")
    check(pc("a\\x.dm4") == "em" and pc("a\\x.mnova") == "nmr", "em / nmr")
    check(pc("a\\fid") == "bruker" and pc("a\\spnam12") == "bruker" and pc("a\\zzz") == "other", "Bruker extension-less names")
    check(pc("a\\x.zmes") == "analysis" and pc("a\\x.png") == "figure" and pc("a\\x.pdf") == "document" and pc("a\\x.avi") == "video", "analysis/figure/document/video")
    check(cat.file_ext("A\\B.Preview.CZI") == ".preview.czi", "ext lowercased, .preview.czi kept whole")

    print("personal heuristic")
    check(cat.personal_hit("Claudia\\Nómina 2019\\a.pdf") == ["nómina"], "nómina token")
    check(cat.personal_hit("x\\Mi_CV_2020.docx") == ["cv"], "CV as its own token")
    check(cat.personal_hit("x\\Mycovid\\a.docx") == [] and cat.personal_hit("x\\admin\\a") == ["admin"], "no substring hits inside words")

    print("fingerprint")
    ref = cat.load_instruments()
    f = lambda s, k, st="Axio Observer.Z1 / 7": cat.fingerprint(ref, s, k, st)[0]
    check(f({"03761880", "22-12_150651_0312"}, {"LSM", "InvertedFixedStage", "SampleFinder"}) == "LSM9", "LSM 900: serial 03761880")
    check(f({}, {"LSM"}) == "LSM9" and cat.fingerprint(ref, [], ["LSM"], "")[1].startswith("stand-key"), "LSM key alone -> LSM9 via stand-key rule")
    check(f({"4661000718"}, {"Pollux", "UprightFixedStage"}, "Axioscan 7") == "ZWSI", "AxioScan 7")
    check(f({"784053"}, {"Upright"}, "Axio Imager.Z2") == "EXTERNAL:AxioImagerZ2", "external Axio Imager.Z2")
    check(f({"4661000340"}, {"Pollux", "UprightFixedStage"}, "Axioscan 7") == "EXTERNAL:Axioscan7-Biodonostia",
          "Biodonostia's Axioscan 7: told from our ZWSI by its serial alone")
    check(f({"4661000341"}, {"Pollux", "UprightFixedStage"}, "Axioscan 7") == "unknown",
          "another Axioscan 7 serial is neither ours nor Biodonostia's")
    check(f(set(), {"Inverted"}) == "CELL", "Cell Observer: no serial, keys exactly {Inverted}")
    check(f(set(), {"Inverted", "SampleFinder"}) == "unknown", "extra stand key -> unknown")
    check(f({"999"}, {"Inverted"}) == "unknown", "a serial we do not know is never CELL")
    check(f(set(), {"Inverted"}, "Something Else") == "unknown", "CELL needs the stand name too")
    check(f(set(), set(), "") == "unknown", "no fingerprint -> unknown")
    check(f({"03761880"}, {"Inverted"}) == "LSM9", "the LSM 900 serial beats the Cell Observer rule")
    inst, rule, fired = cat.fingerprint(ref, {"03761880", "4661000718"}, set(), "")
    check(inst == "LSM9" and len({c for c, _ in fired}) == 2, "two instruments firing is reported (conflict)")

    print("production sidecar rule inputs")
    raw = {"HardwareSetting": {"Configuration": {"Device": [
        {"Id": "Microscope", "SerialNumber": "", "StandSpecification": {"StandCharacteristic": [
            {"@attrs": {"Key": "LSM"}}, {"@attrs": {"Key": "SampleFinder"}}]}},
        {"@attrs": {"SerialNumber": "03761880"}}]}},
        "Information": {"Instrument": {"Microscopes": {"Microscope": {"@attrs": {"Name": "Axio Observer.Z1 / 7"}}}}}}
    s, k, st, hw = cat.fp_inputs_from_dict(raw)
    check(s == {"03761880"} and k == {"LSM", "SampleFinder"} and st == "Axio Observer.Z1 / 7" and hw, "dict extractor finds serials, keys, stand")
    check(cat.fingerprint(ref, s, k, st)[0] == "LSM9", "dict inputs give the same instrument as the XML path")

    print("czi metadata")
    xml = xml_for(serials=["03761880", "22-12_150651_0312"], keys=["LSM", "InvertedFixedStage"])
    d = cat.parse_czi_xml(xml)
    check(d["serials"] == ["03761880", "22-12_150651_0312"] and d["keys"] == ["InvertedFixedStage", "LSM"], "serials and stand keys")
    check(d["stand"] == "Axio Observer.Z1 / 7" and d["system"] == "LSM 800", "stand name and (misleading) System field")
    check(d["acq_dt"].startswith("2024-10-02") and d["objective"] == "Plan-Apo 20x 20x" and d["user"] == "zeiss" and d["zen"] == "ZEN 3.5", "date, objective, user, ZEN")
    check(cat.czi_class({"ok": True, **cat.parse_czi_xml(xml_for(hw=False, exp=False))}) == "czi-processed", "no HardwareSetting and no Experiment -> czi-processed")
    check(cat.czi_class({"ok": True, **cat.parse_czi_xml(xml)}) == "czi-raw" and cat.czi_class({"ok": False}) == "czi-unreadable", "czi-raw / czi-unreadable")

    # a preset inside <HardwareSettingsPool> comes first in document order and has no <Device> elements:
    # a first-match find() there missed every serial on real LSM 900 files
    pool = xml_for(serials=["03761880"], keys=["LSM"]).replace(
        b"<Experiment/>", b'<Experiment><HardwareSettingsPool><HardwareSetting Name="Before"><ParameterCollection Id="x"/></HardwareSetting></HardwareSettingsPool></Experiment>')
    check(cat.parse_czi_xml(pool)["serials"] == ["03761880"], "serials found even when a preset HardwareSetting comes first")

    print("CZI reading: seek vs streaming capture")
    with tempfile.TemporaryDirectory() as td:
        for pos in (1000, 40_000):
            data = make_czi(xml, pos=pos)
            p = os.path.join(td, f"t{pos}.czi")
            open(p, "wb").write(data)
            seek_xml, err = cat.czi_read_xml(p)
            check(seek_xml == xml and err is None, f"seek read, metadata at {pos}")
            for chunk in (200, 4096, 10**6):
                cap = cat.CziCapture()
                buf = io.BytesIO(data)
                off = 0
                while b := buf.read(chunk):
                    cap.feed(off, b)
                    off += len(b)
                check(cap.result() == (xml, None), f"stream capture, metadata at {pos}, chunk {chunk}")
            sha, n, dm, czi = cat.stream_hash(io.BytesIO(data), want_czi=True)
            check(n == len(data) and czi == (xml, None) and not dm, "stream_hash returns hash, size and the same xml")
        bad = os.path.join(td, "bad.czi")
        open(bad, "wb").write(make_czi(xml, header=False))
        check(cat.czi_read_xml(bad)[1] == "no-ZISRAWFILE-header", "not a CZI -> reason, not an exception")
        cap = cat.CziCapture()
        cap.feed(0, make_czi(xml, header=False))
        check(cap.result()[1] == "no-ZISRAWFILE-header", "stream capture agrees")
        trunc = os.path.join(td, "trunc.czi")
        open(trunc, "wb").write(make_czi(xml, pos=1000)[:1100])
        check(cat.czi_read_xml(trunc)[0] is None, "metadata cut off by a truncated file -> None")

    print("DICM magic")
    check(cat.stream_hash(io.BytesIO(bytes(128) + b"DICM" + b"xxxx"))[2] is True, "DICM preamble detected")

    if FAILS:
        print(f"\n{len(FAILS)} FAILED")
        sys.exit(1)
    print("\nall ok")


if __name__ == "__main__":
    main()
