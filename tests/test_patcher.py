import asyncio
import sys
import types

import pytest

from dashcam import patcher
from dashcam.storage import Store


class FakeUsage:
    prompt_tokens = 10
    completion_tokens = 5
    input_tokens = 10
    output_tokens = 5


class FakeResponse:
    model = "gpt-4o-mini"

    def model_dump(self):
        return {
            "id": "resp1",
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "hello there"},
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

    usage = FakeUsage()


class FakeChunk:
    def __init__(self, text):
        delta = types.SimpleNamespace(content=text, tool_calls=None)
        self.choices = [types.SimpleNamespace(delta=delta)]
        self.model = "gpt-4o-mini"
        self.usage = None


def make_fake_openai():
    mod = types.ModuleType("openai")
    resources = types.ModuleType("openai.resources")
    chat = types.ModuleType("openai.resources.chat")
    completions = types.ModuleType("openai.resources.chat.completions")

    class Completions:
        def create(self, **kwargs):
            if kwargs.get("stream"):

                def gen():
                    yield FakeChunk("he")
                    yield FakeChunk("llo")

                return gen()
            return FakeResponse()

    class AsyncCompletions:
        async def create(self, **kwargs):
            return FakeResponse()

    class FailingCompletions:
        def create(self, **kwargs):
            raise RuntimeError("boom: connection reset")

    completions.Completions = Completions
    completions.AsyncCompletions = AsyncCompletions
    completions.FailingCompletions = FailingCompletions
    chat.completions = completions
    resources.chat = chat
    mod.resources = resources
    return mod


@pytest.fixture
def fake_openai(monkeypatch):
    mod = make_fake_openai()
    for name in (
        "openai",
        "openai.resources",
        "openai.resources.chat",
        "openai.resources.chat.completions",
    ):
        monkeypatch.setitem(
            sys.modules,
            name,
            getattr(mod, "resources", mod).chat.completions
            if name.endswith("completions")
            else (
                mod
                if name == "openai"
                else mod.resources
                if name == "openai.resources"
                else mod.resources.chat
            ),
        )
    patcher._patched.clear()
    yield mod
    patcher._patched.clear()


def test_sync_capture(tmp_path, fake_openai):
    store = Store(str(tmp_path / "t.db"))
    patched = patcher.instrument(store)
    assert any("Completions.create" in k for k in patched)

    client = fake_openai.resources.chat.completions.Completions()
    resp = client.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "say hi"}])
    assert resp.model == "gpt-4o-mini"

    traces = store.list_traces()
    assert len(traces) == 1
    assert traces[0]["name"] == "say hi"
    assert traces[0]["span_count"] == 1
    assert traces[0]["prompt_tokens"] == 10
    assert traces[0]["completion_tokens"] == 5
    assert traces[0]["cost"] > 0
    assert traces[0]["status"] == "running"

    span = store.get_trace(traces[0]["id"])["spans"][0]
    assert span["response"]["choices"][0]["message"]["content"] == "hello there"
    assert span["request"]["model"] == "gpt-4o-mini"


def test_stream_capture(tmp_path, fake_openai):
    store = Store(str(tmp_path / "t.db"))
    patcher.instrument(store)

    client = fake_openai.resources.chat.completions.Completions()
    out = list(
        client.create(
            model="gpt-4o-mini", stream=True, messages=[{"role": "user", "content": "hi"}]
        )
    )
    assert len(out) == 2

    traces = store.list_traces()
    assert traces[0]["span_count"] == 1
    span = store.get_trace(traces[0]["id"])["spans"][0]
    assert span["response"]["content"] == "hello"
    assert span["response"]["stream"] is True


def test_async_capture(tmp_path, fake_openai):
    store = Store(str(tmp_path / "t.db"))
    patcher.instrument(store)

    client = fake_openai.resources.chat.completions.AsyncCompletions()
    asyncio.run(
        client.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "async hi"}])
    )

    traces = store.list_traces()
    assert traces[0]["span_count"] == 1
    assert traces[0]["name"] == "async hi"


def test_error_capture(tmp_path, fake_openai, monkeypatch):
    store = Store(str(tmp_path / "t.db"))
    failing = fake_openai.resources.chat.completions.FailingCompletions
    key = patcher._patch_attr(failing, "create", "openai", "chat", store)
    assert key

    with pytest.raises(RuntimeError):
        failing().create(model="gpt-4o-mini", messages=[{"role": "user", "content": "will fail"}])

    traces = store.list_traces()
    assert traces[0]["status"] == "error"
    span = store.get_trace(traces[0]["id"])["spans"][0]
    assert "boom" in span["error"]


def test_idempotent(tmp_path, fake_openai):
    store = Store(str(tmp_path / "t.db"))
    p1 = patcher.instrument(store)
    p2 = patcher.instrument(store)
    assert p1
    assert p2 == []
