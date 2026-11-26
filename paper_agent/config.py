"""Settings for the LLM, read from the .env file.

Every provider in the guide (Ollama, Groq, Gemini, OpenRouter) speaks the same
"OpenAI-compatible" chat API. So switching models means changing three values,
never the agent code:

    LLM_BASE_URL  where the API lives
    LLM_API_KEY   your key (Ollama ignores it, but the client needs *something*)
    LLM_MODEL     which model to use
"""

import os

from dotenv import load_dotenv

# load_dotenv() copies KEY=value lines from .env into os.environ.
# It does NOT overwrite variables already set in your shell, so you can
# override a setting for one run:  $env:LLM_MODEL="qwen2.5:3b"; python ...
load_dotenv()

if os.getenv("GROQ_API_KEY") and not os.getenv("LLM_BASE_URL"):
    # Hosted website (Hugging Face Space): the only setting is the GROQ_API_KEY
    # secret, so Groq becomes the default provider. LLM_MODEL can still override.
    LLM_BASE_URL = "https://api.groq.com/openai/v1"
    LLM_API_KEY = os.environ["GROQ_API_KEY"]
    LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
else:
    # Local default: Ollama on this computer, no key needed.
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")
    LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")
