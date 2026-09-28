import time

from dashcam import context
from dashcam.storage import Store


def test_current_trace_reuses_within_timeout(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    t1 = context.current_trace(store, "task one")
    t2 = context.current_trace(store, "task one")
    assert t1 == t2
    assert context.next_idx() == 0
    assert context.next_idx() == 1
    traces = store.list_traces()
    assert len(traces) == 1


def test_new_trace_after_idle(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    t1 = context.current_trace(store, "first")
    context._local.trace = (t1, time.time() - 400.0, "first")
    t2 = context.current_trace(store, "second")
    assert t1 != t2
    assert len(store.list_traces()) == 2


def test_derive_name():
    kwargs = {
        "messages": [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Find   the best pizza in   town please"},
        ]
    }
    assert context.derive_name(kwargs) == "Find the best pizza in town please"
    assert context.derive_name({"messages": []}) is None
    assert context.derive_name({}) is None


def test_explicit_trace(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    with context.trace(store, "explicit") as tid:
        assert context.current_trace(store) == tid
    assert store.get_trace(tid)["trace"]["status"] == "ok"
