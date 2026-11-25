"""Milestone 5 tests: the dispatcher never raises. No network or model needed.

`monkeypatch` swaps a real function for a fake one during a single test, so we
can simulate arXiv being down without unplugging anything.
"""

import httpx

from paper_agent.tools import registry
from paper_agent.tools.registry import Dispatcher


def test_unknown_tool_lists_valid_names():
    result = Dispatcher()("search_google", "{}")
    assert "Unknown tool" in result["error"] and "search_arxiv" in result["error"]


def test_broken_json_is_reported():
    result = Dispatcher()("search_arxiv", '{"query": "gnn"')
    assert "not valid JSON" in result["error"]


def test_wrong_field_name_is_reported():
    result = Dispatcher()("search_arxiv", '{"q": "gnn"}')
    assert "Invalid arguments" in result["error"]


def test_network_failure_becomes_error_result(monkeypatch):
    def offline(*args, **kwargs):
        raise httpx.ConnectError("network is unreachable")

    monkeypatch.setitem(registry.TOOLS, "search_arxiv", (offline, *registry.TOOLS["search_arxiv"][1:]))
    result = Dispatcher()("search_arxiv", '{"query": "graph neural networks"}')
    assert "ConnectError" in result["error"]


def test_duplicate_call_returns_cached_results(monkeypatch):
    calls = []

    def fake_search(query, max_results=5):
        calls.append(query)
        return [{"id": "1706.03762"}]

    monkeypatch.setitem(registry.TOOLS, "search_arxiv", (fake_search, *registry.TOOLS["search_arxiv"][1:]))
    d = Dispatcher()
    d("search_arxiv", '{"query": "transformers"}')
    second = d("search_arxiv", '{"query": "Transformers", "max_results": 5}')
    assert len(calls) == 1               # arXiv was only hit once
    assert "already made" in second["note"]
    assert d.duplicates == 1
