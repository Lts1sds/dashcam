import json
import os

PRICES = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4.1": (2.00, 8.00),
    "o4-mini": (1.10, 4.40),
    "o3-mini": (1.10, 4.40),
    "o3": (2.00, 8.00),
    "claude-opus-4": (15.00, 75.00),
    "claude-sonnet-4": (3.00, 15.00),
    "claude-3-7-sonnet": (3.00, 15.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-opus": (15.00, 75.00),
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.30, 2.50),
    "qwen-max": (1.60, 6.40),
    "qwen-plus": (0.40, 1.20),
    "qwen-turbo": (0.05, 0.20),
}

_cache = None


def _prices():
    global _cache
    if _cache is None:
        table = dict(PRICES)
        path = os.environ.get("DASHCAM_PRICES")
        if path:
            try:
                with open(path, encoding="utf-8") as f:
                    extra = json.load(f)
                for k, v in extra.items():
                    if isinstance(v, (list, tuple)) and len(v) == 2:
                        table[k] = (float(v[0]), float(v[1]))
            except (OSError, ValueError):
                pass
        _cache = table
    return _cache


def estimate(model, prompt_tokens, completion_tokens):
    if not model or not (prompt_tokens or completion_tokens):
        return 0.0, False
    name = model.lower()
    for key in sorted(_prices(), key=len, reverse=True):
        if key in name:
            pin, pout = _prices()[key]
            cost = (prompt_tokens * pin + completion_tokens * pout) / 1e6
            return round(cost, 6), True
    return 0.0, False
