# Learning log

Two lines per milestone: what surprised me, and what broke.

## Milestone 0: Talk to a model
- Surprised: every free provider uses the same OpenAI-style API, so `base_url` is the only real switch.
- Broke:

## Milestone 1: Build the tool
- Surprised: arXiv titles and abstracts are full of hard line breaks; they need cleaning before an LLM sees them.
- Broke: the guide's http:// URL now returns a 301 redirect to https://, and httpx does not follow redirects by default.
