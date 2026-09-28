# How dashcam works

dashcam is a zero-dependency, zero-config recorder for LLM/agent traffic.
This document explains exactly what happens between `pip install dashcam` and
the dashboard on your screen: activation, patching, trace grouping, streaming
reassembly, cost estimation, storage, and the safety model that keeps your
program running even when dashcam itself misbehaves.

Everything below runs on the Python standard library only - `sqlite3`,
`http.server`, `threading`, `json`. No SDK is required to be installed; dashcam
patches whatever it finds.

## 1. Activation

There are three ways to turn dashcam on, from most explicit to most magical:

1. **Explicit** - call it yourself:

   ```python
   import dashcam

   dashcam.instrument()  # returns the list of patched entry points
   ```

2. **Opt-in global hook** - `dashcam install` writes a `dashcam.pth` file into
   your site-packages. Python executes `.pth` files at every interpreter
   startup, so the hook loads before your code runs. The hook checks the
   `DASHCAM` environment variable and only patches when it is set:

   ```bash
   dashcam install                # one-time setup
   DASHCAM=1 python my_agent.py   # recording on
   python my_agent.py            # recording off (hook is a no-op)
   ```

   This is the "zero code changes" mode: flip one environment variable and any
   program in that interpreter - including scripts you do not own - gets
   recorded. `dashcam uninstall` removes the hook.

3. **Scoped context** - group calls explicitly and give the trace a name:

   ```python
   with dashcam.trace("refund flow"):
       agent.run()
   ```

The `.pth` hook imports the (tiny) `dashcam.bootstrap` module in every Python
process, then does nothing unless `DASHCAM` is set. If you never call
`dashcam install`, nothing is ever imported automatically.

## 2. What gets patched

`dashcam.instrument()` probes for installed SDKs with `importlib.util.find_spec`
(no import side effects) and patches the entry points that exist:

| SDK | Patched entry points |
| --- | --- |
| openai | `resources.chat.completions.Completions.create` (sync + async), `resources.responses.Responses.create` (sync + async) |
| anthropic | `resources.messages.Messages.create` / `AsyncMessages.create`, `Messages.stream` / `AsyncMessages.stream` (context managers) |
| litellm | `litellm.completion`, `litellm.acompletion` |

Patching is a plain attribute replacement on the class (or module, for
litellm). The wrapper saves the original on itself as `__dashcam_orig__` and
guards against double-patching with a module-level key set, so calling
`instrument()` twice is safe. If an SDK is half-installed or its internals
change shape, the `ImportError` is swallowed: dashcam records less, never
crashes.

Each wrapper comes in four shapes, chosen by inspection:

- **sync function** - wrap, call, record result or error
- **async function** - same, through `await`
- **context manager** (anthropic `stream`) - wrap the enter/exit, record at
  exit via `get_final_message()`
- **iterator** (openai/anthropic `stream=True`) - wrap `__next__`/`__anext__`,
  accumulate chunks, record once at `StopIteration`

## 3. Trace grouping

A *trace* is one logical task; a *span* is one LLM call inside it. dashcam
groups spans into traces with a per-thread state (`threading.local`):

- The first recorded call on a thread opens a trace.
- Subsequent calls on the same thread within a **5-minute idle window** join
  it. A gap longer than that starts a new trace - so a long-running agent loop
  produces one trace, while an unrelated later script run does not get glued
  onto it.
- The trace is named from the first user message in the first request
  (whitespace-normalized, 60 chars). `dashcam.trace("name")` overrides this
  explicitly.
- Span order inside a trace is a per-thread counter, so the dashboard shows
  calls in the order the thread issued them.

This is deliberately simple: no spans are shipped anywhere, no agent framework
is required, and a plain `while` loop with `openai.create()` in it is already a
traceable "agent".

## 4. What is recorded per span

For every call, one row is written to SQLite:

- `provider` / `kind` / `model` - which patched entry point, and the model
  string from the request
- `started_at` / `ended_at` - wall clock, so duration is honest
- `request` - the full call kwargs (messages, tools, temperature, ...) as JSON
- `response` - the SDK's own dump: `model_dump()` (pydantic v2), `to_dict()`,
  or `repr()` truncated to 4000 chars as a last resort
- `error` - `repr(exc)` if the call raised (re-raised untouched afterwards)
- `prompt_tokens` / `completion_tokens` - read from the response `usage`,
  accepting both OpenAI (`prompt_tokens`) and Anthropic (`input_tokens`)
  spellings
- `cost` - estimated from the price table (next section)

## 5. Streaming reassembly

`stream=True` responses are wrapped in an iterator proxy that passes every
chunk through untouched while accumulating state:

- **openai**: text deltas from `choices[0].delta.content` are appended;
  `delta.tool_calls` fragments are reassembled by their `index` slot -
  `function.name` is set once, `function.arguments` strings are concatenated -
  so a tool call that arrived in 30 chunks is stored as one coherent call.
- **anthropic**: the event stream is interpreted - `message_start` captures
  the model and input tokens, `content_block_start` opens a `tool_use` slot,
  `text_delta` appends text, `input_json_delta` appends JSON fragments,
  `message_delta` captures final output tokens.

The span is recorded once, when the stream ends (or fails). If accumulation
itself throws, the exception is swallowed and the span is still recorded with
whatever was captured so far.

## 6. Cost estimation

`dashcam.cost.estimate(model, prompt_tokens, completion_tokens)`:

1. The model string is matched against a built-in price table (USD per 1M
   tokens, in/out) covering common GPT, Claude, DeepSeek, Gemini and Qwen
   models.
2. Matching is **longest-substring**: `gpt-4o-mini` wins over `gpt-4o`, so
   date-suffixed or deployment-suffixed names still price correctly.
3. `DASHCAM_PRICES=/path/to/prices.json` merges or overrides entries at
   startup. Unknown models cost `0.0` and are marked "not estimated" in the
   UI - dashcam never guesses a price it does not know.

Prices are per-token estimates, not invoices; the goal is making a runaway
loop visible in dollars, not billing reconciliation.

## 7. Storage

One SQLite file (`~/.dashcam/traces.db`, or `DASHCAM_DB` to override) with two
tables, `traces` and `spans`, plus covering indexes. The connection runs in
WAL mode with `synchronous=NORMAL`, so concurrent readers (the dashboard)
never block the writer (your agent), and a crash cannot corrupt the database.
Each span insert commits immediately - a hard kill of your process loses at
most the call in flight, never the recording.

The dashboard server is a `ThreadingHTTPServer` on `127.0.0.1:8377` with five
endpoints: `GET /api/traces`, `GET /api/trace/<id>`, `GET /api/stats`,
`GET /api/export/<id>` (JSON download), `POST /api/clear`. It binds localhost
only; nothing is exposed to the network, and no data ever leaves your machine.

## 8. Implicit tool-step inference

Agent frameworks all do the same dance: call the LLM, execute the tool calls
it asked for, feed results back as `tool` messages. dashcam does not need to
know your framework. The dashboard diffs the `messages` arrays of consecutive
spans in a trace: any new `tool`-role message between call N and call N+1 is
rendered as a tool execution card between them. This works for LangChain,
raw loops, hand-rolled agents - anything that follows the standard message
protocol.

## 9. The safety model

The core promise: **dashcam must never break your program.** Every layer is
defensive:

- patching failures are caught per-SDK (`ImportError` on odd SDK layouts)
- every wrapper body is wrapped; recording errors are swallowed
- the original function is called *before* any recording work on the success
  path, and exceptions are re-raised untouched after recording the error
- streaming proxies pass chunks through first and accumulate second
- worst case in every failure mode: you lose telemetry, not your run

The only synchronous cost on your hot path is one `time.time()`, a JSON dump
of the request kwargs, and one SQLite insert. Benchmarks on a stub SDK
(`benchmarks/bench_overhead.py`) measure the full record-and-commit path:

- ~80 us overhead per patched call (sync or async)
- ~0.08 ms per SQLite span write (~12,000 spans/s)
- about **0.02%** of the wall time of a typical 500 ms LLM call

## 10. Limitations (by design, for now)

- Single machine, single user. No remote collection, no multi-process merge.
- Trace grouping is thread-based: asyncio tasks on one thread share a trace;
  multi-threaded agents get one trace per thread unless you use
  `dashcam.trace()`.
- Cost is estimated from token counts and a static price table, not from your
  provider invoice.
- No OpenTelemetry export yet - see the README roadmap.
