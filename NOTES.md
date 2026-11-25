# Learning log

Two lines per milestone: what surprised me, and what broke.

## Milestone 0: Talk to a model
- Surprised: every free provider uses the same OpenAI-style API, so `base_url` is the only real switch.
- Broke: nothing, but `print(resp)` shows a lot of fields; the answer is only `resp.choices[0].message.content`.

## Milestone 1: Build the tool
- Surprised: arXiv titles and abstracts are full of hard line breaks; they need cleaning before an LLM sees them.
- Broke: the guide's http:// URL now returns a 301 redirect to https://, and httpx does not follow redirects by default.

## Milestone 2: One tool call, by hand
- Surprised: the model never runs anything; it only asks. Our code decides, runs the function and reports back.
- Broke: nothing; qwen2.5:7b called search_arxiv for the audio question and skipped it for 2 + 2. One round trip took about 2 minutes on this laptop.

## Milestone 3: The agent loop
- Surprised: arXiv only applies `all:` to the first word, so 'all:retrieval augmented generation' returned off-topic papers. Prefixing every word with AND fixed it.
- Broke: qwen2.5:7b stopped after one search despite the system prompt. A code guard (MIN_SEARCHES) pushes back; a prompt is a request, code is a guarantee.
