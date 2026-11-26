"""Tests for the website's usage limits. Skipped if gradio is not installed."""

import pytest

pytest.importorskip("gradio")

from app import UsageLimiter  # noqa: E402


def test_per_user_limit():
    lim = UsageLimiter(per_user_per_hour=2, per_day=100)
    assert lim.try_acquire("1.2.3.4") is None
    assert lim.try_acquire("1.2.3.4") is None
    assert "this hour" in lim.try_acquire("1.2.3.4")
    assert lim.try_acquire("5.6.7.8") is None  # another visitor is not affected


def test_daily_cap_for_whole_site():
    lim = UsageLimiter(per_user_per_hour=10, per_day=2)
    lim.try_acquire("a")
    lim.try_acquire("b")
    assert "daily limit" in lim.try_acquire("c")
