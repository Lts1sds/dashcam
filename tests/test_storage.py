import time

from dashcam.storage import Store


def test_roundtrip(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    tid = store.start_trace("hello trace")
    store.record_span(
        tid,
        0,
        "openai",
        "chat",
        "gpt-4o-mini",
        time.time() - 1,
        time.time(),
        {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        {"content": "hello"},
        None,
        10,
        5,
        0.0000045,
    )
    store.end_trace(tid, "ok")

    traces = store.list_traces()
    assert len(traces) == 1
    assert traces[0]["name"] == "hello trace"
    assert traces[0]["status"] == "ok"
    assert traces[0]["span_count"] == 1
    assert traces[0]["prompt_tokens"] == 10
    assert traces[0]["completion_tokens"] == 5
    assert traces[0]["cost"] == 0.0000045

    data = store.get_trace(tid)
    assert data["trace"]["id"] == tid
    assert len(data["spans"]) == 1
    span = data["spans"][0]
    assert span["request"]["messages"][0]["content"] == "hi"
    assert span["response"]["content"] == "hello"
    assert span["cost"] == 0.0000045


def test_error_span_marks_trace(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    tid = store.start_trace("boom")
    store.record_span(
        tid,
        0,
        "openai",
        "chat",
        "gpt-4o",
        time.time() - 1,
        time.time(),
        {"messages": []},
        None,
        "RateLimitError: 429",
        0,
        0,
        0.0,
    )
    traces = store.list_traces()
    assert traces[0]["status"] == "error"
    assert traces[0]["error_count"] == 1


def test_running_idle_becomes_ok(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    store.start_trace("old")
    old = time.time() - 400.0
    store._conn.execute("UPDATE traces SET started_at=?, ended_at=? WHERE name='old'", (old, old))
    store._conn.commit()
    traces = store.list_traces()
    assert traces[0]["status"] == "ok"


def test_stats_and_clear(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    tid = store.start_trace("s")
    store.record_span(
        tid,
        0,
        "openai",
        "chat",
        "gpt-4o-mini",
        time.time(),
        time.time(),
        {},
        {},
        None,
        100,
        50,
        0.00004,
    )
    s = store.stats()
    assert s["traces"] == 1
    assert s["spans"] == 1
    assert s["prompt_tokens"] == 100
    assert s["today_spans"] == 1
    store.clear()
    assert store.stats()["traces"] == 0
