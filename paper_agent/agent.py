"""The agent loop (Milestone 3), with citations (4), robustness (5) and memory (6).

An agent is an LLM in a loop:

    while not done:
        reply = model(messages, tools)
        if reply has tool calls:
            run each tool, append the results to messages, go round again
        else:
            reply is the final answer, stop

`max_steps` guarantees the loop always ends. Each pass is one model call,
so the step count is a direct measure of cost and speed.

Milestone 6 turned the loop into an `Agent` class so the `messages` list
(short-term memory) survives between questions; see paper_agent/chat.py.

Run:
    python -m paper_agent.agent "retrieval augmented generation"
"""

import json
import sys

from openai import APIConnectionError
from rich.console import Console

from paper_agent import config
from paper_agent.citations import build_references, check_citations, remove_citations
from paper_agent.llm import chat
from paper_agent.memory import get_library
from paper_agent.tools.registry import Dispatcher, tool_schemas

console = Console()

MIN_SEARCHES = 2  # search calls (arXiv or library) required before a first answer
MAX_HISTORY_CHARS = 24_000  # Milestone 6: above this, old tool results are dropped
SEARCH_TOOLS = {"search_arxiv", "search_library"}

SYSTEM_PROMPT = """You are a research assistant that writes short literature summaries.

How to work:
1. Call search_library FIRST: it holds papers you fetched in earlier sessions.
2. Then call search_arxiv 1 to 3 times with DIFFERENT short queries (2-4 keywords each:
   synonyms, sub-topics, key methods). If the library already had 5+ relevant papers,
   one arXiv search is enough.
3. Pick the 5 to 8 most relevant papers from what the searches returned.
4. Write a summary of about 250 words: the main ideas, how the papers relate, open questions.

Rules:
- Cite ONLY papers that your tool calls returned. Never cite from memory.
- Cite inline in exactly this form: [arXiv:1706.03762]
- Keep the user's topic as it is. Do not swap it for a nearby topic that has more papers.
- Before writing, check each paper against the ORIGINAL topic. Search engines always return
  something; a paper that only shares a word with the topic is not relevant.
- If no paper is really about the topic, answer only: "I found nothing relevant on arXiv
  for this topic." and explain in one sentence what the searches returned instead.
- If a tool returns an error, read it, fix your arguments or try another query.
- For follow-up questions, reuse the papers already in this conversation; search only if needed.
"""


def _trace_step(step: int, name: str, args: str, result) -> None:
    """Print one line per tool call so you can see what the agent did."""
    if isinstance(result, dict) and "error" in result:
        outcome = f"[red]error: {result['error'][:120]}[/red]"
    elif isinstance(result, dict) and "note" in result:
        kind = "skipped" if result["note"].startswith("Skipped") else "duplicate call, returned cached results"
        outcome = f"[yellow]{kind}[/yellow]"
    else:
        outcome = f"{len(result) if isinstance(result, list) else 1} result(s)"
    console.print(f"[dim]step {step}[/dim] [cyan]{name}[/cyan]({args}) -> {outcome}", highlight=False)


def _papers_in(result) -> list[dict]:
    """Pull the paper dicts out of any tool result (list, single paper, cached duplicate)."""
    if isinstance(result, dict) and "results" in result:  # a cached duplicate
        result = result["results"]
    papers = result if isinstance(result, list) else [result]
    return [p for p in papers if isinstance(p, dict) and "id" in p and "title" in p]


class Agent:
    """One conversation with the research assistant.

    Short-term memory = self.messages, kept between calls to ask().
    Long-term memory  = the SQLite library (paper_agent/memory.py).
    """

    def __init__(self, max_steps: int = 8, verbose: bool = True):
        self.max_steps = max_steps
        self.verbose = verbose
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.seen_papers: dict[str, dict] = {}  # Milestone 4: ground truth for citations
        self.dispatch = Dispatcher()            # Milestone 5: safe calls + duplicate cache
        self.stats: dict = {}                   # Milestone 7: numbers about the last ask()

    def _log(self, text: str) -> None:
        if self.verbose:
            console.print(text, highlight=False)

    def _compact_history(self, turn_start: int) -> None:
        """Milestone 6: when history is long, blank out tool results from EARLIER turns.

        The final answers stay, so follow-ups still have context; the papers are
        still in seen_papers and the library, so citations keep working.
        """
        if len(json.dumps(self.messages)) <= MAX_HISTORY_CHARS:
            return
        for m in self.messages[:turn_start]:
            if m["role"] == "tool":
                m["content"] = '{"note": "old tool result removed to save space"}'
        self._log("[dim]history compacted: old tool results removed[/dim]")

    def ask(self, question: str, min_searches: int = MIN_SEARCHES, topic: str = "") -> str:
        turn_start = len(self.messages)
        self.messages.append({"role": "user", "content": question})
        self._compact_history(turn_start)

        searches = 0
        asked_to_fix = False
        self.stats = {"steps": 0, "tool_calls": 0, "arxiv_calls": 0, "library_hits": 0,
                      "duplicates_before": self.dispatch.duplicates}

        for step in range(1, self.max_steps + 1):
            self.stats["steps"] = step
            reply = chat(self.messages, tools=tool_schemas())
            self.messages.append(reply.model_dump(exclude_none=True))

            if not reply.tool_calls:
                # Small local models often stop after one search despite the prompt.
                # A prompt is a request; code is a guarantee.
                if searches < min_searches and step < self.max_steps:
                    self._log("[yellow]answered after too few searches, asking for another[/yellow]")
                    # Drop the premature answer so the next one is fresh, not a continuation.
                    self.messages.pop()
                    self.messages.append({"role": "user", "content": (
                        "Before writing, call search_arxiv again with a different query "
                        "(a synonym, sub-topic or key method) to cover the topic better."
                    )})
                    continue

                # Milestone 4: check citations before accepting the answer.
                valid, invalid = check_citations(reply.content, self.seen_papers)
                if (invalid or not valid) and self.seen_papers and not asked_to_fix and step < self.max_steps:
                    asked_to_fix = True
                    problem = (f"You cited {invalid}, which you never retrieved." if invalid
                               else "You did not cite any papers.")
                    self._log(f"[yellow]citation problem, asking for a fix: {problem}[/yellow]")
                    self.messages.append({"role": "user", "content": (
                        f"{problem} Rewrite the answer citing only papers your tools returned, "
                        "inline in exactly this form: [arXiv:<id>]. If nothing relevant was found, say so."
                    )})
                    continue

                self._log(f"[green]done in {step} model call(s), {searches} search(es), "
                          f"{len(self.seen_papers)} paper(s) seen[/green]")
                return self._finalize(reply.content)

            # Models can request SEVERAL tools in one reply ("parallel tool calls").
            # qwen asks for search_library AND three arXiv searches at once, before it
            # has seen what the library holds, so the library saves nothing.
            # Rule enforced in code: when the library is in the batch, run it alone
            # first and send the others back as "skipped, decide again".
            # If the library comes back empty, there is nothing to decide, so the
            # other calls run as normal.
            calls = sorted(reply.tool_calls, key=lambda c: c.function.name != "search_library")
            library_first = calls[0].function.name == "search_library" and len(calls) > 1

            for call in calls:
                name = call.function.name
                if library_first and name != "search_library" and self.stats["library_hits"] > 0:
                    result = {"note": "Skipped. Read the search_library results first, then call "
                                      "search_arxiv only for what the library is missing."}
                    self._trace(step, name, call.function.arguments, result)
                    self.messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
                    continue
                searches += name in SEARCH_TOOLS
                self.stats["tool_calls"] += 1
                result = self.dispatch(name, call.function.arguments)
                papers = _papers_in(result)
                is_cached = isinstance(result, dict) and "note" in result
                if name in ("search_arxiv", "get_paper") and not is_cached:
                    self.stats["arxiv_calls"] += 1
                    get_library().add_papers(papers, topic or question)  # Milestone 6: remember
                if name == "search_library":
                    self.stats["library_hits"] += len(papers)
                for p in papers:
                    self.seen_papers[p["id"]] = p
                self._trace(step, name, call.function.arguments, result)
                self.messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})

        # Out of steps: ask once more, WITHOUT tools, so the model must write the answer.
        self._log(f"[yellow]max_steps ({self.max_steps}) reached, forcing a final answer[/yellow]")
        self.messages.append({"role": "user", "content": "Stop searching. Write the answer now from what you have."})
        reply = chat(self.messages)
        self.messages.append(reply.model_dump(exclude_none=True))
        return self._finalize(reply.content)

    def _trace(self, step: int, name: str, args: str, result) -> None:
        if self.verbose:
            _trace_step(step, name, args, result)

    def _finalize(self, text: str) -> str:
        """Milestone 4: drop unverified citations and append a reference list built in code."""
        valid, invalid = check_citations(text, self.seen_papers)
        self.stats.update(valid_citations=len(valid), invalid_citations=len(invalid), cited_ids=valid,
                          duplicates=self.dispatch.duplicates - self.stats.pop("duplicates_before", 0))
        if invalid:
            self._log(f"[red]removing unverified citations: {invalid}[/red]")
            text = remove_citations(text, invalid)
        if not valid:
            return text + "\n\n_(No verified citations.)_"
        return text + "\n\n" + build_references(valid, self.seen_papers)


def run_agent(topic: str, max_steps: int = 8) -> str:
    """One-shot use: a fresh Agent writes one literature summary."""
    return Agent(max_steps=max_steps).ask(f"Write a literature summary on: {topic}", topic=topic)


if __name__ == "__main__":
    topic = " ".join(sys.argv[1:]) or "retrieval augmented generation"
    try:
        answer = run_agent(topic)
    except APIConnectionError:
        # Milestone 5: the model server is unreachable (Ollama not running, no internet).
        console.print(f"[red]Cannot reach the model at {config.LLM_BASE_URL}. "
                      "Is Ollama running? Try: ollama serve[/red]")
        sys.exit(1)
    # markup=False: rich treats [square brackets] as style tags, which would
    # silently swallow our [arXiv:1234.5678] citations when printing.
    console.print(answer, markup=False)
