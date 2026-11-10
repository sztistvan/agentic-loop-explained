"""
Shared configuration: environment variables, the LLM client, and prompt loading.

Both agents (agent.py and agent_manual_loop.py) import from here, so the only
difference between them is the loop itself.
"""
from __future__ import annotations

import hashlib
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


def prompt_path(name_or_path: str) -> Path:
    """'system' -> prompts/system.md; anything with an extension is used as a path."""
    path = Path(name_or_path)
    return path if path.suffix else PROMPT_DIR / f"{name_or_path}.md"


def load_prompt(name_or_path: str) -> str:
    """Read a prompt from disk.

    Prompts are plain text files so you can edit them without touching code.
    """
    return prompt_path(name_or_path).read_text(encoding="utf-8").strip()


def describe_prompt(name_or_path: str) -> str:
    """'prompts/system.md (sha 3fa9c21)': which file, and a short hash of its exact text.

    The hash tells you whether two runs used the same prompt wording.
    """
    path = prompt_path(name_or_path)
    digest = hashlib.sha256(load_prompt(name_or_path).encode("utf-8")).hexdigest()[:7]
    try:
        shown = path.resolve().relative_to(ROOT)
    except ValueError:
        shown = path
    return f"{shown.as_posix()} (sha {digest})"
