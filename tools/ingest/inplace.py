"""Replace a file's content without replacing the file, so hard links to it stay the same file.

Why (2026-11-07): a project's `raw_linked/<link>/` folder hard-links every file of a whole-folder acquisition, its
`metadata.json`, `checksums.json` and `README.txt` included. Writing a temp file and `os.replace`-ing it over the /raw
path puts a NEW file there, and the project copy keeps the old one. The condition back-fill split 76 CNIC-HEARDS
sidecars that way (repaired with tools/relink_split_sidecars.py).

`replace_keeping_links(tmp, path)` is the drop-in for `os.replace(tmp, path)` on any file inside an acquisition folder:
the temp file is still written first (so a failure while rendering never touches the original), then its bytes are
written into the existing file in place (same inode / file id), fsync'd, read back, and the temp file removed. If `path`
does not exist yet it falls back to `os.replace`. Registry CSVs are not hard-linked and keep using `os.replace`.
"""

import os


def replace_keeping_links(tmp, path):
    """Move `tmp`'s bytes into `path` in place; remove `tmp`. Raises on a read-back mismatch."""
    if not os.path.exists(path):
        os.replace(tmp, path)
        return
    with open(tmp, "rb") as f:
        data = f.read()
    with open(path, "r+b") as f:
        f.seek(0)
        f.write(data)
        f.truncate()
        f.flush()
        os.fsync(f.fileno())
    with open(path, "rb") as f:
        if f.read() != data:
            raise OSError(f"{path}: content does not read back as written")
    os.remove(tmp)
