r"""What a signed-in person may read, and the record of what they wrote.

`Guard` sits inside the sign-in gate (auth.Gate), so every request it sees has
a person. It does two things to the tools' JSON calls, without changing them:

1. SOURCE FOLDERS. The server runs as Ryan, so it can read whatever his account
   can. A tool call that names a folder or files to read (a preview, an ingest,
   a copy into a project) must name something inside the server's source
   folders (settings.py: `<root>\staging` plus any listed share). Anything else
   is refused before the tool runs. The folder browser is confined the same way
   in tools/filebrowse.py, with a friendlier message.

2. THE ACTION LOG. Every write (ingest, pull, project change, recipe save) is
   written to actionlog.ActionLog when it ENDS: the person, what, dry run or
   not, and the outcome read from the tool's own answer (for a streamed ingest,
   its final `done` or `error` event).
"""

import io
import json
import os

# Tool calls that write, and their name in the action log.
WRITE_ACTIONS = {
    "/ingest/api/ingest": "microscopy-ingest",
    "/ingest/api/mri/ingest": "mri-ingest",
    "/ingest/api/sftp_pull": "mri-pull",
    "/ingest/api/save_recipe": "recipe-save",
    "/projects/api/create_project": "project-create",
    "/projects/api/update_project": "project-edit",
    "/projects/api/import_raw": "project-add-acquisitions",
    "/projects/api/import_local": "project-add-files",
}
# Request keys that name something on disk to READ. The folder browser's own
# listing ("listdir") is left to filebrowse, which answers more kindly.
PATH_KEYS = ("staging_path", "staging_root", "path")
LIST_KEYS = ("sources",)
NO_PATH_CHECK = ("/ingest/api/listdir", "/projects/api/listdir")
MAX_BODY = 4 * 1024 * 1024


def inside_any(path, roots):
    """True when `path` is at or below one of `roots`. Real paths are compared,
    so a junction or link inside a source folder cannot lead out of it."""
    p = os.path.normcase(os.path.realpath(path))
    for r in roots:
        r = os.path.normcase(os.path.realpath(r))
        try:
            if os.path.commonpath([p, r]) == r:
                return True
        except ValueError:
            continue
    return False


def _summary(action, data):
    """A short 'what' for the log, from the request."""
    folder = os.path.basename(os.path.normpath(data.get("staging_path") or "")) \
        if data.get("staging_path") else ""
    if action in ("microscopy-ingest", "mri-ingest"):
        inst = data.get("instrument") or ("MRI" if action == "mri-ingest" else "")
        return " ".join(x for x in (inst, folder) if x)
    if action == "mri-pull":
        n = len(data.get("remotes") or [])
        return f"{n} stud{'y' if n == 1 else 'ies'} from the scanner"
    if action == "recipe-save":
        return f"{data.get('instrument', '')} recipe '{data.get('name', '')}'"
    if action == "project-create":
        return data.get("name") or ""
    if action == "project-edit":
        fields = ", ".join(sorted((data.get("updates") or {}).keys()))
        return f"{data.get('project_id', '')} ({fields})"
    if action == "project-add-acquisitions":
        return f"{len(data.get('rows') or [])} acquisition(s) -> {data.get('project', '')}"
    if action == "project-add-files":
        return f"{len(data.get('sources') or [])} item(s) -> {data.get('project', '')}"
    return ""


def _outcome(payload):
    """'3 of 3 ingested' style text from a tool's final answer."""
    if not isinstance(payload, dict):
        return ""
    if "error" in payload and payload["error"]:
        return str(payload["error"])[:200]
    if "total" in payload and "ok" in payload:
        ok = payload["ok"]
        ok = len([r for r in payload.get("results", []) if r.get("ok")]) \
            if isinstance(ok, bool) else ok
        done = "would be ingested" if payload.get("dry_run") else "ingested"
        extra = (f", {payload['n_already_ingested']} already in gjesus3"
                 if payload.get("n_already_ingested") else "")
        return f"{ok} of {payload['total']} {done}{extra}"
    if payload.get("project_id"):
        return payload["project_id"]
    counts = [f"{k.replace('_', ' ')} {v}" for k, v in payload.items()
              if isinstance(v, int) and not isinstance(v, bool)]
    return ", ".join(counts[:4])


class _Recorder:
    """Wraps one response; writes the log record when the response ends."""

    def __init__(self, log, user, action, what, dry_run):
        self.log, self.user, self.action = log, user, action
        self.what, self.dry_run = what, dry_run
        self.status = None
        self.stream = False
        self.chunks = []
        self.final = None       # ("done"|"error", payload)

    def start_response(self, start_response):
        def _sr(status, headers, exc_info=None):
            self.status = int(status.split()[0])
            ctype = dict((k.lower(), v) for k, v in headers).get("content-type", "")
            self.stream = ctype.startswith("text/event-stream")
            return start_response(status, headers, exc_info) if exc_info \
                else start_response(status, headers)
        return _sr

    def see(self, chunk):
        if self.stream:
            for line in chunk.decode("utf-8", "replace").splitlines():
                if not line.startswith("data: "):
                    continue
                try:
                    ev = json.loads(line[6:])
                except ValueError:
                    continue
                if ev.get("kind") == "done":
                    try:
                        self.final = ("done", json.loads(ev.get("msg") or "{}"))
                    except ValueError:
                        self.final = ("done", {})
                elif ev.get("kind") == "error":
                    self.final = ("error", {"error": ev.get("msg")})
        elif sum(len(c) for c in self.chunks) < 65536:
            self.chunks.append(chunk)

    def finish(self):
        if self.stream:
            status, payload = self.final or ("stopped", {"error": "the stream ended early"})
        else:
            try:
                payload = json.loads(b"".join(self.chunks) or b"{}")
            except ValueError:
                payload = {}
            ok = self.status is not None and self.status < 400 and not \
                (isinstance(payload, dict) and payload.get("error"))
            status = "done" if ok else "refused"
        self.log.write(self.user, self.action, what=self.what, dry_run=self.dry_run,
                       status=status, result=_outcome(payload))


class _Body:
    """The response iterator, seen chunk by chunk; logs once at the end."""

    def __init__(self, it, rec):
        self.it, self.rec = it, rec

    def __iter__(self):
        try:
            for chunk in self.it:
                self.rec.see(chunk)
                yield chunk
        finally:
            self.close()

    def close(self):
        if self.rec is not None:
            rec, self.rec = self.rec, None
            try:
                rec.finish()
            finally:
                if hasattr(self.it, "close"):
                    self.it.close()


class Guard:
    def __init__(self, app, source_roots, log):
        self.app = app
        self.roots = tuple(source_roots)
        self.log = log

    def _read_json(self, environ):
        try:
            n = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > MAX_BODY:
            return None
        body = environ["wsgi.input"].read(n)
        environ["wsgi.input"] = io.BytesIO(body)
        try:
            data = json.loads(body.decode("utf-8"))
        except ValueError:
            return None
        return data if isinstance(data, dict) else None

    def _outside(self, path, data):
        if path in NO_PATH_CHECK:
            return None
        named = [data[k] for k in PATH_KEYS if isinstance(data.get(k), str) and data[k].strip()]
        for k in LIST_KEYS:
            named += [s for s in (data.get(k) or []) if isinstance(s, str) and s.strip()]
        for p in named:
            if not inside_any(p.strip(), self.roots):
                return p
        return None

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO") or "/"
        if environ.get("REQUEST_METHOD", "GET").upper() != "POST" or "/api/" not in path:
            return self.app(environ, start_response)
        data = self._read_json(environ) or {}

        bad = self._outside(path, data)
        if bad is not None:
            body = json.dumps({"error": (
                f"That location is outside the folders this server may read from: "
                f"{bad}. Put the files in one of these first: "
                + "; ".join(self.roots))}).encode("utf-8")
            start_response("403 Forbidden", [("Content-Type", "application/json"),
                                             ("Content-Length", str(len(body)))])
            return [body]

        action = WRITE_ACTIONS.get(path)
        if not action:
            return self.app(environ, start_response)
        dry = data.get("dry_run")
        rec = _Recorder(self.log, environ.get("gj3.user"), action,
                        _summary(action, data), bool(dry) if dry is not None else None)
        return _Body(self.app(environ, rec.start_response(start_response)), rec)
