# Research Paper Assistant

A command-line agent that takes a topic, searches arXiv, reads abstracts and
writes a short literature summary with **real, verified citations**. It is
built by hand, one milestone at a time, to learn how agents work underneath
the frameworks.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then pick a provider in .env
```

Default provider: [Ollama](https://ollama.com) running `qwen2.5:7b` locally
(`ollama pull qwen2.5:7b`). No key needed.

Check the model works:

```powershell
python -m paper_agent.llm
```

## How it is built (milestone by milestone)

Each milestone is one git commit, so `git log` walks you through the build.

| # | Milestone | What it adds | Key file |
|---|-----------|--------------|----------|
| 0 | Talk to a model | One OpenAI-compatible client for any provider | `paper_agent/llm.py` |
| 1 | arXiv tool, no LLM | `search_arxiv` and `get_paper` as plain functions, 3 s rate limit, pytest tests | `paper_agent/tools/arxiv.py` |
| 2 | One tool call, by hand | The raw tool-calling protocol: schema in, `tool_calls` out, `role: tool` result back | `paper_agent/one_call.py` |
| 3 | The agent loop | Model -> tools -> results -> model, until an answer or `max_steps`; tool registry; trace output; minimum-search guard | `paper_agent/agent.py`, `paper_agent/tools/registry.py` |
