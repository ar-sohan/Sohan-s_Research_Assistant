"""The tool registry and dispatcher.

Milestone 3: TOOLS maps a tool name (what the model says) to
    (python_function, argument_model, json_schema)
so running whatever the model asks for is one dictionary lookup.

Milestone 5: `Dispatcher` makes tool calls safe. The rule is simple:
**a tool call never raises.** Every failure becomes a result like
{"error": "..."} that goes back to the model, which can often recover by
itself (fix its arguments, try another query). A stack trace helps nobody.
"""

import json

from pydantic import BaseModel, Field, ValidationError

from paper_agent.tools.arxiv import get_paper, search_arxiv

# Abstracts are long. Search results are truncated to keep the conversation
# (the model's context) small; get_paper returns the full abstract on demand.
SEARCH_SUMMARY_CHARS = 800


# --- Argument models (Milestone 5) -------------------------------------------
# pydantic checks types and limits, and produces readable error messages
# that we hand back to the model when its arguments are wrong.

class SearchArgs(BaseModel):
    query: str = Field(min_length=2, description="Search keywords")
    max_results: int = Field(default=5, ge=1, le=10, description="Number of papers, 1-10")


class GetPaperArgs(BaseModel):
    arxiv_id: str = Field(description="The arXiv id, e.g. '1706.03762'")


def _search_truncated(query: str, max_results: int = 5) -> list[dict]:
    papers = search_arxiv(query, max_results)
    for p in papers:
        if len(p["summary"]) > SEARCH_SUMMARY_CHARS:
            p["summary"] = p["summary"][:SEARCH_SUMMARY_CHARS] + "... (use get_paper for the full abstract)"
    return papers


def _get_paper_or_error(arxiv_id: str):
    return get_paper(arxiv_id) or {"error": f"No arXiv paper with id {arxiv_id!r}."}


def _schema(name: str, description: str, args_model: type[BaseModel]) -> dict:
    """Build the JSON schema the model sees from the pydantic model.

    One source of truth: the same class validates the arguments AND describes them.
    """
    params = args_model.model_json_schema()
    params.pop("title", None)
    for prop in params.get("properties", {}).values():
        prop.pop("title", None)
    return {"type": "function", "function": {"name": name, "description": description, "parameters": params}}


TOOLS = {
    "search_arxiv": (
        _search_truncated,
        SearchArgs,
        _schema(
            "search_arxiv",
            "Search arXiv for papers on a topic. Returns id, title, authors, date "
            "and a shortened abstract for each paper. Call it several times with "
            "different short queries to cover a topic well.",
            SearchArgs,
        ),
    ),
    "get_paper": (
        _get_paper_or_error,
        GetPaperArgs,
        _schema("get_paper", "Fetch one paper's full details and full abstract by its arXiv id.", GetPaperArgs),
    ),
}


def tool_schemas() -> list[dict]:
    """The list we pass as `tools=` on every model call."""
    return [schema for _, _, schema in TOOLS.values()]


class Dispatcher:
    """Runs tool calls for ONE agent run, safely.

    Keeps a cache of earlier calls so a model that repeats the same search
    (a common loop) gets the earlier result back instead of another API hit.
    """

    def __init__(self):
        self.cache: dict[tuple, object] = {}
        self.duplicates = 0

    def __call__(self, name: str, arguments_json: str):
        # 1. Unknown tool name: tell the model what exists.
        if name not in TOOLS:
            return {"error": f"Unknown tool {name!r}. Valid tools: {sorted(TOOLS)}"}
        func, args_model, _ = TOOLS[name]

        # 2. Broken JSON in the arguments.
        try:
            raw = json.loads(arguments_json or "{}")
        except json.JSONDecodeError as e:
            return {"error": f"Arguments were not valid JSON ({e}). Send a JSON object."}

        # 3. Wrong field names or types.
        try:
            args = args_model.model_validate(raw)
        except ValidationError as e:
            return {"error": f"Invalid arguments for {name}: {e.errors(include_url=False)}"}

        # 4. Duplicate call: same tool, same arguments as before in this run.
        key = (name, json.dumps(args.model_dump(), sort_keys=True).lower())
        if key in self.cache:
            self.duplicates += 1
            return {"note": "You already made this exact call. Here are the earlier results; "
                            "try a different query instead.",
                    "results": self.cache[key]}

        # 5. The tool itself failing (network down, arXiv 503, ...).
        try:
            result = func(**args.model_dump())
        except Exception as e:  # noqa: BLE001 - deliberately catch everything here
            return {"error": f"{name} failed: {type(e).__name__}: {e}"}

        self.cache[key] = result
        return result


def dispatch(name: str, arguments_json: str):
    """One-off convenience wrapper (no duplicate detection across calls)."""
    return Dispatcher()(name, arguments_json)
