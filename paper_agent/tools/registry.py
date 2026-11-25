"""Milestone 3: the tool registry and dispatcher.

TOOLS maps a tool name (what the model says) to:
    (python_function, json_schema)

So running whatever the model asks for is one dictionary lookup, and the
list of schemas we send to the model is built from the same place. Adding a
tool = writing a function + adding one entry here.
"""

import json

from paper_agent.tools.arxiv import get_paper, search_arxiv


def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    """Small helper so each schema below is short and readable."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


TOOLS = {
    "search_arxiv": (
        search_arxiv,
        _schema(
            "search_arxiv",
            "Search arXiv for papers on a topic. Returns id, title, authors, date "
            "and abstract for each paper. Call it several times with different "
            "queries to cover a topic well.",
            {
                "query": {"type": "string", "description": "Search keywords"},
                "max_results": {"type": "integer", "description": "Number of papers, 1-10 (default 5)"},
            },
            ["query"],
        ),
    ),
    "get_paper": (
        get_paper,
        _schema(
            "get_paper",
            "Fetch one paper's full details by its arXiv id, e.g. '1706.03762'.",
            {"arxiv_id": {"type": "string", "description": "The arXiv id"}},
            ["arxiv_id"],
        ),
    ),
}


def tool_schemas() -> list[dict]:
    """The list we pass as `tools=` on every model call."""
    return [schema for _, schema in TOOLS.values()]


def dispatch(name: str, arguments_json: str):
    """Run the tool the model asked for and return its (JSON-friendly) result."""
    func, _ = TOOLS[name]
    args = json.loads(arguments_json)
    return func(**args)
