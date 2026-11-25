"""Milestone 1 tests. These hit the real arXiv API, so they need internet.

Run with:  pytest tests/test_arxiv.py -v
"""

from paper_agent.tools.arxiv import get_paper, search_arxiv

FIELDS = {"id", "title", "authors", "published", "summary", "url"}


def test_search_returns_clean_dicts():
    papers = search_arxiv("graph neural networks", max_results=5)
    assert len(papers) == 5
    for p in papers:
        assert set(p) == FIELDS
        assert "\n" not in p["title"] and "\n" not in p["summary"]
        assert p["url"] == f"https://arxiv.org/abs/{p['id']}"


def test_get_paper_attention():
    paper = get_paper("1706.03762")
    assert paper is not None
    assert paper["title"] == "Attention Is All You Need"
