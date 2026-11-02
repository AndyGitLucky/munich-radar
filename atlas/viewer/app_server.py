"""HTTP helpers for the retained atlas preview and original application."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WEB_FILES = {"style.css", "app.js", "personal.js", "map.js", "topics.js", "occasions.js", "favicon.svg"}
PREVIEW_FILES = {"prototype.css"}


class PreviewServer(ThreadingHTTPServer):
    # Windows permits ambiguous duplicate listeners when SO_REUSEADDR is enabled.
    allow_reuse_address = False


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ("/", "/original/", "/app/", "/app/index.html"):
            html = (ROOT / "web/index.html").read_text(encoding="utf-8")
            html = html.replace("<head>", '<head><base href="/app/">', 1)
            if path == "/":
                html = html.replace('src="./app.js"', 'src="/prototype/app.js"')
                html = html.replace("</head>", '<link rel="stylesheet" href="/prototype/prototype.css">'
                                    '<script src="/prototype/prototype.js" defer></script></head>')
            return self.send_bytes(html.encode(), "text/html; charset=utf-8")
        asset = None
        if path == "/prototype/app.js":
            source = (ROOT / "web/app.js").read_text(encoding="utf-8")
            needle = '    const container = $("#events"); container.replaceChildren(); container.setAttribute("aria-busy","false");'
            if source.count(needle) != 1:
                return self.send_error(500, "Prototype presentation bridge needs updating")
            bridge = '    window.dispatchEvent(new CustomEvent("radar:selection", {detail:{candidates,recommendations,chosen,view,filter,topic,createCard:event=>card(event,0,today)}}));\n'
            return self.send_bytes(source.replace(needle, bridge + needle).encode(), "text/javascript; charset=utf-8")
        if path.startswith("/app/") and path[5:] in WEB_FILES:
            asset = ROOT / "web" / path[5:]
        elif path in ("/app/data/events.json", "/app/data/metadata.json"):
            asset = ROOT / "data" / path.rsplit("/", 1)[1]
        elif path == "/app/data/places.json":
            asset = ROOT / "config/places.json"
        elif path.startswith("/app/vendor/"):
            vendor = (ROOT / "web/vendor").resolve()
            candidate = (vendor / path[len("/app/vendor/"):]).resolve()
            if candidate.is_relative_to(vendor):
                asset = candidate
        elif path.startswith("/prototype/") and path[len("/prototype/"):] in PREVIEW_FILES:
            asset = HERE / path[len("/prototype/"):]
        if asset and asset.is_file():
            return self.send_bytes(asset.read_bytes(), mimetypes.guess_type(asset)[0] or "application/octet-stream")
        self.send_error(404)

    def send_bytes(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


