"""Milestone 2: one tool call, by hand. No loop yet.

This file shows the raw "tool calling" protocol step by step:

  1. We send the user's message PLUS a list of tool schemas (`tools=[...]`).
  2. If the model wants a tool, its reply has `tool_calls` instead of text.
     Each call has an id, a function name and arguments as a JSON *string*.
  3. We run the Python function ourselves and append two messages:
       - the assistant message that contains the tool call
       - a {"role": "tool", "tool_call_id": ..., "content": <result JSON>}
  4. We call the model again; now it can answer in text using the results.

The model never runs code. It only *asks*; our program decides and runs.

Try:
    python -m paper_agent.one_call "find papers on diffusion models for audio"
    python -m paper_agent.one_call "what is 2 + 2"
"""

import json
import sys

from rich import print as rprint

from paper_agent.llm import chat
from paper_agent.tools.arxiv import search_arxiv

# The JSON schema that describes search_arxiv to the model.
# The description is a prompt: it tells the model WHEN to use the tool.
# Experiment: change it to "does stuff" and see how behaviour changes.
SEARCH_ARXIV_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_arxiv",
        "description": (
            "Search arXiv for academic papers. Use this whenever the user asks "
            "about research papers or the scientific literature on a topic."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords, e.g. 'diffusion models audio'"},
                "max_results": {"type": "integer", "description": "How many papers (1-10)", "default": 5},
            },
            "required": ["query"],
        },
    },
}


def run(question: str) -> str:
    messages = [{"role": "user", "content": question}]

    # Step 1: first model call, with the tool available.
    reply = chat(messages, tools=[SEARCH_ARXIV_SCHEMA])

    if not reply.tool_calls:
        # The model chose not to use the tool (e.g. "what is 2 + 2").
        print("(no tool call)")
        return reply.content

    # Step 3a: keep the assistant's tool-call message in the history.
    # model_dump(exclude_none=True) turns the SDK object into a plain dict.
    messages.append(reply.model_dump(exclude_none=True))

    # Step 3b: run every requested call and append its result.
    for call in reply.tool_calls:
        args = json.loads(call.function.arguments)  # arguments arrive as a JSON string
        rprint(f"[cyan]tool call[/cyan] {call.function.name}({args})")
        papers = search_arxiv(**args)
        messages.append({
            "role": "tool",
            "tool_call_id": call.id,  # links this result to the request above
            "content": json.dumps(papers),
        })

    # Step 4: second model call. The model now sees the results.
    final = chat(messages, tools=[SEARCH_ARXIV_SCHEMA])

    # Print the full conversation once, so every entry can be explained.
    rprint("\n[bold]Full messages list:[/bold]")
    for m in messages:
        role = m["role"]
        body = m.get("content") or m.get("tool_calls")
        rprint(f"  [yellow]{role:9}[/yellow] {str(body)[:150]}")
    return final.content


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "find papers on diffusion models for audio"
    print("\nAnswer:\n" + run(q))
