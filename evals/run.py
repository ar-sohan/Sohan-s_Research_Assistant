"""Milestone 7: evals. Measure quality with numbers, not vibes.

For every topic in evals/topics.jsonl we run a FRESH agent (with an empty,
in-memory library, so runs do not help each other) and record:

Automatic checks (cheap, exact):
    finished        the run ended without crashing
    citation_valid  share of cited ids that were really retrieved (Milestone 4)
    recall          share of the topic's "must find" landmark papers that were cited
    steps           model calls in the loop (cost and speed)
    tool_calls, arxiv_calls, seconds

LLM-as-judge (fuzzy): a second model call reads the abstracts of the cited
papers and the summary, and scores 1-5 for
    faithfulness    no claim goes beyond the abstracts
    coverage        the summary covers the main ideas of the papers
Judges are wrong too: spot-check a few scores by hand.

Results: one CSV row per run in evals/results/, plus a table of averages.

Run:
    python -m evals.run --model qwen2.5:7b
    python -m evals.run --model qwen2.5:3b --limit 4
    python -m evals.run --model qwen2.5:7b --judge-model qwen2.5:7b --no-judge
"""

import argparse
import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from paper_agent import config
from paper_agent.agent import Agent
from paper_agent.llm import chat
from paper_agent.memory import Library, set_library

console = Console()
EVALS_DIR = Path(__file__).parent
RESULTS_DIR = EVALS_DIR / "results"

JUDGE_PROMPT = """You are grading a literature summary written by an AI research assistant.

TOPIC: {topic}

ABSTRACTS OF THE PAPERS IT CITED:
{abstracts}

SUMMARY TO GRADE:
{summary}

Score two things from 1 (bad) to 5 (excellent):
- faithfulness: every claim in the summary is supported by the abstracts above. Deduct for any
  claim, number or detail that is not in the abstracts, or that mixes up two papers.
- coverage: the summary explains the main ideas of the cited papers and how they relate to the topic.

Answer with JSON only, like: {{"faithfulness": 4, "coverage": 3, "reason": "one short sentence"}}"""


def load_topics(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def judge(topic: str, summary: str, papers: list[dict], judge_model: str) -> dict:
    """Ask a model to grade the summary. Returns {} if it gives unusable output."""
    if not papers:
        return {}
    abstracts = "\n\n".join(f"[arXiv:{p['id']}] {p['title']}\n{p['summary']}" for p in papers)
    prompt = JUDGE_PROMPT.format(topic=topic, abstracts=abstracts, summary=summary)
    text = chat([{"role": "user", "content": prompt}], model=judge_model).content or ""
    # Small models often wrap JSON in ```json fences or add words; grab the {...} part.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        scores = json.loads(match.group(0)) if match else {}
        return {"faithfulness": int(scores["faithfulness"]), "coverage": int(scores["coverage"]),
                "judge_reason": str(scores.get("reason", ""))[:200]}
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return {"judge_reason": f"unparseable judge output: {text[:100]!r}"}


def run_one(item: dict, judge_model: str | None) -> dict:
    topic = item["topic"]
    set_library(Library(":memory:"))  # fresh, empty library: every run starts equal
    agent = Agent(verbose=False)
    row = {"topic": topic, "finished": False}
    start = time.monotonic()
    try:
        summary = agent.ask(f"Write a literature summary on: {topic}", topic=topic)
        row["finished"] = True
    except Exception as e:  # noqa: BLE001 - an eval records failures, it does not stop on them
        summary = ""
        row["error"] = f"{type(e).__name__}: {e}"[:200]
    row["seconds"] = round(time.monotonic() - start, 1)

    s = agent.stats
    cited = s.get("cited_ids", [])
    total_cites = s.get("valid_citations", 0) + s.get("invalid_citations", 0)
    must = item.get("must_find", [])
    row.update(
        steps=s.get("steps", 0),
        tool_calls=s.get("tool_calls", 0),
        arxiv_calls=s.get("arxiv_calls", 0),
        citations=len(cited),
        citation_valid=round(s.get("valid_citations", 0) / total_cites, 2) if total_cites else "",
        recall=round(sum(m in agent.seen_papers and m in cited for m in must) / len(must), 2) if must else "",
    )
    if item.get("expect_nothing"):
        # For a nonsense topic, "good" means admitting it found nothing.
        row["honest_empty"] = "nothing relevant" in summary.lower()
    if judge_model and row["finished"]:
        row.update(judge(topic, summary, [agent.seen_papers[i] for i in cited], judge_model))
    row["summary"] = summary.replace("\n", " ")[:1500]
    return row


def averages(rows: list[dict], key: str) -> str:
    vals = [r[key] for r in rows if isinstance(r.get(key), (int, float)) and not isinstance(r.get(key), bool)]
    return f"{sum(vals) / len(vals):.2f}" if vals else "-"


def print_table(rows: list[dict], model: str) -> None:
    cols = ["steps", "arxiv_calls", "citations", "citation_valid", "recall", "faithfulness", "coverage", "seconds"]
    table = Table(title=f"Eval results: {model}")
    table.add_column("topic", max_width=34)
    for c in cols:
        table.add_column(c, justify="right")
    for r in rows:
        table.add_row(r["topic"] if r["finished"] else f"[red]{r['topic']} (failed)[/red]",
                      *[str(r.get(c, "")) for c in cols])
    table.add_section()
    table.add_row("[bold]average[/bold]", *[averages(rows, c) for c in cols])
    console.print(table)
    done = sum(r["finished"] for r in rows)
    console.print(f"finished: {done}/{len(rows)}")
    for r in rows:
        if "honest_empty" in r:
            console.print(f"honest 'nothing relevant' on '{r['topic']}': {r['honest_empty']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the research agent on test topics and score it.")
    ap.add_argument("--model", default=config.LLM_MODEL, help="model under test")
    ap.add_argument("--judge-model", default=None, help="model used as judge (default: same as --model)")
    ap.add_argument("--no-judge", action="store_true", help="skip the LLM judge (faster)")
    ap.add_argument("--limit", type=int, default=None, help="only run the first N topics")
    ap.add_argument("--topics", default=str(EVALS_DIR / "topics.jsonl"))
    ap.add_argument("--tag", default="", help="label for this run, e.g. 'prompt-v2'")
    args = ap.parse_args()

    # chat() reads config.LLM_MODEL at call time, so this switches the whole agent.
    config.LLM_MODEL = args.model
    judge_model = None if args.no_judge else (args.judge_model or args.model)

    items = load_topics(Path(args.topics))[: args.limit]
    rows = []
    for n, item in enumerate(items, 1):
        console.print(f"[dim]{n}/{len(items)}[/dim] {item['topic']} ...", highlight=False)
        row = run_one(item, judge_model)
        row.update(model=args.model, judge_model=judge_model or "", tag=args.tag)
        rows.append(row)

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    safe_model = re.sub(r"[^\w.-]", "_", args.model)
    out = RESULTS_DIR / f"{stamp}_{safe_model}{'_' + args.tag if args.tag else ''}.csv"
    fields = sorted({k for r in rows for k in r}, key=lambda k: (k != "topic", k == "summary", k))
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print_table(rows, args.model)
    console.print(f"saved {out}")


if __name__ == "__main__":
    main()
