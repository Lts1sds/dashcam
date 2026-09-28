import inspect
import time

from . import context, cost

_patched = set()


class _SpanCtx:
    __slots__ = ("store", "tid", "idx", "provider", "kind", "model",
                 "started", "kwargs")

    def __init__(self, store, tid, idx, provider, kind, model, started, kwargs):
        self.store = store
        self.tid = tid
        self.idx = idx
        self.provider = provider
        self.kind = kind
        self.model = model
        self.started = started
        self.kwargs = kwargs


def instrument(store):
    patched = []
    try:
        import openai
        patched += _patch_openai(store)
    except ImportError:
        pass
    try:
        import anthropic
        patched += _patch_anthropic(store)
    except ImportError:
        pass
    try:
        import litellm
        patched += _patch_litellm(store)
    except ImportError:
        pass
    return patched


def _patch_openai(store):
    out = []
    from openai.resources.chat import completions as cc
    out.append(_patch_attr(cc.Completions, "create", "openai", "chat", store))
    out.append(_patch_attr(cc.AsyncCompletions, "create", "openai", "chat", store))
    try:
        from openai.resources import responses as rr
        out.append(_patch_attr(rr.Responses, "create", "openai", "responses", store))
        out.append(_patch_attr(rr.AsyncResponses, "create", "openai", "responses", store))
    except ImportError:
        pass
    return [x for x in out if x]


def _patch_anthropic(store):
    out = []
    from anthropic.resources import messages as mm
    out.append(_patch_attr(mm.Messages, "create", "anthropic", "messages", store))
    out.append(_patch_attr(mm.AsyncMessages, "create", "anthropic", "messages", store))
    out.append(_patch_cm(mm.Messages, "stream", "anthropic", "messages", store))
    out.append(_patch_cm(mm.AsyncMessages, "stream", "anthropic", "messages", store))
    return [x for x in out if x]


def _patch_litellm(store):
    out = []
    out.append(_patch_attr(litellm_module(), "completion", "litellm", "chat", store))
    out.append(_patch_attr(litellm_module(), "acompletion", "litellm", "chat", store))
    return [x for x in out if x]


def litellm_module():
    import litellm
    return litellm


def _qualname(obj, attr):
    name = getattr(obj, "__qualname__", None) or getattr(obj, "__name__", None)
    if name is None:
        name = str(id(obj))
    if inspect.ismodule(obj):
        return f"{obj.__name__}.{attr}"
    return f"{name}.{attr}"


def _patch_attr(obj, attr, provider, kind, store):
    key = _qualname(obj, attr)
    if key in _patched:
        return None
    orig = getattr(obj, attr)
    if inspect.iscoroutinefunction(orig):
        wrapper = _make_async(orig, provider, kind, store)
    else:
        wrapper = _make_sync(orig, provider, kind, store)
    wrapper.__dashcam_orig__ = orig
    setattr(obj, attr, wrapper)
    _patched.add(key)
    return key


def _patch_cm(obj, attr, provider, kind, store):
    key = _qualname(obj, attr)
    if key in _patched:
        return None
    orig = getattr(obj, attr)

    def wrapper(*args, **kwargs):
        cm = orig(*args, **kwargs)
        span = _begin(store, provider, kind, kwargs)
        return _WrapCM(cm, span)

    wrapper.__dashcam_orig__ = orig
    setattr(obj, attr, wrapper)
    _patched.add(key)
    return key


def _model_from(kwargs, args):
    model = kwargs.get("model") if isinstance(kwargs, dict) else None
    if model:
        return str(model)
    if args:
        first = args[0]
        if isinstance(first, str):
            return first
    return ""


def _begin(store, provider, kind, kwargs, args=()):
    started = time.time()
    model = _model_from(kwargs, args)
    name = context.derive_name(kwargs)
    if name is None and isinstance(kwargs.get("input"), str):
        name = " ".join(kwargs["input"].split())[:60]
    tid = context.current_trace(store, name)
    idx = context.next_idx()
    return _SpanCtx(store, tid, idx, provider, kind, model, started, kwargs)


def _make_sync(orig, provider, kind, store):
    def wrapper(*args, **kwargs):
        span = _begin(store, provider, kind, kwargs, args)
        try:
            result = orig(*args, **kwargs)
        except Exception as e:
            _record_error(span, e)
            raise
        if kwargs.get("stream"):
            acc = _acc_anthropic if provider == "anthropic" else _acc_openai
            return _WrapIter(result, span, acc)
        try:
            _record_result(span, result)
        except Exception:
            pass
        return result
    return wrapper


def _make_async(orig, provider, kind, store):
    async def wrapper(*args, **kwargs):
        span = _begin(store, provider, kind, kwargs, args)
        try:
            result = await orig(*args, **kwargs)
        except Exception as e:
            _record_error(span, e)
            raise
        if kwargs.get("stream"):
            acc = _acc_anthropic if provider == "anthropic" else _acc_openai
            return _WrapIter(result, span, acc)
        try:
            _record_result(span, result)
        except Exception:
            pass
        return result
    return wrapper


def _request_json(kwargs):
    try:
        return dict(kwargs)
    except Exception:
        return {}


def _record_error(span, exc):
    try:
        span.store.record_span(
            span.tid, span.idx, span.provider, span.kind, span.model,
            span.started, time.time(), _request_json(span.kwargs), None,
            repr(exc)[:4000], 0, 0, 0.0)
    except Exception:
        pass


def _extract_response(result):
    try:
        if hasattr(result, "model_dump"):
            return result.model_dump()
    except Exception:
        pass
    try:
        if hasattr(result, "to_dict"):
            return result.to_dict()
    except Exception:
        pass
    return {"repr": repr(result)[:4000]}


def _extract_usage(result):
    u = getattr(result, "usage", None)
    if u is None:
        return 0, 0
    pt = getattr(u, "prompt_tokens", None)
    if pt is None:
        pt = getattr(u, "input_tokens", None)
    ct = getattr(u, "completion_tokens", None)
    if ct is None:
        ct = getattr(u, "output_tokens", None)
    return int(pt or 0), int(ct or 0)


def _record_result(span, result):
    response = _extract_response(result)
    pt, ct = _extract_usage(result)
    c, _ = cost.estimate(span.model, pt, ct)
    span.store.record_span(
        span.tid, span.idx, span.provider, span.kind, span.model,
        span.started, time.time(), _request_json(span.kwargs), response,
        None, pt, ct, c)


class _WrapIter:
    def __init__(self, gen, span, acc):
        self._gen = gen
        self._span = span
        self._acc = acc
        self._parts = []
        self._tools = {}
        self._usage = {}
        self._model = span.model
        self._done = False

    def __iter__(self):
        return self

    def __next__(self):
        try:
            chunk = next(self._gen)
        except StopIteration:
            self._finish(None)
            raise
        except Exception as e:
            self._finish(repr(e))
            raise
        try:
            self._acc(self, chunk)
        except Exception:
            pass
        return chunk

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            chunk = await self._gen.__anext__()
        except StopAsyncIteration:
            self._finish(None)
            raise
        except Exception as e:
            self._finish(repr(e))
            raise
        try:
            self._acc(self, chunk)
        except Exception:
            pass
        return chunk

    def _finish(self, error):
        if self._done:
            return
        self._done = True
        try:
            if error:
                self._span.store.record_span(
                    self._span.tid, self._span.idx, self._span.provider,
                    self._span.kind, self._model or self._span.model,
                    self._span.started, time.time(),
                    _request_json(self._span.kwargs), None, error, 0, 0, 0.0)
                return
            response = {
                "content": "".join(self._parts),
                "stream": True,
                "model": self._model or self._span.model,
            }
            if self._tools:
                response["tool_calls"] = [self._tools[k] for k in sorted(self._tools)]
            pt = self._usage.get("prompt_tokens", 0)
            ct = self._usage.get("completion_tokens", 0)
            if self._usage:
                response["usage"] = dict(self._usage)
            c, _ = cost.estimate(response.get("model") or "", pt, ct)
            self._span.store.record_span(
                self._span.tid, self._span.idx, self._span.provider,
                self._span.kind, response.get("model") or self._span.model,
                self._span.started, time.time(),
                _request_json(self._span.kwargs), response, None, pt, ct, c)
        except Exception:
            pass


class _WrapCM:
    def __init__(self, cm, span):
        self._cm = cm
        self._span = span
        self._inner = None

    def __enter__(self):
        self._inner = self._cm.__enter__()
        return self._inner

    async def __aenter__(self):
        self._inner = await self._cm.__aenter__()
        return self._inner

    def __exit__(self, exc_type, exc, tb):
        try:
            return self._cm.__exit__(exc_type, exc, tb)
        finally:
            self._capture(exc_type, exc)

    async def __aexit__(self, exc_type, exc, tb):
        try:
            return await self._cm.__aexit__(exc_type, exc, tb)
        finally:
            self._capture(exc_type, exc)

    def _capture(self, exc_type, exc):
        try:
            if exc_type is not None:
                self._span.store.record_span(
                    self._span.tid, self._span.idx, self._span.provider,
                    self._span.kind, self._span.model, self._span.started,
                    time.time(), _request_json(self._span.kwargs), None,
                    repr(exc)[:4000], 0, 0, 0.0)
                return
            try:
                msg = self._inner.get_final_message()
            except Exception:
                msg = None
            if msg is None:
                self._span.store.record_span(
                    self._span.tid, self._span.idx, self._span.provider,
                    self._span.kind, self._span.model, self._span.started,
                    time.time(), _request_json(self._span.kwargs),
                    {"stream": True}, None, 0, 0, 0.0)
                return
            _record_result(self._span, msg)
        except Exception:
            pass


def _acc_openai(rec, chunk):
    model = getattr(chunk, "model", None)
    if model:
        rec._model = model
    choices = getattr(chunk, "choices", None)
    if choices:
        delta = getattr(choices[0], "delta", None)
        if delta is not None:
            content = getattr(delta, "content", None)
            if isinstance(content, str):
                rec._parts.append(content)
            tcs = getattr(delta, "tool_calls", None)
            if tcs:
                for tc in tcs:
                    slot = rec._tools.setdefault(
                        tc.index,
                        {"id": "", "type": "function",
                         "function": {"name": "", "arguments": ""}})
                    if tc.id:
                        slot["id"] = tc.id
                    fn = getattr(tc, "function", None)
                    if fn is not None:
                        if fn.name:
                            slot["function"]["name"] = fn.name
                        if fn.arguments:
                            slot["function"]["arguments"] += fn.arguments
    pt, ct = _extract_usage(chunk)
    if pt or ct:
        rec._usage = {"prompt_tokens": pt, "completion_tokens": ct}


def _acc_anthropic(rec, event):
    et = getattr(event, "type", None)
    if et == "message_start":
        msg = getattr(event, "message", None)
        if msg is not None:
            pt, ct = _extract_usage(msg)
            rec._usage = {"prompt_tokens": pt, "completion_tokens": ct}
            if getattr(msg, "model", None):
                rec._model = msg.model
    elif et == "content_block_start":
        block = getattr(event, "content_block", None)
        if getattr(block, "type", None) == "tool_use":
            rec._tools[event.index] = {
                "id": getattr(block, "id", ""),
                "type": "function",
                "function": {"name": getattr(block, "name", ""),
                             "arguments": ""}}
    elif et == "content_block_delta":
        delta = getattr(event, "delta", None)
        dt = getattr(delta, "type", None)
        if dt == "text_delta":
            rec._parts.append(getattr(delta, "text", "") or "")
        elif dt == "input_json_delta" and event.index in rec._tools:
            rec._tools[event.index]["function"]["arguments"] += \
                getattr(delta, "partial_json", "") or ""
    elif et == "message_delta":
        u = getattr(event, "usage", None)
        if u is not None:
            ct = int(getattr(u, "output_tokens", 0) or 0)
            base = rec._usage or {}
            rec._usage = {"prompt_tokens": base.get("prompt_tokens", 0),
                          "completion_tokens": ct}
