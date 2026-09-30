<div align="center">

<img src="docs/logo.svg" alt="dashcam logo" width="340">

# dashcam

**The dashcam for your AI agents.**

Zero-config, local-first tracing, replay and cost debugging for LLM apps and agents — now with MCP tool-call capture.

[Quickstart](#-quickstart) · [How it works](#-how-it-works) · [Configuration](#%EF%B8%8F-configuration) · [FAQ](#-faq)

[![CI](https://github.com/Lts1sds/dashcam/actions/workflows/ci.yml/badge.svg)](https://github.com/Lts1sds/dashcam/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org)
![Zero dependencies](https://img.shields.io/badge/dependencies-zero-green.svg)

**English** | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Русский](README.ru.md) | [Português (Brasil)](README.pt-BR.md) | [हिन्दी](README.hi.md)

</div>

---

Your agent failed at 2am. *Which* call failed? What did it *actually* send? How much did the whole run cost, and where did the tokens go?

A dashcam in a car records everything silently in the background — and when something goes wrong, you rewind the tape and see exactly what happened. **dashcam does that for LLM apps**: it silently records every LLM call your program makes, then gives you a local timeline to replay, inspect and attribute failures.

## Why dashcam

| | dashcam | LangSmith / Langfuse | print() debugging |
|---|---|---|---|
| Code changes needed | **none** | SDK / decorator | everywhere |
| Data leaves your machine | **never** | cloud or self-hosted server | - |
| Dependencies | **zero** (pure stdlib) | server + DB + SDK | - |
| Setup time | 10 seconds | minutes to hours | - |
| Cost tracking | built-in | varies | manual |
| Works with any framework | yes (patches the SDK) | framework-specific | - |

## Quickstart

```bash
pip install dashcam
dashcam demo        # generates demo traces, no API key needed
dashcam             # opens the dashboard at http://127.0.0.1:8377
```

### Option A — zero code changes (recommended)

```bash
dashcam install                          # one-time, writes a .pth hook
DASHCAM=1 python your_agent.py           # that's it. everything is recorded
```

On Windows: `set DASHCAM=1 && python your_agent.py`

### Option B — one import line

```python
import dashcam
dashcam.instrument()   # patches openai / anthropic / litellm / mcp if present
```

### Option C — explicit trace boundaries (optional)

```python
with dashcam.trace("refund-processing-agent") as tid:
    run_agent()   # all LLM calls inside are grouped into one trace
```

Without explicit boundaries, calls are grouped automatically by thread + activity gap — no code changes required.

## What you get

<p align="center">
  <img src="docs/screenshot.png" alt="dashcam dashboard showing an agent timeline" width="860">
</p>

- **Timeline replay** — every LLM call in order, with full request messages, params, tools and responses. Click any step to expand.
- **Inferred tool steps** — dashcam diffs consecutive message arrays to reconstruct *what your agent did between calls* (tool executions, user turns) — **without any framework integration**.
- **MCP tool-call capture** — calls made through the official `mcp` SDK (`ClientSession.call_tool`, `list_tools`, `read_resource`) are recorded as tool cards on the timeline, so LLM steps and MCP tool steps appear in one replay.
- **Failure attribution** — failed calls get red cards with the full exception. The trace list shows errors at a glance.
- **Cost & token accounting** — per-call and per-trace token counts and USD cost estimates for common OpenAI / Anthropic / DeepSeek / Gemini / Qwen models. Bring your own price table via `DASHCAM_PRICES`.
- **Streaming support** — streamed responses are reassembled and recorded, including tool-call fragments.
- **Local & private** — everything in a single SQLite file (`~/.dashcam/traces.db`). No server, no account, no telemetry.

## How it works

```
                    your program
                         │
    openai / anthropic / litellm / mcp SDK calls
                         │
              ┌──────────▼──────────┐
              │  dashcam patcher    │   monkey-patches SDK entry points
              │  (zero config)     │   records request / response / usage
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  SQLite store        │   ~/.dashcam/traces.db (WAL)
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  local dashboard    │   stdlib http.server, port 8377
              │  replay · costs     │   trace list, timeline, JSON export
              └─────────────────────┘
```

dashcam patches the client classes of installed SDKs at import time. Your program's behavior is untouched — if dashcam itself ever fails, it fails silently and your agent keeps running.
Full internals: [docs/how-it-works.md](docs/how-it-works.md) — activation, patching, streaming reassembly, cost estimation, storage, and the safety model.

### Supported SDKs

| SDK | entry points | sync | async | streaming |
|---|---|---|---|---|
| openai >= 1.0 | `chat.completions.create`, `responses.create` | ✅ | ✅ | ✅ |
| anthropic | `messages.create`, `messages.stream` | ✅ | ✅ | ✅ |
| litellm | `completion`, `acompletion` | ✅ | ✅ | ✅ |
| mcp >= 1.0 | `ClientSession.call_tool`, `list_tools`, `read_resource` | — | ✅ | — |

Anything routed through these (LangChain, AutoGen, CrewAI, OpenAI-compatible endpoints via litellm, MCP servers like filesystem / git / playwright, ...) is captured automatically.

## ⚙️ Configuration

| Env var | Default | Meaning |
|---|---|---|
| `DASHCAM` | unset | When set to `1`, the `.pth` hook auto-instruments at interpreter startup |
| `DASHCAM_DB` | `~/.dashcam/traces.db` | SQLite database location |
| `DASHCAM_PRICES` | built-in table | Path to a JSON price table: `{"model-substring": [input_per_mtok, output_per_mtok]}` |

Price matching is substring-based, longest key wins (e.g. `gpt-4o-mini` beats `gpt-4o`). Prices are estimates — override with your own table for billing-grade numbers.

## CLI

```
dashcam                # open the dashboard (default)
dashcam demo           # generate demo traces without an API key
dashcam install        # enable zero-code auto-instrumentation
dashcam uninstall      # disable auto-instrumentation
dashcam export <id>    # dump one trace as JSON
dashcam clear          # delete all traces
```

## FAQ

**Does it slow down my agent?**
Measured with `benchmarks/bench_overhead.py`: ~80 µs overhead per call, ~0.08 ms per SQLite write — about 0.02% of a 500 ms LLM call. You won't notice.

**What if dashcam breaks?**
All dashcam logic is wrapped defensively — if anything inside dashcam throws, the exception is swallowed and your program continues unaffected.

**Does it send data anywhere?**
No. No network calls, no telemetry, no account. The dashboard binds to 127.0.0.1 only.

**How are calls grouped into traces?**
Explicitly via `dashcam.trace(name)`, or automatically: calls on the same thread within a 5-minute activity gap join the same trace. Idle traces are closed automatically.

**Streaming responses?**
Chunks are accumulated (text, tool-call fragments, usage) and recorded when the stream finishes. `stream_options={"include_usage": True}` is respected for OpenAI usage capture.

## Development

```bash
git clone https://github.com/Lts1sds/dashcam
cd dashcam
pip install -e ".[dev]"
pytest                       # 34 tests, no API keys needed
python examples/demo_agent.py   # offline agent-loop demo
```

## Roadmap

- [x] MCP tool-call capture (v0.2)
- [ ] Prompt diff view (what changed between calls)
- [ ] Search across all traces
- [ ] Time-travel replay of a single step in a REPL
- [ ] Framework adapters (LangChain callbacks, OpenTelemetry bridge)

## License

MIT
