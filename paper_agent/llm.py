"""Milestone 0: the LLM client.

This is the only file that knows how to talk to a model. Everything else
(tools, the agent loop) calls `chat()` and never touches the provider.

Run it directly to check your setup:
    python -m paper_agent.llm
"""

from openai import OpenAI

from paper_agent import config

# One client for the whole program. base_url decides which provider we hit.
client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)


def chat(messages: list[dict], tools: list[dict] | None = None, model: str | None = None):
    """Send a conversation (and optionally tool schemas) to the model.

    messages: the whole conversation so far, e.g.
        [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
    tools: JSON schemas describing functions the model may ask us to call
           (used from Milestone 2 on).

    Returns the assistant *message* object. It has either:
      .content     -> text, when the model answers directly
      .tool_calls  -> a list of requested function calls, when it wants a tool
    """
    kwargs = {"model": model or config.LLM_MODEL, "messages": messages}
    if tools:  # only send the key when there are tools; some providers reject tools=[]
        kwargs["tools"] = tools
    resp = client.chat.completions.create(**kwargs)
    # resp.choices is a list because the API can return several alternatives.
    # We always ask for one, so we take choices[0].message.
    return resp.choices[0].message


if __name__ == "__main__":
    print(f"Provider: {config.LLM_BASE_URL}   Model: {config.LLM_MODEL}\n")
    resp = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[{"role": "user", "content": "In one sentence, what is arXiv?"}],
    )
    # Print the whole response object once, so you can see its shape:
    # id, model, usage (token counts) and choices[0].message.content.
    print(resp.model_dump_json(indent=2))
    print("\nReply:", resp.choices[0].message.content)
