"""Milestone 6: a chat REPL (Read-Eval-Print Loop) with short-term memory.

The trick is tiny: we keep ONE Agent object alive between questions, so its
`messages` list keeps growing. The model sees the whole conversation every
time, which is all "memory" means to an LLM.

Try:
    python -m paper_agent.chat
    > diffusion models for audio
    > now compare the first two papers
    > focus on the 2024 ones

Commands: /library (count papers stored), /quit
"""

from openai import APIConnectionError
from rich.console import Console

from paper_agent import config
from paper_agent.agent import Agent
from paper_agent.memory import get_library

console = Console()


def main() -> None:
    agent = Agent()
    console.print(f"[bold]Research assistant[/bold] ({config.LLM_MODEL}). "
                  f"Library: {get_library().count()} papers. Type /quit to exit.\n")
    first = True
    while True:
        try:
            question = console.input("[bold cyan]> [/bold cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question:
            continue
        if question in ("/quit", "/exit"):
            break
        if question == "/library":
            console.print(f"{get_library().count()} papers in the library")
            continue

        # The first question is a topic: require real searching.
        # Follow-ups ("compare the first two") may answer from what we already have.
        prompt = f"Write a literature summary on: {question}" if first else question
        try:
            answer = agent.ask(prompt, min_searches=2 if first else 0, topic=question if first else "")
        except APIConnectionError:
            console.print(f"[red]Cannot reach the model at {config.LLM_BASE_URL}. Is Ollama running?[/red]")
            continue
        first = False
        console.print(answer, markup=False)
        console.print()


if __name__ == "__main__":
    main()
