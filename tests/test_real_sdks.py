"""End-to-end tests against the real openai/anthropic SDKs with mocked HTTP.

These exercise the actual SDK class structure (decorated entry points,
pydantic responses, SSE decoding) instead of stub modules. They are skipped
automatically when the SDKs are not installed, and need no API key: all HTTP
traffic is intercepted by a mock transport.
"""

from __future__ import annotations

import asyncio

import pytest

openai = pytest.importorskip("openai", reason="openai SDK not installed")
anthropic = pytest.importorskip("anthropic", reason="anthropic SDK not installed")

import httpx  # noqa: E402

try:  # newer SDKs (anthropic >= 1.6) require the httpx2 fork
    import httpx2  # noqa: F401

    HTTPX2 = True
except ImportError:
    HTTPX2 = False

from dashcam import patcher  # noqa: E402
from dashcam.storage import Store  # noqa: E402

OPENAI_JSON = {
    "id": "chatcmpl-e2e",
    "object": "chat.completion",
    "model": "gpt-4o",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "Hello!"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
}

OPENAI_SSE = (
    'data: {"id":"chatcmpl-s","object":"chat.completion.chunk","model":"gpt-4o",'
    '"choices":[{"index":0,"delta":{"role":"assistant","content":"Hel"},"finish_reason":null}]}\n\n'
    'data: {"id":"chatcmpl-s","object":"chat.completion.chunk","model":"gpt-4o",'
    '"choices":[{"index":0,"delta":{"content":"lo"},"finish_reason":null}]}\n\n'
    'data: {"id":"chatcmpl-s","object":"chat.completion.chunk","model":"gpt-4o",'
    '"choices":[{"index":0,"delta":{},"finish_reason":"stop"}],'
    '"usage":{"prompt_tokens":10,"completion_tokens":2,"total_tokens":12}}\n\n'
    "data: [DONE]\n\n"
)

ANTHROPIC_JSON = {
    "id": "msg_e2e",
    "type": "message",
    "role": "assistant",
    "model": "claude-sonnet-4",
    "content": [{"type": "text", "text": "Hi there!"}],
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 10, "output_tokens": 2},
}

ANTHROPIC_SSE = (
    'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_s",'
    '"type":"message","role":"assistant","model":"claude-sonnet-4","content":[],'
    '"stop_reason":null,"usage":{"input_tokens":10,"output_tokens":1}}}\n\n'
    'event: content_block_start\ndata: {"type":"content_block_start","index":0,'
    '"content_block":{"type":"text","text":""}}\n\n'
    'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,'
    '"delta":{"type":"text_delta","text":"Hi"}}\n\n'
    'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n'
    'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn"},'
    '"usage":{"output_tokens":2}}\n\n'
    'event: message_stop\ndata: {"type":"message_stop"}\n\n'
)


def _anthropic_http_mod():
    if HTTPX2:
        import httpx2

        return httpx2
    return httpx


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    s = Store(str(tmp_path_factory.mktemp("realsdk") / "realsdk.db"))
    patched = patcher.instrument(s)
    assert len(patched) >= 8, patched
    yield s
    # restore the real SDK classes (unwrap the full __dashcam_orig__ chain)
    from anthropic.resources import messages as mm
    from openai.resources import responses as rr
    from openai.resources.chat import completions as cc

    for cls, attr in [
        (cc.Completions, "create"),
        (cc.AsyncCompletions, "create"),
        (rr.Responses, "create"),
        (rr.AsyncResponses, "create"),
        (mm.Messages, "create"),
        (mm.AsyncMessages, "create"),
        (mm.Messages, "stream"),
        (mm.AsyncMessages, "stream"),
    ]:
        fn = getattr(cls, attr, None)
        while getattr(fn, "__dashcam_orig__", None) is not None:
            fn = fn.__dashcam_orig__
        setattr(cls, attr, fn)
    patcher._patched.clear()
    s.close()


def test_openai_sync(store):
    client = openai.OpenAI(
        api_key="sk-test",
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=OPENAI_JSON))
        ),
    )
    msg = client.chat.completions.create(
        model="gpt-4o", messages=[{"role": "user", "content": "hi"}]
    )
    assert msg.choices[0].message.content == "Hello!"


def test_openai_async(store):
    async def run():
        client = openai.AsyncOpenAI(
            api_key="sk-test",
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(lambda r: httpx.Response(200, json=OPENAI_JSON))
            ),
        )
        return await client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": "hi"}]
        )

    msg = asyncio.run(run())
    assert msg.choices[0].message.content == "Hello!"


def test_openai_stream(store):
    def run(stream: bool):
        client = openai.OpenAI(
            api_key="sk-test",
            http_client=httpx.Client(
                transport=httpx.MockTransport(
                    lambda r: httpx.Response(
                        200,
                        content=OPENAI_SSE.encode(),
                        headers={"content-type": "text/event-stream"},
                    )
                )
            ),
        )
        text = ""
        for ch in client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": "hi"}], stream=True
        ):
            if ch.choices and ch.choices[0].delta.content:
                text += ch.choices[0].delta.content
        return text

    assert run(True) == "Hello"


def test_openai_async_stream(store):
    async def run():
        client = openai.AsyncOpenAI(
            api_key="sk-test",
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda r: httpx.Response(
                        200,
                        content=OPENAI_SSE.encode(),
                        headers={"content-type": "text/event-stream"},
                    )
                )
            ),
        )
        text = ""
        stream = await client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": "hi"}], stream=True
        )
        async for ch in stream:
            if ch.choices and ch.choices[0].delta.content:
                text += ch.choices[0].delta.content
        return text

    assert asyncio.run(run()) == "Hello"


def test_anthropic_sync(store):
    h = _anthropic_http_mod()
    client = anthropic.Anthropic(
        api_key="test-key",
        http_client=h.Client(
            transport=h.MockTransport(lambda r: h.Response(200, json=ANTHROPIC_JSON))
        ),
    )
    msg = client.messages.create(
        model="claude-sonnet-4", max_tokens=32, messages=[{"role": "user", "content": "hi"}]
    )
    assert msg.content[0].text == "Hi there!"


def test_anthropic_stream_cm(store):
    h = _anthropic_http_mod()
    client = anthropic.Anthropic(
        api_key="test-key",
        http_client=h.Client(
            transport=h.MockTransport(
                lambda r: h.Response(
                    200,
                    content=ANTHROPIC_SSE.encode(),
                    headers={"content-type": "text/event-stream"},
                )
            )
        ),
    )
    text = ""
    with client.messages.stream(
        model="claude-sonnet-4", max_tokens=32, messages=[{"role": "user", "content": "hi"}]
    ) as s:
        for t in s.text_stream:
            text += t
        assert s.get_final_message().usage.output_tokens == 2
    assert text == "Hi"


def test_anthropic_async(store):
    h = _anthropic_http_mod()

    async def run():
        client = anthropic.AsyncAnthropic(
            api_key="test-key",
            http_client=h.AsyncClient(
                transport=h.MockTransport(lambda r: h.Response(200, json=ANTHROPIC_JSON))
            ),
        )
        return await client.messages.create(
            model="claude-sonnet-4", max_tokens=32, messages=[{"role": "user", "content": "hi"}]
        )

    msg = asyncio.run(run())
    assert msg.content[0].text == "Hi there!"


def test_db_contents(store):
    """All calls from this module landed in the store with correct usage/cost."""
    traces = store.list_traces(50)
    spans = []
    for t in traces:
        spans.extend(store.get_trace(t["id"])["spans"])
    assert len(spans) == 7, [s["provider"] for s in spans]
    assert all(s["error"] is None for s in spans)

    gpt = [s for s in spans if s["model"] == "gpt-4o"]
    assert len(gpt) == 4
    assert all(s["prompt_tokens"] == 10 and s["completion_tokens"] == 2 for s in gpt)
    assert all(abs(s["cost"] - (10 * 2.50 + 2 * 10.00) / 1e6) < 1e-9 for s in gpt)

    claude = [s for s in spans if s["model"] == "claude-sonnet-4"]
    assert len(claude) == 3
    assert all(s["prompt_tokens"] == 10 for s in claude)
    assert all(abs(s["cost"] - (10 * 3.00 + 2 * 15.00) / 1e6) < 1e-9 for s in claude)

    stream_spans = [
        s for s in spans if isinstance(s.get("response"), dict) and s["response"].get("stream")
    ]
    assert len(stream_spans) == 2
    assert all(s["response"].get("content") in ("Hello", "Hi") for s in stream_spans)
