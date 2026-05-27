from src.infrastructure.rate_limiter import RateLimiter


def test_check_returns_true_before_limit() -> None:
    rl = RateLimiter()
    rl.configure("test", max_requests=3, window_seconds=60)
    assert rl.check(1, "test") is True
    assert rl.check(1, "test") is True
    assert rl.check(1, "test") is True


def test_check_returns_false_after_limit() -> None:
    rl = RateLimiter()
    rl.configure("test", max_requests=2, window_seconds=60)
    assert rl.check(1, "test") is True
    assert rl.check(1, "test") is True
    assert rl.check(1, "test") is False


def test_get_remaining() -> None:
    rl = RateLimiter()
    rl.configure("test", max_requests=3, window_seconds=60)
    assert rl.get_remaining(1, "test") == 3
    rl.check(1, "test")
    assert rl.get_remaining(1, "test") == 2
    rl.check(1, "test")
    assert rl.get_remaining(1, "test") == 1
    rl.check(1, "test")
    assert rl.get_remaining(1, "test") == 0


def test_unknown_action_allowed() -> None:
    rl = RateLimiter()
    assert rl.check(1, "unknown") is True
    assert rl.get_remaining(1, "unknown") == 999


def test_different_users_independent() -> None:
    rl = RateLimiter()
    rl.configure("test", max_requests=1, window_seconds=60)
    assert rl.check(1, "test") is True
    assert rl.check(2, "test") is True
    assert rl.check(1, "test") is False
    assert rl.check(2, "test") is False
