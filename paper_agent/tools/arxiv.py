"""Milestone 1: arXiv search tools, with no LLM involved.

The arXiv API (http://export.arxiv.org/api/query) is free and needs no key.
It returns an Atom XML feed; feedparser turns that into Python objects.

arXiv asks clients to wait at least 3 seconds between requests, so every
request goes through `_get()`, which enforces that gap.
"""

import re
import time

import feedparser
import httpx

# The guide says http://, but arXiv now answers that with a 301 redirect to
# https://, and httpx does not follow redirects by default. Use https directly.
ARXIV_URL = "https://export.arxiv.org/api/query"
MIN_GAP_SECONDS = 3.0

# Module-level timestamp of our last request. Because it lives at module level,
# it is shared by every call in this process.
_last_request_at = 0.0


def _get(params: dict) -> str:
    """GET the arXiv API politely: never two requests less than 3 s apart."""
    global _last_request_at
    wait = MIN_GAP_SECONDS - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    resp = httpx.get(ARXIV_URL, params=params, timeout=30)
    _last_request_at = time.monotonic()
    resp.raise_for_status()
    return resp.text


def _clean(text: str) -> str:
    """arXiv titles and abstracts contain hard line breaks; collapse all whitespace."""
    return re.sub(r"\s+", " ", text).strip()


def _short_id(entry_id: str) -> str:
    """'http://arxiv.org/abs/1706.03762v7' -> '1706.03762'.

    We drop the version suffix (v7) so the same paper always has the same id.
    """
    tail = entry_id.rsplit("/abs/", 1)[-1]
    return re.sub(r"v\d+$", "", tail)


def _to_paper(entry) -> dict:
    """Turn one feedparser entry into the plain dict our agent works with."""
    paper_id = _short_id(entry.id)
    return {
        "id": paper_id,
        "title": _clean(entry.title),
        "authors": [a.name for a in entry.get("authors", [])],
        "published": entry.get("published", "")[:10],  # keep just YYYY-MM-DD
        "summary": _clean(entry.summary),               # the abstract
        "url": f"https://arxiv.org/abs/{paper_id}",
    }


def search_arxiv(query: str, max_results: int = 5) -> list[dict]:
    """Search arXiv and return up to `max_results` papers, most relevant first."""
    xml = _get({
        "search_query": f"all:{query}",
        "max_results": max_results,
        "sortBy": "relevance",
    })
    feed = feedparser.parse(xml)
    return [_to_paper(e) for e in feed.entries]


def get_paper(arxiv_id: str) -> dict | None:
    """Fetch one paper by its arXiv id (e.g. '1706.03762'). Returns None if not found."""
    xml = _get({"id_list": arxiv_id})
    entries = feedparser.parse(xml).entries
    # For an unknown id arXiv returns either no entry or an entry with no title.
    if not entries or not entries[0].get("title"):
        return None
    return _to_paper(entries[0])


if __name__ == "__main__":
    # Quick manual check:  python -m paper_agent.tools.arxiv
    for p in search_arxiv("graph neural networks"):
        print(p["id"], "|", p["published"], "|", p["title"])
