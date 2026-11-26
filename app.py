"""The website: a Gradio web app around the same agent the CLI uses.

Run it on your own computer (uses Ollama from .env):
    pip install gradio
    python app.py            -> open http://127.0.0.1:7860

Host it for free on Hugging Face Spaces (uses the Groq free tier): see DEPLOY.md.

Because a public site shares ONE API key among everyone who opens it, the app
protects that key with:
  - a per-visitor limit   (WEB_MAX_PER_USER_PER_HOUR, default 5 summaries/hour)
  - a site-wide daily cap (WEB_MAX_PER_DAY, default 100 summaries/day)
  - an optional password  (APP_PASSWORD; if set, visitors must log in)
  - friendly messages when the provider's free quota runs out (HTTP 429)
The key itself is only read from an environment variable / Space secret.
"""

import os
import tempfile
import threading
import time
from collections import defaultdict, deque
from datetime import date

import gradio as gr
from openai import APIConnectionError, AuthenticationError, RateLimitError

from paper_agent import config
from paper_agent.agent import Agent
from paper_agent.cli import build_report, slugify

try:
    # Hugging Face "ZeroGPU" Spaces refuse to start unless the app declares at
    # least one @spaces.GPU function. Ours never needs a GPU (the model runs on
    # Groq), so this placeholder is never called; it only lets the Space start.
    # On a CPU Space or your own computer `spaces` is not installed: skip it.
    import spaces

    @spaces.GPU(duration=1)
    def _zero_gpu_placeholder():
        return None
except ImportError:
    pass

MAX_PER_USER_PER_HOUR = int(os.getenv("WEB_MAX_PER_USER_PER_HOUR", "5"))
MAX_PER_DAY = int(os.getenv("WEB_MAX_PER_DAY", "100"))
APP_PASSWORD = os.getenv("APP_PASSWORD", "")


class UsageLimiter:
    """Counts requests in memory. Resets when the app restarts, which is fine
    for a small free site; the provider's own limits are the final backstop."""

    def __init__(self, per_user_per_hour: int, per_day: int):
        self.per_user_per_hour = per_user_per_hour
        self.per_day = per_day
        self.user_times: dict[str, deque] = defaultdict(deque)  # visitor -> request timestamps
        self.day = date.today()
        self.day_count = 0
        self.lock = threading.Lock()  # several visitors can click at the same moment

    def try_acquire(self, user: str) -> str | None:
        """Record one request. Returns None if allowed, or a message saying why not."""
        with self.lock:
            now = time.time()
            if date.today() != self.day:  # a new day: reset the daily counter
                self.day, self.day_count = date.today(), 0
            if self.day_count >= self.per_day:
                return ("The site has reached its daily limit of free summaries. "
                        "Please come back tomorrow.")
            times = self.user_times[user]
            while times and now - times[0] > 3600:  # forget requests older than 1 hour
                times.popleft()
            if len(times) >= self.per_user_per_hour:
                wait_min = int((3600 - (now - times[0])) / 60) + 1
                return (f"You have used your {self.per_user_per_hour} summaries for this hour. "
                        f"Please try again in about {wait_min} minutes.")
            times.append(now)
            self.day_count += 1
            return None


limiter = UsageLimiter(MAX_PER_USER_PER_HOUR, MAX_PER_DAY)


def visitor_id(request: gr.Request | None) -> str:
    """Identify a visitor by IP address. Behind Hugging Face's proxy the real IP
    is the first entry of the X-Forwarded-For header."""
    if request is None:
        return "local"
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def friendly_error(e: Exception) -> str:
    if isinstance(e, RateLimitError):
        return ("The free AI quota shared by this site is used up for the moment. "
                "Please try again in a few minutes (or tomorrow if it says the daily limit).")
    if isinstance(e, AuthenticationError):
        return "The site's API key is missing or invalid. (Site owner: check the GROQ_API_KEY secret.)"
    if isinstance(e, APIConnectionError):
        return f"The AI model at {config.LLM_BASE_URL} cannot be reached right now. Please try again later."
    return f"Something went wrong: {type(e).__name__}. Please try again."


def _status(kind: str, text: str) -> str:
    """A small coloured status banner (styled by CSS below)."""
    return f'<div class="status status-{kind}">{text}</div>'


def _split_answer(answer: str) -> tuple[str, str]:
    """The agent's answer ends with '## References'; show the two parts in separate tabs."""
    head, sep, refs = answer.partition("## References")
    return head.strip(), (sep + refs).strip() if sep else "_No verified references._"


def research(topic: str, papers: int, request: gr.Request):
    """Gradio calls this when the button is pressed.

    It is a *generator*: each `yield` updates the page, so visitors see the
    agent's steps live instead of staring at a spinner for a minute.
    Yields (status_html, summary_md, references_md, trace_text, report_file).
    """
    topic = (topic or "").strip()
    if not 3 <= len(topic) <= 150:
        yield _status("warn", "Please enter a research topic of 3 to 150 characters."), "", "", "", None
        return
    refusal = limiter.try_acquire(visitor_id(request))
    if refusal:
        yield _status("warn", refusal), "", "", "", None
        return

    agent = Agent(max_steps=8, verbose=False)
    question = (f"Write a literature summary on: {topic}. "
                f"Select and cite about {int(papers)} of the most relevant papers.")
    box: dict = {}

    def work():
        try:
            box["answer"] = agent.ask(question, topic=topic)
        except Exception as e:  # noqa: BLE001 - shown to the visitor as a friendly message
            box["error"] = e

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    started = time.monotonic()
    while thread.is_alive():
        elapsed = int(time.monotonic() - started)
        steps = sum(line.startswith("step") for line in agent.trace)
        found = len(agent.seen_papers)
        yield (_status("busy", f'<span class="spinner"></span> Researching "{topic}"... '
                               f"{elapsed}s · {steps} tool calls · {found} papers found"),
               "_The agent is searching and reading. Watch the **Agent steps** tab to see it work._",
               "_References appear when the review is ready._", "\n".join(agent.trace), None)
        thread.join(timeout=1.0)

    trace = "\n".join(agent.trace)
    if "error" in box:
        yield _status("error", friendly_error(box["error"])), "", "", trace, None
        return

    answer = box["answer"]
    summary, refs = _split_answer(answer)
    report = build_report(topic, answer, agent.stats.get("queries", []), agent.stats)
    path = os.path.join(tempfile.mkdtemp(), f"{slugify(topic)}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    s = agent.stats
    done = (f"Done in {int(time.monotonic() - started)}s · {s.get('valid_citations', 0)} verified "
            f"citations · {s.get('arxiv_calls', 0)} arXiv searches")
    yield _status("done", done), summary, refs, trace, path


# ---------------------------------------------------------------------------
# Look and layout
# ---------------------------------------------------------------------------

THEME = gr.themes.Soft(
    primary_hue="indigo",
    secondary_hue="violet",
    neutral_hue="slate",
    font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"],
).set(button_primary_background_fill="linear-gradient(90deg, #4f46e5, #7c3aed)",
      button_primary_background_fill_hover="linear-gradient(90deg, #4338ca, #6d28d9)")

CSS = """
.gradio-container { max-width: 1100px !important; margin: 0 auto !important; }
.hero {
  background: linear-gradient(135deg, #312e81 0%, #4f46e5 55%, #7c3aed 100%);
  color: #fff; border-radius: 18px; padding: 28px 28px 22px; margin-bottom: 6px;
}
.hero h1 { color: #fff; font-size: 2rem; margin: 0 0 6px; line-height: 1.2; }
.hero p  { color: #e0e7ff; font-size: 1.05rem; margin: 0 0 14px; }
.badges  { display: flex; flex-wrap: wrap; gap: 8px; }
.badge   { background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.28);
           border-radius: 999px; padding: 4px 12px; font-size: .85rem; color: #fff; }
.card    { border-radius: 14px !important; }
.steps ol { margin: 4px 0 0 18px; padding: 0; }
.steps li { margin: 6px 0; }
.status  { border-radius: 10px; padding: 10px 14px; font-weight: 500; }
.status-busy  { background: #eef2ff; color: #3730a3; border: 1px solid #c7d2fe; }
.status-done  { background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }
.status-warn  { background: #fffbeb; color: #92400e; border: 1px solid #fde68a; }
.status-error { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
.spinner { display: inline-block; width: 12px; height: 12px; margin-right: 6px; vertical-align: -1px;
           border: 2px solid #a5b4fc; border-top-color: #4338ca; border-radius: 50%;
           animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.chips { flex-wrap: wrap !important; gap: 6px !important; }
.chips button { flex: 0 0 auto !important; border-radius: 999px !important; }
.footer { text-align: center; color: #64748b; font-size: .85rem; margin-top: 8px; }
@media (max-width: 640px) {
  .gradio-container { padding-left: 14px !important; padding-right: 14px !important; }
  .hero { padding: 20px 18px; } .hero h1 { font-size: 1.5rem; }
}
"""

HERO = """
<div class="hero">
  <h1>📚 Research Paper Assistant</h1>
  <p>Type a topic. An AI agent searches arXiv, reads the abstracts and writes you a
     short literature review in under a minute.</p>
  <div class="badges">
    <span class="badge">🔎 Searches arXiv several times</span>
    <span class="badge">✅ Every citation verified in code</span>
    <span class="badge">📄 Download as Markdown</span>
    <span class="badge">🆓 Free</span>
  </div>
</div>
"""

HOW_IT_WORKS = f"""
### How it works
<div class="steps">

1. **Search**: the agent runs 2 to 4 different arXiv searches for your topic.
2. **Select**: it picks the most relevant papers from what it found.
3. **Write**: it summarises the main ideas and how the papers relate.
4. **Verify**: code removes any citation to a paper it never retrieved and builds the reference list itself.

</div>

**Good to know**
- It reads **abstracts only**: open the papers before you rely on a claim.
- Use the field's usual words. For Bangla topics, also try "Bengali".
- Limit: {MAX_PER_USER_PER_HOUR} summaries per hour per visitor.
"""

FOOTER = (f'<div class="footer">Model: {config.LLM_MODEL} · Built step by step as a learning project · '
          '<a href="https://github.com/ar-sohan/Sohan-s_Research_Assistant" target="_blank">Source code</a></div>')

EXAMPLES = ["Bengali sentiment analysis", "retrieval augmented generation",
            "graph neural networks for molecules", "low-resource machine translation",
            "speech emotion recognition", "federated learning privacy"]

WELCOME = _status("done", "Ready. Enter a topic or click an example, then press <b>Write literature review</b>.")

with gr.Blocks(title="Research Paper Assistant") as demo:
    gr.HTML(HERO)

    with gr.Row(equal_height=False):
        with gr.Column(scale=3):
            with gr.Group(elem_classes="card"):
                topic_box = gr.Textbox(label="Research topic", placeholder="e.g. Bengali sentiment analysis",
                                       max_lines=1, autofocus=True)
                papers_slider = gr.Slider(3, 10, value=6, step=1, label="Number of papers to cite")
            run_btn = gr.Button("✨ Write literature review", variant="primary", size="lg")
            gr.Markdown("**Try an example:**")
            with gr.Row(elem_classes="chips"):
                for example in EXAMPLES:
                    chip = gr.Button(example, size="sm", variant="secondary", min_width=0)
                    # Clicking a chip copies its text into the topic box.
                    chip.click(lambda t=example: t, None, topic_box)
        with gr.Column(scale=2):
            gr.Markdown(HOW_IT_WORKS)

    status_html = gr.HTML(WELCOME)

    with gr.Tabs():
        with gr.Tab("📝 Summary"):
            summary_md = gr.Markdown("_Your literature review will appear here._")
        with gr.Tab("📚 References"):
            refs_md = gr.Markdown("_Verified references with arXiv links will appear here._")
        with gr.Tab("🔧 Agent steps"):
            gr.Markdown("Every tool call the agent made, live. This is the agent loop at work.")
            trace_box = gr.Textbox(lines=12, show_label=False, placeholder="No steps yet.")
        with gr.Tab("⬇️ Download"):
            gr.Markdown("The full report: date, model, search queries used, summary and references.")
            report_file = gr.File(label="Report (Markdown)")

    gr.HTML(FOOTER)

    outputs = [status_html, summary_md, refs_md, trace_box, report_file]
    run_btn.click(research, [topic_box, papers_slider], outputs)
    topic_box.submit(research, [topic_box, papers_slider], outputs)


if __name__ == "__main__":
    # A queue lets many visitors wait in line; at most 2 summaries run at once,
    # which keeps us under the provider's requests-per-minute limit.
    demo.queue(default_concurrency_limit=2)
    auth = ("guest", APP_PASSWORD) if APP_PASSWORD else None
    demo.launch(auth=auth, theme=THEME, css=CSS)
