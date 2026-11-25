"""Milestone 3: the agent loop. This is the core of every agent.

An agent is an LLM in a loop:

    while not done:
        reply = model(messages, tools)
        if reply has tool calls:
            run each tool, append the results to messages, go round again
        else:
            reply is the final answer, stop

`max_steps` guarantees the loop always ends. Each pass is one model call,
so the step count is a direct measure of cost and speed.

Run:
    python -m paper_agent.agent "retrieval augmented generation"
"""

import json
import sys

from rich.console import Console

from paper_agent.llm import chat
from paper_agent.tools.registry import dispatch, tool_schemas

console = Console()

MIN_SEARCHES = 2  # the agent must search at least this many times before answering

SYSTEM_PROMPT = """You are a research assistant that writes short literature summaries.

How to work:
1. Call search_arxiv 2 to 4 times with DIFFERENT short queries (2-4 keywords each:
   synonyms, sub-topics, key methods). Do not write the summary after only one search.
2. Pick the 5 to 8 most relevant papers from what the searches returned.
3. Write a summary of about 250 words: the main ideas, how the papers relate, open questions.

Rules:
- Cite ONLY papers that your tool calls returned. Never cite from memory.
- Cite inline in exactly this form: [arXiv:1706.03762]
- If the searches found nothing relevant, say so honestly instead of inventing papers.
"""


def _trace_step(step: int, name: str, args: dict, result) -> None:
    """Print one line per tool call so you can see what the agent did."""
    size = len(result) if isinstance(result, list) else (1 if result else 0)
    console.print(f"[dim]step {step}[/dim] [cyan]{name}[/cyan]({args}) -> {size} result(s)")


def run_agent(topic: str, max_steps: int = 8) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Write a literature summary on: {topic}"},
    ]

    searches = 0  # how many times search_arxiv has run

    for step in range(1, max_steps + 1):
        reply = chat(messages, tools=tool_schemas())
        messages.append(reply.model_dump(exclude_none=True))

        if not reply.tool_calls:
            # Small local models often stop after one search despite the prompt.
            # A prompt is a request; code is a guarantee. If it answered too
            # early, push back once and let the loop continue.
            if searches < MIN_SEARCHES and step < max_steps:
                console.print("[yellow]answered after too few searches, asking for another[/yellow]")
                # Drop the premature answer. If we kept it, the model would later
                # write "additional insights" that continue it instead of a fresh summary.
                messages.pop()
                messages.append({"role": "user", "content": (
                    "Before writing, call search_arxiv again with a different query "
                    "(a synonym, sub-topic or key method) to cover the topic better."
                )})
                continue
            console.print(f"[green]done in {step} model call(s), {searches} search(es)[/green]")
            return reply.content

        for call in reply.tool_calls:
            if call.function.name == "search_arxiv":
                searches += 1
            result = dispatch(call.function.name, call.function.arguments)
            _trace_step(step, call.function.name, json.loads(call.function.arguments), result)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})

    # Out of steps: ask once more, WITHOUT tools, so the model must write the answer.
    console.print(f"[yellow]max_steps ({max_steps}) reached, forcing a final answer[/yellow]")
    messages.append({"role": "user", "content": "Stop searching. Write the summary now from what you have."})
    return chat(messages).content


if __name__ == "__main__":
    topic = " ".join(sys.argv[1:]) or "retrieval augmented generation"
    console.print(run_agent(topic))
