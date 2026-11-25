"""Milestone 6: long-term memory, a local library of papers and notes.

Short-term memory is just the `messages` list (see agent.py). It vanishes
when the program exits. Long-term memory has to live on disk, so we use
SQLite: a whole database in one file, built into Python (`import sqlite3`).

Tables:
    papers       one row per arXiv paper ever fetched
    paper_topics which topics a paper came up for (many-to-many)
    notes        takeaways saved by the agent or by you
"""

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = os.getenv("LIBRARY_PATH", "data/library.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    authors TEXT NOT NULL,       -- JSON list of names
    published TEXT,
    summary TEXT,
    url TEXT
);
CREATE TABLE IF NOT EXISTS paper_topics (
    paper_id TEXT REFERENCES papers(id),
    topic TEXT,
    PRIMARY KEY (paper_id, topic)
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT REFERENCES papers(id),
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class Library:
    def __init__(self, path: str = DEFAULT_PATH):
        if path != ":memory:":  # ":memory:" = a throwaway in-RAM database, used by tests
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row  # rows behave like dicts: row["title"]
        self.db.executescript(SCHEMA)

    def add_papers(self, papers: list[dict], topic: str = "") -> None:
        """Store papers. INSERT OR REPLACE keeps the newest copy if we see one again.

        We never store a truncated abstract over a full one: a search result
        (shortened) only fills in a paper we do not already have.
        """
        for p in papers:
            truncated = p["summary"].endswith("(use get_paper for the full abstract)")
            verb = "INSERT OR IGNORE" if truncated else "INSERT OR REPLACE"
            self.db.execute(
                f"{verb} INTO papers (id, title, authors, published, summary, url) VALUES (?, ?, ?, ?, ?, ?)",
                (p["id"], p["title"], json.dumps(p["authors"]), p["published"], p["summary"], p["url"]),
            )
            if topic:
                self.db.execute("INSERT OR IGNORE INTO paper_topics VALUES (?, ?)", (p["id"], topic.lower()))
        self.db.commit()

    def search(self, query: str, limit: int = 8) -> list[dict]:
        """Keyword search: papers whose title, abstract or topics contain EVERY word.

        Each word becomes `... LIKE ?` and the conditions are joined with AND.
        The ? placeholders let sqlite3 insert values safely (no SQL injection).
        """
        words = [w for w in re.split(r"\W+", query.lower()) if len(w) > 2]
        if not words:
            return []
        haystack = "lower(p.title || ' ' || p.summary || ' ' || coalesce(t.topics, ''))"
        where = " AND ".join(f"{haystack} LIKE ?" for _ in words)
        rows = self.db.execute(
            f"""SELECT p.* FROM papers p
                LEFT JOIN (SELECT paper_id, group_concat(topic, ' ') AS topics
                           FROM paper_topics GROUP BY paper_id) t ON t.paper_id = p.id
                WHERE {where} LIMIT ?""",
            [f"%{w}%" for w in words] + [limit],
        ).fetchall()
        return [self._row_to_paper(r) for r in rows]

    def save_note(self, paper_id: str, note: str) -> dict:
        if not self.db.execute("SELECT 1 FROM papers WHERE id = ?", (paper_id,)).fetchone():
            return {"error": f"Paper {paper_id} is not in the library. Fetch it first."}
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.db.execute("INSERT INTO notes (paper_id, note, created_at) VALUES (?, ?, ?)", (paper_id, note, now))
        self.db.commit()
        return {"saved": True, "paper_id": paper_id}

    def notes_for(self, paper_id: str) -> list[str]:
        rows = self.db.execute("SELECT note FROM notes WHERE paper_id = ? ORDER BY id", (paper_id,))
        return [r["note"] for r in rows]

    def count(self) -> int:
        return self.db.execute("SELECT count(*) FROM papers").fetchone()[0]

    def _row_to_paper(self, row) -> dict:
        paper = {k: row[k] for k in ("id", "title", "published", "summary", "url")}
        paper["authors"] = json.loads(row["authors"])
        paper["notes"] = self.notes_for(row["id"])
        return paper


# One shared library per process, created the first time it is needed.
_library: Library | None = None


def get_library() -> Library:
    global _library
    if _library is None:
        _library = Library()
    return _library


def set_library(lib: Library) -> None:
    """Swap the library (tests use an in-memory one; evals use a fresh one per run)."""
    global _library
    _library = lib
