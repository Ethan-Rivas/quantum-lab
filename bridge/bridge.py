"""The lab bridge: lets Qanvas, the lab's circuit builder, hand circuits to the rest of the lab.

Qanvas's web server forwards /api/ here, so the browser only ever talks to Qanvas's own address.
This service has no published port; only the containers in this compose project can reach it.

    GET  /health    what this bridge can do, and the address JupyterLab opens at
    POST /notebook  {"name": "bell-qiskit", "notebook": {...}} saves notebooks/qanvas/<name>.ipynb
"""

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlparse

import nbformat

VERSION = 1
NOTEBOOKS = Path(os.environ.get("BRIDGE_NOTEBOOKS", "/home/quantum/work"))
FOLDER = "qanvas"
JUPYTER_URL = os.environ.get("BRIDGE_JUPYTER_URL", "http://127.0.0.1:8888").rstrip("/")
JUPYTER_TOKEN = os.environ.get("JUPYTER_TOKEN", "")
MAX_BODY = 5 * 1024 * 1024


def free_path(name):
    """notebooks/qanvas/<name>.ipynb, or <name>-2.ipynb and so on, so nothing is ever overwritten."""
    folder = NOTEBOOKS / FOLDER
    folder.mkdir(exist_ok=True)
    path = folder / f"{name}.ipynb"
    n = 2
    while path.exists():
        path = folder / f"{name}-{n}.ipynb"
        n += 1
    return path


def jupyter_link(relative):
    link = f"{JUPYTER_URL}/lab/tree/{quote(relative)}"
    return f"{link}?token={quote(JUPYTER_TOKEN)}" if JUPYTER_TOKEN else link


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def same_origin(self):
        # Any website could make the browser send a request to 127.0.0.1:8080, so writes only
        # come from Qanvas's own page. Requiring JSON also forces a CORS preflight, which this
        # server never approves, on requests from other origins.
        origin = self.headers.get("Origin")
        return origin is not None and urlparse(origin).netloc == self.headers.get("Host")

    def do_GET(self):
        if self.path != "/health":
            return self.reply(404, {"error": "not-found"})
        self.reply(200, {"version": VERSION, "features": ["notebook"]})

    def do_POST(self):
        if self.path != "/notebook":
            return self.reply(404, {"error": "not-found"})
        if not self.same_origin() or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.reply(403, {"error": "forbidden"})
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self.reply(413, {"error": "too-large"})
        try:
            body = json.loads(self.rfile.read(length))
            name = body["name"]
            notebook = nbformat.from_dict(body["notebook"])
            nbformat.validate(notebook)
        except Exception:
            return self.reply(400, {"error": "invalid"})
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name):
            return self.reply(400, {"error": "invalid-name"})
        try:
            path = free_path(name)
            nbformat.write(notebook, path)
        except OSError as error:
            print(f"Couldn't save the notebook: {error}", flush=True)
            return self.reply(500, {"error": "write-failed"})
        relative = path.relative_to(NOTEBOOKS).as_posix()
        self.reply(201, {"path": relative, "url": jupyter_link(relative)})

    def log_message(self, format, *args):
        print(f"{self.command} {self.path} {args[1] if len(args) > 1 else ''}", flush=True)


if __name__ == "__main__":
    port = int(os.environ.get("BRIDGE_PORT", "8000"))
    print(f"Lab bridge listening on port {port}, saving notebooks under {NOTEBOOKS / FOLDER}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
