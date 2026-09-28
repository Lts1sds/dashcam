"""
A minimal tool-using agent loop, recorded by dashcam.

Runs fully offline: it registers a stub module shaped like the openai SDK,
so you can see dashcam capture an agent loop without any API key.

    python examples/demo_agent.py
    dashcam
"""

import os
import sys
import time
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dashcam


def make_stub_openai():
    mod = types.ModuleType("openai")
    resources = types.ModuleType("openai.resources")
    chat = types.ModuleType("openai.resources.chat")
    completions = types.ModuleType("openai.resources.chat.completions")

    script = [
        {"type": "function", "function": {
            "name": "web_search", "arguments": '{"query": "python monkey patching"}'}},
        {"type": "function", "function": {
            "name": "calculator", "arguments": '{"expr": "137 * 42"}'}},
    ]

    class Completions:
        def create(self, **kwargs):
            msgs = kwargs.get("messages", [])
            n_assistant = sum(1 for m in msgs if m.get("role") == "assistant")
            if n_assistant < len(script):
                tc = script[n_assistant]
                content = None
                tool_calls = [{"id": f"call_00{n_assistant + 1}", **tc}]
                finish = "tool_calls"
            else:
                content = "137 * 42 = 5754. Monkey patching swaps methods at runtime."
                tool_calls = None
                finish = "stop"

            class R:
                model = "gpt-4o-mini"

                def __init__(self, n):
                    self._n = n

                @property
                def usage(self):
                    return types.SimpleNamespace(
                        prompt_tokens=40 + 60 * self._n, completion_tokens=20)

                def model_dump(self):
                    return {
                        "id": f"chatcmpl-stub{n_assistant}",
                        "model": "gpt-4o-mini",
                        "choices": [{"index": 0, "finish_reason": finish,
                                     "message": {"role": "assistant",
                                                 "content": content,
                                                 **({"tool_calls": tool_calls}
                                                    if tool_calls else {})}}],
                        "usage": {"prompt_tokens": self.usage.prompt_tokens,
                                  "completion_tokens": 20},
                    }

            time.sleep(0.05)
            return R(n_assistant)

    completions.Completions = Completions

    class AsyncCompletions:
        async def create(self, **kwargs):
            return Completions.create(self, **kwargs)

    completions.AsyncCompletions = AsyncCompletions
    chat.completions = completions
    resources.chat = chat
    mod.resources = resources
    return mod


stub = make_stub_openai()
sys.modules["openai"] = stub
sys.modules["openai.resources"] = stub.resources
sys.modules["openai.resources.chat"] = stub.resources.chat
sys.modules["openai.resources.chat.completions"] = stub.resources.chat.completions

patched = dashcam.instrument()
print("dashcam instrumented:", patched)

client = stub.resources.chat.completions.Completions()

messages = [
    {"role": "system", "content": "You are a helpful research assistant."},
    {"role": "user", "content": "Compute 137 * 42 and explain monkey patching."},
]
tools = [
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the web",
        "parameters": {"type": "object",
                       "properties": {"query": {"type": "string"}},
                       "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "calculator",
        "description": "Evaluate a math expression",
        "parameters": {"type": "object",
                       "properties": {"expr": {"type": "string"}},
                       "required": ["expr"]}}},
]

tool_results = {
    "call_001": "Monkey patching means replacing methods of classes or modules at runtime.",
    "call_002": "5754",
}

for step in range(3):
    resp = client.create(model="gpt-4o-mini", messages=messages, tools=tools)
    data = resp.model_dump()
    msg = data["choices"][0]["message"]
    messages.append({"role": "assistant", "content": msg["content"],
                     **({"tool_calls": msg["tool_calls"]}
                        if msg.get("tool_calls") else {})})
    if msg.get("tool_calls"):
        for tc in msg["tool_calls"]:
            print("tool call:", tc["function"]["name"], tc["function"]["arguments"])
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                            "name": tc["function"]["name"],
                            "content": tool_results[tc["id"]]})
    else:
        print("final:", msg["content"])
        break

print("\nDone. Open the dashboard with:  dashcam")
