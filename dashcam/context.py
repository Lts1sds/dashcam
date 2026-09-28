import threading
import time
from contextlib import contextmanager

_local = threading.local()
IDLE_TIMEOUT = 300.0


def derive_name(kwargs):
    msgs = kwargs.get("messages") if isinstance(kwargs, dict) else None
    if not isinstance(msgs, list):
        return None
    for m in msgs:
        if not isinstance(m, dict):
            continue
        if m.get("role") != "user":
            continue
        content = m.get("content")
        text = ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    text += part["text"] + " "
        text = " ".join(text.split())[:60]
        return text or None
    return None


def current_trace(store, name=None):
    now = time.time()
    st = getattr(_local, "trace", None)
    if st is not None and now - st[1] < IDLE_TIMEOUT:
        _local.trace = (st[0], now, st[2])
        if name and not st[2]:
            store.rename_trace(st[0], name)
            _local.trace = (st[0], now, name)
        return st[0]
    tid = store.start_trace(name)
    _local.trace = (tid, now, name)
    _local.span_idx = 0
    return tid


def next_idx():
    i = getattr(_local, "span_idx", 0)
    _local.span_idx = i + 1
    return i


def start_explicit(store, name=None):
    tid = store.start_trace(name)
    _local.trace = (tid, time.time(), name)
    _local.span_idx = 0
    return tid


def end_explicit(store, tid):
    store.end_trace(tid, "ok")
    st = getattr(_local, "trace", None)
    if st is not None and st[0] == tid:
        _local.trace = None


@contextmanager
def trace(store, name=None):
    tid = start_explicit(store, name)
    try:
        yield tid
    finally:
        end_explicit(store, tid)
