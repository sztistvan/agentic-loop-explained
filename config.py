"""
Shared configuration: environment variables, the LLM client, and prompt loading.

Both agents (agent.py and agent_manual_loop.py) import from here, so the only
difference between them is the loop itself.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

ROOT = Path(__file__).parent
PROMPT_DIR = ROOT / "prompts"


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing {name}. Copy .env.example to .env and fill it in.")
    return value


BASE_URL = _require("AZURE_BASE_URL")
API_KEY = _require("AZURE_API_KEY")
MODEL = _require("AZURE_MODEL")

# Optional: price per 1M tokens, only used to print a cost estimate.
PRICE_INPUT_PER_M = float(os.getenv("PRICE_INPUT_PER_M", "0"))
PRICE_OUTPUT_PER_M = float(os.getenv("PRICE_OUTPUT_PER_M", "0"))


def make_llm() -> ChatOpenAI:
    """The chat model. Any OpenAI-compatible endpoint works."""
    return ChatOpenAI(
        model=MODEL, base_url=BASE_URL, api_key=API_KEY, max_completion_tokens=4096
    )


def load_prompt(name_or_path: str) -> str:
    """Read a prompt from disk. 'system' -> prompts/system.md; a path is used as is.

    Prompts are plain text files so you can edit them without touching code.
    """
    path = Path(name_or_path)
    if not path.suffix:
        path = PROMPT_DIR / f"{name_or_path}.md"
    return path.read_text(encoding="utf-8").strip()
