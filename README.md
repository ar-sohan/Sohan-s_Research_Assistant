# Research Paper Assistant

A command-line agent that takes a topic, searches arXiv, reads abstracts and
writes a short literature summary with **real, verified citations**. It is
built by hand, one milestone at a time, to learn how agents work underneath
the frameworks.

## Quick start (about 10 minutes)

1. Install [Ollama](https://ollama.com) and pull a model (about 4.7 GB):
   ```powershell
   ollama pull qwen2.5:7b
   ```
2. Clone and install:
   ```powershell
   git clone https://github.com/ar-sohan/Sohan-s_Research_Assistant.git
   cd Sohan-s_Research_Assistant
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e .
   copy .env.example .env
   ```
3. Run it:
   ```powershell
   paper-agent "chain of thought prompting" --papers 5
   ```
   The summary prints in the terminal and is saved to `reports/<date>_<topic>.md`.

No GPU or API key needed. On a laptop with 8 GB RAM one summary takes 1 to 5
minutes. For speed, use `--model qwen2.5:3b` or a free hosted model (Groq,
Gemini): just change the three lines in `.env`.

### Other ways to run it

```powershell
paper-agent --chat                          # chat mode: ask follow-ups like "compare the first two papers"
paper-agent "topic" --out my_report.md      # choose where the report goes
python -m paper_agent.llm                   # check the model connection
python -m evals.run --model qwen2.5:7b      # run the eval suite
pytest                                      # unit tests (citation checker, dispatcher, library, arXiv)
```

## Example output

See [`examples/chain-of-thought.md`](examples/chain-of-thought.md). Every
reference is built in code from papers the agent actually retrieved, so each
`https://arxiv.org/abs/<id>` link is real.

## How it works

```
 you: "topic"
     |
     v
 +-----------+   messages + tool schemas   +-----------------+
 |   Agent   | --------------------------> |  LLM (Ollama)   |
 |   loop    | <-------------------------- |  qwen2.5:7b     |
 +-----------+   text answer OR tool_calls +-----------------+
     |  ^
     |  | results as {"role": "tool"} messages
     v  |
 +-----------------------------------------------+
 | Dispatcher: validate args, catch errors,      |
 | dedupe calls                                  |
 |   search_library  -> SQLite (data/library.db) |
 |   search_arxiv    -> arXiv API (3 s apart)    |
 |   get_paper       -> arXiv API                |
 |   save_note       -> SQLite                   |
 +-----------------------------------------------+
     |
     v
 final answer -> citation checker -> references built from seen_papers
```

An agent is an LLM in a loop. Each pass the model either asks for tools or
answers. Our code runs the tools and feeds results back. The code, not the
prompt, enforces the important rules: a minimum number of searches, checking
the library before arXiv, removing citations to papers never retrieved, and
a `max_steps` limit so the loop always ends.

### Project layout

```
paper_agent/
  config.py       settings from .env (base_url, key, model)
  llm.py          the only file that talks to the model
  tools/arxiv.py  arXiv search + fetch (no LLM code)
  tools/registry.py  tool schemas, argument validation, safe dispatcher
  agent.py        the agent loop and system prompt
  citations.py    citation extraction, checking, reference list
  memory.py       SQLite library of papers and notes
  chat.py         interactive chat (short-term memory)
  cli.py          the paper-agent command
  one_call.py     Milestone 2 teaching script: one tool call by hand
evals/            test topics and the eval runner
tests/            pytest tests
NOTES.md          learning log: what surprised me, what broke
```

## How it is built (milestone by milestone)

Each milestone is one git commit, so `git log` walks you through the build.

| # | Milestone | What it adds | Key file |
|---|-----------|--------------|----------|
| 0 | Talk to a model | One OpenAI-compatible client for any provider | `paper_agent/llm.py` |
| 1 | arXiv tool, no LLM | `search_arxiv` and `get_paper` as plain functions, 3 s rate limit, pytest tests | `paper_agent/tools/arxiv.py` |
| 2 | One tool call, by hand | The raw tool-calling protocol: schema in, `tool_calls` out, `role: tool` result back | `paper_agent/one_call.py` |
| 3 | The agent loop | Model -> tools -> results -> model, until an answer or `max_steps`; tool registry; trace output; minimum-search guard | `paper_agent/agent.py`, `paper_agent/tools/registry.py` |
| 4 | Grounded citations | `seen_papers` ground truth, regex check of cited ids, one fix-up round, reference list built in code | `paper_agent/citations.py` |
| 5 | Robustness | Tool calls never raise: unknown tool, bad JSON, pydantic validation, duplicate-call cache, abstract truncation, arXiv retry with backoff, clear error when the model is unreachable | `paper_agent/tools/registry.py` |
| 6 | Memory | `Agent` class keeps `messages` between questions (chat REPL), history compaction, SQLite library of papers and notes, `search_library` and `save_note` tools, library-first rule | `paper_agent/memory.py`, `paper_agent/chat.py` |
| 7 | Evals | 12 test topics, automatic checks (citation validity, must-find recall, steps, arXiv calls, time), LLM-as-judge for faithfulness and coverage, CSV + table | `evals/run.py`, `evals/topics.jsonl` |
| 8 | Polish | `paper-agent` CLI, Markdown reports with date, model and queries, installable package, this README | `paper_agent/cli.py`, `pyproject.toml` |

## Eval results

12 topics from `evals/topics.jsonl`, each run with a fresh empty library.
Judge: qwen2.5:7b scoring 1-5. Run on a laptop CPU/GTX 1650, 2026-11-26.

| Metric | qwen2.5:7b | qwen2.5:3b |
|--------|-----------:|-----------:|
| Runs finished | 12/12 | 12/12 |
| Citation validity (cited ids really retrieved) | **1.00** | 0.91 |
| Recall of landmark papers | 0.11 | 0.11 |
| Faithfulness (judge, 1-5) | 3.83 | 4.55 |
| Coverage (judge, 1-5) | 3.17 | 3.82 |
| Papers cited per summary | 5.25 | 3.42 |
| arXiv calls per run | 2.33 | 1.08 |
| Seconds per run | 245 | **48** |
| Honest "nothing relevant" on a nonsense topic | yes | no |

What the numbers say:

- **7b is the safer model:** it never cited a paper it had not retrieved and
  admitted when a topic had no papers. 3b invented some ids (removed by the
  citation checker) and wrote a summary for "quantum basket weaving".
- **3b is 5x faster**, and the judge scored it higher, but it cites fewer
  papers, so there is less to get wrong. Judges are wrong too: spot-check by hand.
- **Recall is the weak spot:** arXiv's relevance search rarely puts the famous
  paper (e.g. *Attention Is All You Need*) in the top results. A stopword bug
  (fixed in Milestone 8) also made some searches return nothing.

These results were recorded before the Milestone 8 stopword fix and prompt
change. Re-run `python -m evals.run` to see their effect: that is exactly the
"change one thing, re-run, compare" habit evals are for.

## Next steps (stretch goals from the guide)

- Turn the tools into an MCP server (`pip install mcp`, FastMCP).
- Rebuild the loop in LangGraph and compare.
- Add the Semantic Scholar API for citation counts.
