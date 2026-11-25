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

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")
