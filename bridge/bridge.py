"""The lab bridge: lets Qanvas, the lab's circuit builder, hand circuits to the rest of the lab.

Qanvas's web server forwards /api/ here, so the browser only ever talks to Qanvas's own address.
This service has no published port; only the containers in this compose project can reach it.

    GET  /health    what this bridge can do
    POST /notebook  {"name": "bell-qiskit", "notebook": {...}} saves notebooks/qanvas/<name>.ipynb
                    and answers with its path and the JupyterLab link that opens it
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
MAX_COPIES = 999

LOCAL_HOST = re.compile(r"(localhost|127\.0\.0\.1|\[::1\])(:\d+)?")
# GitHub Codespaces forwards each port to its own https://<codespace>-<port>.app.github.dev address.
CODESPACES_HOST = re.compile(r"([a-z0-9-]+)-\d+\.app\.github\.dev")


def jupyter_base(host):
    """Where the browser that sent `host` reaches JupyterLab, or None for a host Qanvas isn't served at.

    Checking the host stops DNS rebinding: a website that points its own name at 127.0.0.1 can make
    the browser treat this bridge as same-origin, but its requests still carry its own name.
    """
    host = host or ""
    if LOCAL_HOST.fullmatch(host):
        return JUPYTER_URL
    codespace = CODESPACES_HOST.fullmatch(host)
    if codespace:
        return f"https://{codespace[1]}-{urlparse(JUPYTER_URL).port or 8888}.app.github.dev"
    return None


def save(notebook, name):
    """Writes notebooks/qanvas/<name>.ipynb, or <name>-2.ipynb and so on; never replaces a file."""
    folder = NOTEBOOKS / FOLDER
    folder.mkdir(exist_ok=True)
    for n in range(1, MAX_COPIES + 1):
        path = folder / (f"{name}.ipynb" if n == 1 else f"{name}-{n}.ipynb")
        try:
            # "x" fails if the file exists, so two saves at the same moment can't pick the same name.
            with open(path, "x", encoding="utf-8") as file:
                nbformat.write(notebook, file)
            return path
        except FileExistsError:
            continue
    raise OSError(f"{MAX_COPIES} notebooks named {name} already exist")


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
        if jupyter_base(self.headers.get("Host")) is None:
            return self.reply(403, {"error": "forbidden"})
        self.reply(200, {"version": VERSION, "features": ["notebook"]})

    def do_POST(self):
        if self.path != "/notebook":
            return self.reply(404, {"error": "not-found"})
        base = jupyter_base(self.headers.get("Host"))
        if base is None or not self.same_origin() or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.reply(403, {"error": "forbidden"})
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self.reply(411, {"error": "length-required"})
        if not 0 <= length <= MAX_BODY:
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
            path = save(notebook, name)
        except OSError as error:
            print(f"Couldn't save the notebook: {error}", flush=True)
            return self.reply(500, {"error": "write-failed"})
        relative = path.relative_to(NOTEBOOKS).as_posix()
        link = f"{base}/lab/tree/{quote(relative)}"
        self.reply(201, {"path": relative, "url": f"{link}?token={quote(JUPYTER_TOKEN)}" if JUPYTER_TOKEN else link})

    def log_message(self, format, *args):
        print(format % args, flush=True)


if __name__ == "__main__":
    port = int(os.environ.get("BRIDGE_PORT", "8000"))
    print(f"Lab bridge listening on port {port}, saving notebooks under {NOTEBOOKS / FOLDER}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
