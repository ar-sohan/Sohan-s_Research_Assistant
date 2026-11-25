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

## Milestone 4: Grounded citations
- Surprised: qwen2.5:7b wrote bare ids like [2506.06962] instead of [arXiv:2506.06962], so the regex accepts both.
- Broke: rich's console.print treats [arXiv:...] as a style tag and silently deleted every citation from the output. Fixed with markup=False.

## Milestone 5: Make it robust
- Surprised: for 'quantum basket weaving' the model quietly changed the topic to quantum basket OPTIONS (finance) and summarised those. Search always returns something; relevance has to be judged against the original topic.
- Broke first: the irrelevant-results problem, not errors. Fixed with explicit 'keep the topic, say nothing relevant' rules in the system prompt.
