"""Milestone 4 tests: the citation checker. No network or model needed."""

from paper_agent.citations import build_references, check_citations, extract_ids, remove_citations

SEEN = {
    "1706.03762": {
        "id": "1706.03762", "title": "Attention Is All You Need",
        "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar", "Jakob Uszkoreit"],
        "published": "2017-06-12", "summary": "...", "url": "https://arxiv.org/abs/1706.03762",
    }
}


def test_extract_ids_dedupes_and_drops_version():
    text = "Transformers [arXiv:1706.03762v5] changed NLP [arXiv:1706.03762]. Old: [arXiv:hep-th/9901001]"
    assert extract_ids(text) == ["1706.03762", "hep-th/9901001"]


def test_bare_id_without_prefix_is_found():
    assert extract_ids("RAG [2506.06962] works.") == ["2506.06962"]


def test_fake_id_is_detected():
    text = "Real [arXiv:1706.03762] and invented [arXiv:2399.99999]."
    valid, invalid = check_citations(text, SEEN)
    assert valid == ["1706.03762"]
    assert invalid == ["2399.99999"]


def test_fake_id_is_removed():
    text = "Real [arXiv:1706.03762] and invented [arXiv:2399.99999]."
    assert remove_citations(text, ["2399.99999"]) == "Real [arXiv:1706.03762] and invented."


def test_references_come_from_seen_papers():
    refs = build_references(["1706.03762"], SEEN)
    assert "Attention Is All You Need" in refs
    assert "et al." in refs
    assert "https://arxiv.org/abs/1706.03762" in refs
