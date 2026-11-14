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


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing {name}. Copy .env.example to .env and fill it in.")
    return value


MODEL = _require("AZURE_MODEL")
client = OpenAI(base_url=_require("AZURE_BASE_URL"), api_key=_require("AZURE_API_KEY"))


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
