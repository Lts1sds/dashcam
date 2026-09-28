import json
import threading
import time
import urllib.request

import pytest

from dashcam import server
from dashcam.storage import Store


def _get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
        return r.status, r.read()


@pytest.fixture
def running_server(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    tid = store.start_trace("server test")
    store.record_span(
        tid,
        0,
        "openai",
        "chat",
        "gpt-4o-mini",
        time.time(),
        time.time(),
        {"messages": [{"role": "user", "content": "hi"}]},
        {"content": "yo"},
        None,
        3,
        2,
        0.000001,
    )
    httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server._make_handler(store))
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield port
    httpd.shutdown()


def test_dashboard_html(running_server):
    status, body = _get(running_server, "/")
    assert status == 200
    assert b"dashcam" in body


def test_api_traces(running_server):
    status, body = _get(running_server, "/api/traces")
    data = json.loads(body)
    assert status == 200
    assert data[0]["name"] == "server test"
    assert data[0]["span_count"] == 1


def test_api_trace_detail(running_server):
    _, body = _get(running_server, "/api/traces")
    tid = json.loads(body)[0]["id"]
    status, body = _get(running_server, f"/api/trace/{tid}")
    data = json.loads(body)
    assert status == 200
    assert data["spans"][0]["model"] == "gpt-4o-mini"


def test_api_stats(running_server):
    status, body = _get(running_server, "/api/stats")
    data = json.loads(body)
    assert status == 200
    assert data["traces"] == 1
    assert data["spans"] == 1


def test_api_export(running_server):
    _, body = _get(running_server, "/api/traces")
    tid = json.loads(body)[0]["id"]
    status, body = _get(running_server, f"/api/export/{tid}")
    assert status == 200
    assert json.loads(body)["trace"]["id"] == tid
