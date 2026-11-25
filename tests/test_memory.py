"""Milestone 6 tests: the SQLite library. No network or model needed."""

from paper_agent.memory import Library

PAPER = {
    "id": "1706.03762", "title": "Attention Is All You Need", "authors": ["Ashish Vaswani"],
    "published": "2017-06-12", "summary": "The dominant sequence transduction models ...",
    "url": "https://arxiv.org/abs/1706.03762",
}


def test_store_and_search_by_topic_and_title():
    lib = Library(":memory:")
    lib.add_papers([PAPER], topic="transformers")
    assert lib.search("attention")[0]["id"] == "1706.03762"
    assert lib.search("transformers")[0]["id"] == "1706.03762"  # matched via its topic
    assert lib.search("protein folding") == []


def test_notes_are_saved_and_returned():
    lib = Library(":memory:")
    lib.add_papers([PAPER])
    assert lib.save_note("1706.03762", "Introduced the Transformer.")["saved"]
    assert lib.search("attention")[0]["notes"] == ["Introduced the Transformer."]
    assert "error" in lib.save_note("9999.99999", "nope")


def test_library_survives_restart(tmp_path):
    path = str(tmp_path / "lib.db")
    Library(path).add_papers([PAPER])
    assert Library(path).count() == 1  # a brand-new connection still sees it
