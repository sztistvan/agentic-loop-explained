"""
Shared setup for the example scripts: read .env and build the API client.

The scripts in this folder use the plain `openai` SDK, with no LangChain and no LangGraph, so you can
see exactly what is sent to the model and what comes back. Any OpenAI-compatible endpoint works.

Run them from the project folder, for example:  python examples/01_bare_call.py
"""
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # finds the .env file in the project folder


# Same provider switch as config.py: LLM_PROVIDER=openrouter reads OPENROUTER_BASE_URL, _API_KEY, _MODEL.
PROVIDER = os.environ.get("LLM_PROVIDER", "azure").strip().lower()


def _setting(name: str) -> str:
    var = f"{PROVIDER.upper()}_{name}"
    value = os.environ.get(var)
    if not value:
        raise SystemExit(f"Missing {var} (LLM_PROVIDER={PROVIDER}). Add it to .env, see .env.example.")
    return value


MODEL = _setting("MODEL")
client = OpenAI(base_url=_setting("BASE_URL"), api_key=_setting("API_KEY"))


def assistant_message(message) -> dict:
    """Turn the model's reply into the dict we add to the history.

    If the reply contains tool calls they must be kept, because every tool result that follows
    is matched to a call by its id.
    """
    entry = {"role": "assistant", "content": message.content}
    if message.tool_calls:
        entry["tool_calls"] = [
            {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
            for c in message.tool_calls
        ]
    return entry
