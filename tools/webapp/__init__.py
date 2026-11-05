"""The gjesus3 web app: the ingest GUI and the Project Manager in one process.

`app.py` is the entry point; `settings.py` reads the server's one NAS root.
A regular package (unlike `tools/operator/`): `webapp` collides with nothing in
the standard library, so `from webapp import settings` is safe with `tools/` on
sys.path.
"""
