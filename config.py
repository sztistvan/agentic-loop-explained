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


# Which LLM provider to use. Each provider has its own block of settings in .env, named after it:
#   LLM_PROVIDER=openrouter  ->  OPENROUTER_BASE_URL, OPENROUTER_API_KEY, OPENROUTER_MODEL
# Any OpenAI-compatible endpoint works. To switch, change this one line (or set it for one run:
#   LLM_PROVIDER=lmstudio python agent.py data/sales.csv). Without it, "azure" is used.
PROVIDER = os.environ.get("LLM_PROVIDER", "azure").strip().lower()


def _setting(name: str) -> str:
    """The value of this provider's setting, e.g. name='MODEL' -> OPENROUTER_MODEL."""
    var = f"{PROVIDER.upper()}_{name}"
    value = os.environ.get(var)
    if not value:
        raise SystemExit(f"Missing {var} (LLM_PROVIDER={PROVIDER}). Add it to .env, see .env.example.")
    return value


BASE_URL = _setting("BASE_URL")
API_KEY = _setting("API_KEY")
MODEL = _setting("MODEL")
MODEL_LABEL = f"{MODEL} via {PROVIDER}"  # what the run header shows


def _price(name: str) -> float:
    """Optional price per 1M tokens, only used to print a cost estimate.
    A provider-specific value (AZURE_PRICE_INPUT_PER_M) wins over the global one (PRICE_INPUT_PER_M)."""
    return float(os.getenv(f"{PROVIDER.upper()}_{name}") or os.getenv(name) or 0)


PRICE_INPUT_PER_M = _price("PRICE_INPUT_PER_M")
PRICE_OUTPUT_PER_M = _price("PRICE_OUTPUT_PER_M")


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
