"""Shared test fixtures/helpers."""

from __future__ import annotations

import pytest

from dashcam import context


@pytest.fixture(autouse=True)
def clean_thread_context():
    context._local.trace = None
    context._local.span_idx = 0
    yield
    context._local.trace = None


def restore_real_sdks() -> None:
    """Fully unwrap dashcam wrappers from the real SDK classes.

    Any real-SDK test module that calls patcher.instrument() patches ALL
    installed SDKs globally (openai, anthropic, mcp), so its teardown must
    restore all of them - not just the ones it asserts on. This also clears
    patcher._patched, which is safe here because every wrapper has been
    unwrapped.
    """
    from dashcam import patcher

    targets: list[tuple[type, str]] = []
    try:
        from openai.resources import responses as rr
        from openai.resources.chat import completions as cc

        targets += [
            (cc.Completions, "create"),
            (cc.AsyncCompletions, "create"),
            (rr.Responses, "create"),
            (rr.AsyncResponses, "create"),
        ]
    except ImportError:
        pass
    try:
        from anthropic.resources import messages as mm

        targets += [
            (mm.Messages, "create"),
            (mm.AsyncMessages, "create"),
            (mm.Messages, "stream"),
            (mm.AsyncMessages, "stream"),
        ]
    except ImportError:
        pass
    try:
        from mcp.client.session import ClientSession

        targets += [(ClientSession, a) for a in ("call_tool", "list_tools", "read_resource")]
    except ImportError:
        pass
    for cls, attr in targets:
        fn = getattr(cls, attr, None)
        while getattr(fn, "__dashcam_orig__", None) is not None:
            fn = fn.__dashcam_orig__
        setattr(cls, attr, fn)
    patcher._patched.clear()
