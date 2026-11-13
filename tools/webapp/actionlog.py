r"""The web app's action log: who did what, from which page, and how it ended.

Design choice C2 (web_app_design_options.md): the registry is not changed to
record who pressed "Ingest"; the app keeps its own log instead. One JSON object
per line in `actions.jsonl`, in the server's state folder (never on the share):

    {"time": "2026-11-13T10:42:07", "user": "ryan", "name": "Ryan Tasseff",
     "action": "microscopy-ingest", "dry_run": false,
     "what": "demo_microscopy -> AE-biomaGUNE-1123", "status": "done",
     "result": "3 of 3 ingested"}

Only writes are logged (ingests, pulls, project changes, recipe saves), never
reads or searches (L1). Each record is written when the action ENDS, so a
streamed ingest is logged with its outcome, not just its start.

**Open for production (L1):** the design notes say write actions are logged as
counts without names until the DPO agrees. This prototype runs on a test root
and logs names, which is what Ryan asked the sign-in to be used for; the DPO
question stays open before it runs on production.
"""

import datetime as _dt
import json
import os
import threading

LOG_FILE = "actions.jsonl"


class ActionLog:
    def __init__(self, state_dir):
        self.path = os.path.join(state_dir, LOG_FILE)
        self._lock = threading.Lock()

    def write(self, user, action, what="", dry_run=None, status="done", result=""):
        rec = {"time": _dt.datetime.now().replace(microsecond=0).isoformat(),
               "user": (user or {}).get("username"), "name": (user or {}).get("name"),
               "action": action, "dry_run": dry_run, "what": what,
               "status": status, "result": result}
        line = json.dumps(rec, ensure_ascii=False)
        with self._lock:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        return rec

    def recent(self, username=None, limit=10):
        """The newest records first; only `username`'s when given."""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            return []
        out = []
        for line in reversed(lines):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if username and rec.get("user") != username:
                continue
            out.append(rec)
            if len(out) >= limit:
                break
        return out
