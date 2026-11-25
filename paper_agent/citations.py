"""Milestone 4: grounded citations.

LLMs happily invent plausible arXiv ids. So we never trust the model's
citations. Instead:

  1. The agent keeps `seen_papers` (id -> paper dict), filled from every
     tool result. That is the ground truth of what was really retrieved.
  2. After the model answers, a regex pulls every [arXiv:XXXX] it cited.
  3. Any cited id NOT in seen_papers is a hallucination.
  4. The reference list is built here, in Python, from seen_papers. The model
     never types a title or an author name in the references.
"""

import re

# Matches [arXiv:1706.03762], old-style ids like [arXiv:hep-th/9901001], and
# a bare [1706.03762] (small models often drop the "arXiv:" prefix).
# The capture group is the id itself. A version suffix (v2) is dropped.
ID_PATTERN = r"[a-z\-]+(?:\.[A-Z]{2})?/\d{7}|\d{4}\.\d{4,5}"
CITE_RE = re.compile(rf"\[(?:arXiv:\s*)?({ID_PATTERN})(?:v\d+)?\]", re.IGNORECASE)


def extract_ids(text: str) -> list[str]:
    """Every cited arXiv id, in order of first appearance, without duplicates."""
    seen: dict[str, None] = {}  # a dict keeps insertion order, like an ordered set
    for match in CITE_RE.finditer(text or ""):
        seen.setdefault(match.group(1), None)
    return list(seen)


def check_citations(text: str, seen_papers: dict) -> tuple[list[str], list[str]]:
    """Split cited ids into (valid, invalid). Invalid = never retrieved by a tool."""
    cited = extract_ids(text)
    valid = [i for i in cited if i in seen_papers]
    invalid = [i for i in cited if i not in seen_papers]
    return valid, invalid


def remove_citations(text: str, bad_ids: list[str]) -> str:
    """Strip citations to ids we could not verify (last-resort clean-up)."""
    for bad in bad_ids:
        text = re.sub(rf"\s*\[(?:arXiv:\s*)?{re.escape(bad)}(?:v\d+)?\]", "", text, flags=re.IGNORECASE)
    return text


def build_references(ids: list[str], seen_papers: dict) -> str:
    """A Markdown reference list built only from retrieved data."""
    lines = ["## References", ""]
    for n, pid in enumerate(ids, 1):
        p = seen_papers[pid]
        authors = ", ".join(p["authors"][:3]) + (" et al." if len(p["authors"]) > 3 else "")
        year = p["published"][:4]
        lines.append(f"{n}. {authors} ({year}). *{p['title']}*. [arXiv:{pid}]({p['url']})")
    return "\n".join(lines)
