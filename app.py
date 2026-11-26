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


def research(topic: str, papers: int, request: gr.Request):
    """Gradio calls this when the button is pressed.

    It is a *generator*: each `yield` updates the page, so visitors see the
    agent's steps live instead of staring at a spinner for a minute.
    Yields (summary_markdown, trace_text, report_file).
    """
    topic = (topic or "").strip()
    if not 3 <= len(topic) <= 150:
        yield "Please enter a research topic of 3 to 150 characters.", "", None
        return
    refusal = limiter.try_acquire(visitor_id(request))
    if refusal:
        yield f"**{refusal}**", "", None
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
        yield f"_Researching... {elapsed}s (usually 20-90 seconds)_", "\n".join(agent.trace), None
        thread.join(timeout=1.0)

    trace = "\n".join(agent.trace)
    if "error" in box:
        yield f"**{friendly_error(box['error'])}**", trace, None
        return

    report = build_report(topic, box["answer"], agent.stats.get("queries", []), agent.stats)
    path = os.path.join(tempfile.mkdtemp(), f"{slugify(topic)}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    yield box["answer"], trace, path


INTRO = f"""
# Research Paper Assistant

Type a research topic. The agent searches **arXiv** several times, reads the
abstracts, and writes a short literature summary. Every reference is a real
paper it actually retrieved, checked in code, with a working arXiv link.

_Reads abstracts only, so check the papers before relying on a claim.
Limit: {MAX_PER_USER_PER_HOUR} summaries per hour per visitor._
"""

with gr.Blocks(title="Research Paper Assistant") as demo:
    gr.Markdown(INTRO)
    with gr.Row():
        topic_box = gr.Textbox(label="Research topic", placeholder="e.g. Bengali sentiment analysis",
                               scale=4, max_lines=1)
        papers_slider = gr.Slider(3, 10, value=6, step=1, label="Papers to cite", scale=1)
    run_btn = gr.Button("Write literature summary", variant="primary")
    gr.Examples(
        examples=[["retrieval augmented generation", 6], ["Bengali sentiment analysis", 6],
                  ["graph neural networks for molecules", 5], ["low-resource machine translation", 6]],
        inputs=[topic_box, papers_slider],
    )
    summary_md = gr.Markdown(label="Summary")
    report_file = gr.File(label="Download report (Markdown)")
    with gr.Accordion("What the agent did (step by step)", open=False):
        trace_box = gr.Textbox(lines=10, show_label=False)
    gr.Markdown(f"<small>Model: {config.LLM_MODEL} · "
                "[Source code](https://github.com/ar-sohan/Sohan-s_Research_Assistant)</small>")

    run_btn.click(research, [topic_box, papers_slider], [summary_md, trace_box, report_file])
    topic_box.submit(research, [topic_box, papers_slider], [summary_md, trace_box, report_file])


if __name__ == "__main__":
    # A queue lets many visitors wait in line; at most 2 summaries run at once,
    # which keeps us under the provider's requests-per-minute limit.
    demo.queue(default_concurrency_limit=2)
    auth = ("guest", APP_PASSWORD) if APP_PASSWORD else None
    demo.launch(auth=auth)
