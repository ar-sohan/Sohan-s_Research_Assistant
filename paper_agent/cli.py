"""Milestone 8: a proper command-line interface.

After `pip install -e .` you get a `paper-agent` command:

    paper-agent "retrieval augmented generation"
    paper-agent "graph neural networks for molecules" --papers 8 --out reports/gnn.md
    paper-agent --chat                      # interactive mode (Milestone 6 REPL)
    paper-agent "topic" --model qwen2.5:3b  # override the model for one run

Without installing, `python -m paper_agent.cli ...` does the same.

Every report is saved as Markdown with the date, the model, the search
queries the agent used and the reference list.
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

from openai import APIConnectionError
from rich.console import Console

from paper_agent import config

console = Console()


def slugify(text: str) -> str:
    """'Graph Neural Networks!' -> 'graph-neural-networks' (safe as a file name)."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "report"


def build_report(topic: str, answer: str, queries: list[str], stats: dict) -> str:
    """Wrap the agent's answer (which already ends with References) in a Markdown report."""
    lines = [
        f"# Literature summary: {topic}",
        "",
        f"- **Date:** {datetime.now():%Y-%m-%d %H:%M}",
        f"- **Model:** {config.LLM_MODEL}",
        f"- **Model calls:** {stats.get('steps', '?')}, **arXiv calls:** {stats.get('arxiv_calls', '?')}",
        "- **Search queries used:**",
        *[f"  - `{q}`" for q in queries],
        "",
        answer,
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="paper-agent", description="Research paper assistant: arXiv literature summaries with verified citations.")
    ap.add_argument("topic", nargs="?", help="the research topic to summarise")
    ap.add_argument("--papers", type=int, default=6, help="how many papers to cite (default 6)")
    ap.add_argument("--out", help="where to save the Markdown report (default reports/<date>_<topic>.md)")
    ap.add_argument("--model", help="model name, overrides LLM_MODEL from .env")
    ap.add_argument("--max-steps", type=int, default=8, help="safety limit on model calls")
    ap.add_argument("--quiet", action="store_true", help="hide the step-by-step trace")
    ap.add_argument("--chat", action="store_true", help="start the interactive chat instead")
    args = ap.parse_args(argv)

    if args.model:
        config.LLM_MODEL = args.model  # read at call time by paper_agent.llm.chat

    # Imported here so --model above is set before anything else reads config.
    from paper_agent.agent import Agent
    from paper_agent.chat import main as chat_main

    if args.chat:
        chat_main()
        return 0
    if not args.topic:
        ap.error("give a topic, e.g. paper-agent \"diffusion models for audio\", or use --chat")

    agent = Agent(max_steps=args.max_steps, verbose=not args.quiet)
    question = (f"Write a literature summary on: {args.topic}. "
                f"Select and cite about {args.papers} of the most relevant papers.")
    try:
        answer = agent.ask(question, topic=args.topic)
    except APIConnectionError:
        console.print(f"[red]Cannot reach the model at {config.LLM_BASE_URL}. "
                      "Is Ollama running? Try: ollama serve[/red]")
        return 1

    report = build_report(args.topic, answer, agent.stats.get("queries", []), agent.stats)
    out = Path(args.out or f"reports/{datetime.now():%Y-%m-%d}_{slugify(args.topic)}.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")

    console.print(answer, markup=False)
    console.print(f"\n[green]Report saved to {out}[/green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
