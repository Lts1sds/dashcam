import time

from . import cost

TOOLS = [
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the web for information",
        "parameters": {"type": "object",
                       "properties": {"query": {"type": "string"}},
                       "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a file from disk",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"}},
                       "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "calculator",
        "description": "Evaluate a math expression",
        "parameters": {"type": "object",
                       "properties": {"expr": {"type": "string"}},
                       "required": ["expr"]}}},
]

SYSTEM = ("You are a research assistant. Use the provided tools to answer "
          "questions. Cite sources when possible.")


def _assistant(content="", tool_calls=None):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
        msg["content"] = None
    return msg


def _tool(call_id, name, result):
    return {"role": "tool", "tool_call_id": call_id, "name": name,
            "content": result}


def _tc(call_id, name, args):
    return {"id": call_id, "type": "function",
            "function": {"name": name, "arguments": args}}


def _span(store, tid, idx, model, started, messages, tools, content,
          tool_calls, pt, ct, error=None, dur=1.4):
    request = {"model": model, "messages": messages}
    if tools:
        request["tools"] = tools
    response = None
    if error is None:
        message = {"role": "assistant", "content": content}
        if tool_calls:
            message["tool_calls"] = tool_calls
            message["content"] = None
        response = {
            "id": f"chatcmpl-demo{tid[:4]}{idx}",
            "object": "chat.completion",
            "model": model,
            "choices": [{"index": 0,
                         "finish_reason": "tool_calls" if tool_calls else "stop",
                         "message": message}],
            "usage": {"prompt_tokens": pt, "completion_tokens": ct},
        }
    c, _ = cost.estimate(model, pt, ct)
    store.record_span(tid, idx, "openai", "chat", model, started,
                      started + dur, request, response, error, pt, ct, c)


def _research(store, now):
    model = "gpt-4o-mini"
    t = now - 1560.0
    tid = store.start_trace("Q3 revenue highlights and summary", t)

    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Find Acme Corp's Q3 2026 revenue highlights and write a two-paragraph summary."},
    ]
    tc1 = [_tc("call_001", "web_search",
               '{"query": "Acme Corp Q3 2026 revenue results"}')]
    _span(store, tid, 0, model, t, msgs, TOOLS, None, tc1, 142, 28, dur=1.9)

    msgs = msgs + [
        _assistant(None, tc1),
        _tool("call_001", "web_search",
              "Acme Corp Q3 2026: revenue $412M (+18% YoY), cloud segment "
              "$158M (+34%), net income $61M. Source: acme-ir.com/press/q3-2026"),
    ]
    tc2 = [_tc("call_002", "read_file",
               '{"path": "data/finance/q3_segment_breakdown.csv"}')]
    _span(store, tid, 1, model, t + 3.1, msgs, TOOLS, None, tc2, 396, 25, dur=1.2)

    msgs = msgs + [
        _assistant(None, tc2),
        _tool("call_002", "read_file",
              "segment,revenue_musd,growth\ncloud,158,34%\nenterprise,121,9%\n"
              "consumer,97,4%\nother,36,12%"),
    ]
    tc3 = [_tc("call_003", "calculator",
               '{"expr": "158 + 121 + 97 + 36"}')]
    _span(store, tid, 2, model, t + 6.8, msgs, TOOLS, None, tc3, 512, 22, dur=0.9)

    msgs = msgs + [
        _assistant(None, tc3),
        _tool("call_003", "calculator", "412"),
    ]
    final = ("Acme Corp delivered a strong Q3 2026 with total revenue of "
             "$412M, up 18% year-over-year. The cloud segment was the "
             "standout performer at $158M (+34% YoY), now representing 38% "
             "of total revenue.\n\nEnterprise software contributed $121M "
             "(+9%), consumer products $97M (+4%), and other segments $36M. "
             "Net income reached $61M. The segment breakdown confirms the "
             "company's strategic shift toward cloud infrastructure is "
             "driving overall growth.")
    _span(store, tid, 3, model, t + 9.7, msgs, TOOLS, final, None, 641, 148, dur=2.8)
    store.end_trace(tid, "ok")


def _failure(store, now):
    model = "claude-sonnet-4"
    t = now - 480.0
    tid = store.start_trace("Customer support: refund request #8841", t)

    msgs = [
        {"role": "system", "content": "You are a support agent. Look up orders and issue refunds per policy."},
        {"role": "user", "content": "Customer says order #8841 never arrived and wants a refund."},
    ]
    tc1 = [{"id": "toolu_01A", "type": "function",
            "function": {"name": "lookup_order",
                         "arguments": '{"order_id": "8841"}'}}]
    _span(store, tid, 0, model, t, msgs, None, None, tc1, 118, 21, dur=2.2)

    msgs = msgs + [
        _assistant(None, tc1),
        _tool("toolu_01A", "lookup_order",
              '{"status": "delivered", "signed_by": "front desk", "delivered_at": "2026-09-20T14:03:11Z"}'),
    ]
    _span(store, tid, 1, model, t + 5.0, msgs, None, None, None, 0, 0,
          error="anthropic.RateLimitError: Error code: 429 - "
                "{\"type\": \"error\", \"error\": {\"type\": \"rate_limit_error\", "
                "\"message\": \"Number of request tokens has exceeded your "
                "per-minute rate limit\"}}", dur=0.4)


def _simple(store, now):
    model = "gpt-4o"
    t = now - 120.0
    tid = store.start_trace("Summarize meeting notes", t)
    msgs = [
        {"role": "user", "content": "Summarize in one sentence: 'Sync covered Q4 "
                                     "roadmap: ship MCP integration by Oct 15, "
                                     "defer SSO to Q1, hiring 2 backend engineers.'"},
    ]
    _span(store, tid, 0, model, t, msgs, None,
          "The team agreed to ship MCP integration by October 15, defer SSO to Q1, and hire two backend engineers for Q4.",
          None, 58, 27, dur=1.6)
    store.end_trace(tid, "ok")


def run(store):
    now = time.time()
    _research(store, now)
    _failure(store, now)
    _simple(store, now)
    return 3
