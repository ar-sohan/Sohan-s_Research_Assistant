# How to use the Research Paper Assistant

A step-by-step guide for Windows. No programming needed after setup.

What the agent does: you give it a research topic, it searches arXiv several
times, reads the abstracts, and writes a ~250-word literature summary with
citations. Every reference is a real paper it actually retrieved, with a
working `https://arxiv.org/abs/...` link.

What it does NOT do: it reads abstracts only (not full papers), it searches
only arXiv (not IEEE, ACL Anthology, Google Scholar), and a small local model
can still misdescribe a paper. Treat its output as a **map of where to read**,
not as the final word.

---

## 1. Every time you start working

### Step 1: Make sure Ollama is running
Ollama starts automatically with Windows and sits in the system tray (bottom
right, a small llama icon). If you don't see it, open the Start menu, type
**Ollama** and open it. Nothing visible happens; it just runs in the background.

To check, open PowerShell and run:
```powershell
ollama list
```
You should see `qwen2.5:7b` (and `qwen2.5:3b`). If you get "could not connect",
Ollama is not running: start it from the Start menu.

### Step 2: Open PowerShell in the project folder
In File Explorer, go to `C:\1.All_Projects\Research_Assistant`, click the
address bar, type `powershell` and press Enter. Or, in any PowerShell window:
```powershell
cd C:\1.All_Projects\Research_Assistant
```

### Step 3 (optional): Activate the virtual environment
```powershell
.\.venv\Scripts\Activate.ps1
```
After this you can type `paper-agent` instead of `.\.venv\Scripts\paper-agent`.
If Windows says "running scripts is disabled", skip this step and use the long
form `.\.venv\Scripts\paper-agent` in every command below. Both work the same.

---

## 2. Get a literature summary (the main command)

```powershell
.\.venv\Scripts\paper-agent "your topic here"
```

Example:
```powershell
.\.venv\Scripts\paper-agent "low-resource machine translation" --papers 6
```

What you will see:
1. A trace of what the agent does, one line per tool call:
   `step 1 search_arxiv({"query":"low-resource translation"}) -> 5 result(s)`
2. A `done in N model call(s)` line.
3. The summary, then a **References** list.
4. `Report saved to reports\2026-11-26_low-resource-machine-translation.md`

It takes **1 to 5 minutes** with qwen2.5:7b on your laptop. Don't close the
window while it works.

### All options

| Option | What it does | When to use it |
|--------|--------------|----------------|
| `"topic"` | The research topic, in quotes | Always (unless `--chat`) |
| `--papers 8` | How many papers to cite (default 6) | More for a broad review, fewer for a quick look |
| `--out file.md` | Where to save the report | To keep reports in your own folder, e.g. `--out C:\Research\mt\review1.md` |
| `--model qwen2.5:3b` | Use a different model for this run | When you want speed over accuracy (see section 5) |
| `--max-steps 12` | Max model calls before it must answer (default 8) | Broad topics where it runs out of steps |
| `--quiet` | Hide the step-by-step trace | When you only want the summary |
| `--chat` | Interactive mode with follow-up questions | Exploring a topic (section 3) |
| `--help` | Show all options | When you forget |

### Where things are saved
- **Reports:** `reports\<date>_<topic>.md` (or the `--out` path). Open in
  VS Code, Notepad, or any Markdown viewer. Each report records the date,
  model, the exact search queries used, and the references.
- **Your paper library:** `data\library.db`. Every paper the agent has ever
  fetched is stored here, so later runs on related topics are faster and need
  fewer arXiv calls. Delete the `data` folder to start fresh.

Both folders are in `.gitignore`, so your personal research never goes to GitHub.

---

## 3. Chat mode: explore a topic with follow-up questions

```powershell
.\.venv\Scripts\paper-agent --chat
```

You get a `>` prompt. The **first** thing you type is treated as a topic and
gets a full literature summary. Everything after that is a follow-up that can
use the earlier answer:

```
> Bangla sentiment analysis
  ... summary with references ...
> compare the first two papers you cited
> which of these used transformer models?
> focus on the papers from 2023 or later
> find papers on datasets for this
> /library        (shows how many papers are stored)
> /quit           (exit)
```

Tips:
- Follow-ups are fast because they reuse papers already found.
- To start a **new** topic, `/quit` and start chat again, so the conversation
  doesn't mix two topics.
- Very long chats get compacted (old search results are dropped), which keeps
  it working but makes it forget details from early on.

---

## 4. Writing good topics

The agent turns your topic into short arXiv keyword searches. arXiv matches
words, not meaning, so:

| Do | Don't |
|----|-------|
| `"Bangla named entity recognition"` | `"what are the best methods people use for NER in my language?"` |
| Use the field's standard terms: `"code-mixed sentiment analysis"` | Use your own invented phrase for the idea |
| Try synonyms in separate runs: `"Bangla"` and `"Bengali"` | Assume one spelling covers everything |
| 2 to 6 words | A whole paragraph |
| `"speech recognition low-resource languages"` | `"ASR"` alone (acronyms are ambiguous) |

**Bangla tip:** arXiv papers use "Bengali" more often than "Bangla". Run both.

If the agent answers "I found nothing relevant", the topic may be too narrow
or use unusual words. Broaden it (`"Bangla OCR"` -> `"Bengali text recognition"`)
or split it in two.

---

## 5. Which model to use

| | qwen2.5:7b (default) | qwen2.5:3b |
|---|---|---|
| Time per summary | ~4 minutes | under 1 minute |
| Fake citations | none in our tests | some (the checker removes them) |
| Admits "nothing found" honestly | yes | not reliably |
| Use it for | anything you will rely on | quick brainstorming, testing topic wording |

A good habit: try 2-3 topic wordings with `--model qwen2.5:3b --quiet` to find
the one that gives good papers, then run the best wording with the default 7b.

Want better quality and speed? A free hosted model works too: get a free key
from console.groq.com or aistudio.google.com, then edit `.env` (see the
commented blocks in `.env.example`). Never share or commit that key.

---

## 6. Practical workflows

### A. Starting a literature review (e.g. for a Bangla NLP research idea)
1. **Brainstorm wordings fast** (3b):
   ```powershell
   .\.venv\Scripts\paper-agent "Bengali sentiment analysis" --model qwen2.5:3b --quiet
   .\.venv\Scripts\paper-agent "Bangla sentiment analysis" --model qwen2.5:3b --quiet
   .\.venv\Scripts\paper-agent "code-mixed Bangla English" --model qwen2.5:3b --quiet
   ```
2. **Run the 2-3 best wordings properly** (7b), saving to one folder:
   ```powershell
   .\.venv\Scripts\paper-agent "Bengali sentiment analysis" --papers 8 --out C:\Research\bangla-sa\01-overview.md
   .\.venv\Scripts\paper-agent "Bengali sentiment datasets" --papers 6 --out C:\Research\bangla-sa\02-datasets.md
   .\.venv\Scripts\paper-agent "multilingual transformers low-resource sentiment" --papers 6 --out C:\Research\bangla-sa\03-methods.md
   ```
3. **Read the actual papers.** Open each reference link, read the abstract on
   arXiv, and download the PDF of the ones that matter. Check every sentence
   in the summary that you plan to reuse.
4. **Dig deeper in chat mode** on the most promising sub-topic:
   ```powershell
   .\.venv\Scripts\paper-agent --chat
   ```
   Ask: "which of these papers released a dataset?", "what are the open
   problems they mention?", "compare their evaluation metrics".
5. **Write your related-work section yourself** using the reports as an
   outline. Never paste the agent's text into a paper: it is based on
   abstracts only and may be inaccurate.

### B. Checking whether your idea is already done
```powershell
.\.venv\Scripts\paper-agent "your exact idea in 4-6 words" --papers 8
```
Then in chat mode ask: "Does any of these papers do exactly X?" If several
papers are close, look at what they did NOT do: that gap is your contribution.

### C. Keeping up with a topic
Re-run the same topic every few weeks. The library remembers what it has
seen, and the arXiv search will surface new papers. Compare the reports by date.

### D. Quick question about one known paper
In chat mode: `find the paper with arXiv id 1706.03762 and explain its main idea`.
The agent uses `get_paper` to fetch it with the full abstract.

---

## 7. Troubleshooting

| What you see | What to do |
|--------------|------------|
| `Cannot reach the model at http://localhost:11434/v1` | Ollama is not running. Start it from the Start menu, wait 10 seconds, retry. |
| `'paper-agent' is not recognized` | Use the long form `.\.venv\Scripts\paper-agent`, and make sure you are in `C:\1.All_Projects\Research_Assistant`. |
| `running scripts is disabled on this system` | Skip `Activate.ps1` and use `.\.venv\Scripts\paper-agent`. |
| Very slow (over 10 minutes) | Close other heavy apps (browser tabs, games); your laptop has 8 GB RAM. Or use `--model qwen2.5:3b`. |
| `I found nothing relevant on arXiv` but you know papers exist | Reword with standard terms or synonyms (section 4). Try "Bengali" for "Bangla". |
| Off-topic papers in the summary | Make the topic more specific, or add the key method name. |
| `max_steps reached, forcing a final answer` | Add `--max-steps 12`. |
| `error: search_arxiv failed: ...ConnectError` | No internet, or arXiv is down. Check your connection and retry in a minute. |
| Unicode or strange characters in the output | Run `$env:PYTHONIOENCODING="utf-8"` once in that PowerShell window. |
| Disk getting full | `ollama rm qwen2.5:3b` frees 1.9 GB. Old reports in `reports\` can be deleted. |

---

## 8. Updating and other commands

```powershell
git pull                                   # get the latest code from GitHub
.\.venv\Scripts\python -m pytest           # check everything still works (needs internet)
.\.venv\Scripts\python -m evals.run --model qwen2.5:3b --limit 4   # quick quality check
.\.venv\Scripts\python -m paper_agent.llm  # test the model connection only
```

To learn how it works inside, read `README.md` (architecture), then
`NOTES.md` (what broke at each step), then the code starting with
`paper_agent/agent.py`.
