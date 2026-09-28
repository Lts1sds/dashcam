import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_STATIC = Path(__file__).parent / "static"
DEFAULT_PORT = 8377


def _make_handler(store):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8",
                  extra=None):
            if isinstance(body, bytes):
                data = body
            else:
                data = json.dumps(body, ensure_ascii=False,
                                 default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            try:
                if path in ("/", "/index.html"):
                    self._send(200, (_STATIC / "index.html").read_bytes(),
                               "text/html; charset=utf-8")
                elif path == "/api/traces":
                    self._send(200, store.list_traces(200))
                elif path.startswith("/api/trace/"):
                    tid = path.rsplit("/", 1)[1]
                    data = store.get_trace(tid)
                    if data is None:
                        self._send(404, {"error": "trace not found"})
                    else:
                        self._send(200, data)
                elif path == "/api/stats":
                    self._send(200, store.stats())
                elif path.startswith("/api/export/"):
                    tid = path.rsplit("/", 1)[1]
                    data = store.get_trace(tid)
                    if data is None:
                        self._send(404, {"error": "trace not found"})
                        return
                    body = json.dumps(data, ensure_ascii=False, indent=2,
                                      default=str).encode("utf-8")
                    self._send(200, body,
                               "application/json; charset=utf-8",
                               {"Content-Disposition":
                                f'attachment; filename="dashcam-{tid}.json"'})
                else:
                    self._send(404, {"error": "not found"})
            except Exception as e:
                self._send(500, {"error": repr(e)})

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            try:
                if path == "/api/clear":
                    store.clear()
                    self._send(200, {"ok": True})
                else:
                    self._send(404, {"error": "not found"})
            except Exception as e:
                self._send(500, {"error": repr(e)})

    return Handler


def serve(store, host="127.0.0.1", port=DEFAULT_PORT, open_browser=True):
    httpd = ThreadingHTTPServer((host, port), _make_handler(store))
    url = f"http://{host}:{port}"
    print(f"dashcam dashboard running at {url}")
    print(f"db: {store.path}")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        httpd.server_close()
