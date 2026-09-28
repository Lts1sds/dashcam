"""Measure dashcam's per-call recording overhead against a stub SDK client.

No network, no SDK dependencies: the stub returns instantly, so any extra
time in the patched run is dashcam's own cost (trace grouping, JSON
serialization, cost lookup, SQLite write with commit).

Usage:
    python benchmarks/bench_overhead.py
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashcam import patcher  # noqa: E402
from dashcam.storage import Store  # noqa: E402

N_CALLS = 2000
N_DB = 1000

MESSAGES = [
    {"role": "system", "content": "You are a helpful assistant. Be concise."},
    {"role": "user", "content": "Summarize the quarterly report below in two paragraphs."},
    {"role": "assistant", "content": "Sure - please paste the report text."},
    {
        "role": "user",
        "content": "Revenue grew 18% YoY to $412M. The cloud segment reached $158M (+34%), "
        "enterprise $121M (+9%), consumer $97M (+4%). Net income was $61M. "
        "The board approved a $200M buyback and raised FY guidance by 3%.",
    },
    {"role": "user", "content": "Also mention the hiring plan: two backend engineers in Q4."},
    {"role": "user", "content": "Keep it under 120 words and end with a one-line outlook."},
]

RESPONSE = {
    "id": "chatcmpl-bench",
    "model": "gpt-4o",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Acme posted a strong quarter: revenue up 18% YoY to $412M, "
                "led by cloud at $158M (+34%). Net income reached $61M, and the board "
                "raised FY guidance by 3% while approving a $200M buyback. Outlook: "
                "cloud momentum should keep compounding into next year.",
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 118, "completion_tokens": 21},
}


class StubSync:
    def create(self, **kwargs):
        return RESPONSE


class StubAsync:
    async def create(self, **kwargs):
        return RESPONSE


def bench_sync(store: Store) -> tuple[float, float]:
    base_obj = StubSync()
    t0 = time.perf_counter()
    for _ in range(N_CALLS):
        base_obj.create(model="gpt-4o", messages=MESSAGES)
    base = (time.perf_counter() - t0) / N_CALLS

    patcher._patch_attr(StubSync, "create", "openai", "chat", store)
    patched_obj = StubSync()
    t0 = time.perf_counter()
    for _ in range(N_CALLS):
        patched_obj.create(model="gpt-4o", messages=MESSAGES)
    patched = (time.perf_counter() - t0) / N_CALLS
    return base, patched


def bench_async(store: Store) -> tuple[float, float]:
    async def run(obj: StubAsync, n: int) -> None:
        for _ in range(n):
            await obj.create(model="gpt-4o", messages=MESSAGES)

    base_obj = StubAsync()
    t0 = time.perf_counter()
    asyncio.run(run(base_obj, N_CALLS))
    base = (time.perf_counter() - t0) / N_CALLS

    patcher._patch_attr(StubAsync, "create", "openai", "chat", store)
    patched_obj = StubAsync()
    t0 = time.perf_counter()
    asyncio.run(run(patched_obj, N_CALLS))
    patched = (time.perf_counter() - t0) / N_CALLS
    return base, patched


def bench_db(store: Store) -> float:
    tid = store.start_trace("bench")
    req = {"model": "gpt-4o", "messages": MESSAGES}
    t0 = time.perf_counter()
    for i in range(N_DB):
        store.record_span(
            tid,
            i,
            "openai",
            "chat",
            "gpt-4o",
            t0 + i,
            t0 + i + 0.5,
            req,
            RESPONSE,
            None,
            118,
            21,
            0.00042,
        )
    return (time.perf_counter() - t0) / N_DB


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(str(Path(tmp) / "bench.db"))
        try:
            base_s, pat_s = bench_sync(store)
            base_a, pat_a = bench_async(store)
            db_us = bench_db(store)
        finally:
            store.close()

    print(
        f"sync calls:        baseline {base_s * 1e6:8.1f} us   patched {pat_s * 1e6:8.1f} us"
        f"   overhead {(pat_s - base_s) * 1e6:6.1f} us/call"
    )
    print(
        f"async calls:       baseline {base_a * 1e6:8.1f} us   patched {pat_a * 1e6:8.1f} us"
        f"   overhead {(pat_a - base_a) * 1e6:6.1f} us/call"
    )
    print(f"sqlite span write: {db_us * 1e3:8.2f} ms/span   ({1.0 / db_us:,.0f} spans/s)")
    worst = max(pat_s - base_s, pat_a - base_a)
    print(f"overhead vs a 500 ms LLM call: {worst / 0.5 * 100:.3f}%")


if __name__ == "__main__":
    main()
