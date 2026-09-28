from dashcam import cost


def test_known_model():
    c, matched = cost.estimate("gpt-4o-mini-2024-07-18", 1000, 1000)
    assert matched
    assert abs(c - (1000 * 0.15 + 1000 * 0.60) / 1e6) < 1e-9


def test_longer_key_wins():
    c1, m1 = cost.estimate("gpt-4o", 1_000_000, 0)
    c2, m2 = cost.estimate("gpt-4o-mini", 1_000_000, 0)
    assert m1 and m2
    assert c1 > c2


def test_anthropic_naming():
    c, matched = cost.estimate("claude-sonnet-4-20250514", 1_000_000, 1_000_000)
    assert matched
    assert abs(c - (3.0 + 15.0)) < 1e-6


def test_unknown_model():
    c, matched = cost.estimate("totally-unknown-model", 1000, 1000)
    assert not matched
    assert c == 0.0


def test_empty():
    assert cost.estimate("", 100, 100) == (0.0, False)
    assert cost.estimate("gpt-4o", 0, 0) == (0.0, False)
