"""
The data analyst agent with an INPUT GUARD in front of it.

agent.py is not changed. This file puts a small check before it:

    question --> guard (one model call, no tools) --> IN_SCOPE   --> the normal agent (agent.ask)
                                                  --> OFF_TOPIC  --> a fixed polite refusal
                                                  --> INJECTION  --> a fixed firm refusal
                       (a provider content filter may refuse the message first: FILTERED)

The guard is a separate model call with its own prompt (prompts/guard.md). It sees only the
previous question and the new message, never the data and never the tools, and it answers with one
word. The refusal texts are written here in code, so they are the same every time and cost nothing.

The guard checks what the USER typed. It cannot see instructions hidden inside the data the agent
reads later (see docs/09-guardrails.md, "Indirect injection").

Usage:
    python agent_guarded.py data/sales.csv "Write a poem about falling leaves."
    python agent_guarded.py data/sales.csv "Which region had the highest revenue?"
    python agent_guarded.py data/sales.csv                       # interactive, follow-ups allowed
    python agent_guarded.py data/sales.csv "..." --prompt system_scoped   # guard + a scoped prompt
"""
from __future__ import annotations

import argparse
import sys

from langchain_core.messages import HumanMessage, SystemMessage

import display
from agent import Settings, ask, build_graph
from config import MODEL_LABEL, load_prompt, make_llm
from tools import load_dataset

LABELS = ("IN_SCOPE", "OFF_TOPIC", "INJECTION")

# What the user sees when the guard stops a message. Fixed text, so it is predictable.
REFUSALS = {
    "OFF_TOPIC": (
        "I can only help with analysing the loaded dataset. "
        'For example, you could ask: "Which region had the highest revenue?"'
    ),
    "INJECTION": (
        "I can't change my instructions or role. I am here to analyse the loaded dataset, "
        "so ask me a question about the data."
    ),
    # Not a label the guard prompt produces: the model PROVIDER's own content filter refused the
    # message before the guard model saw it (Azure does this for some injection-like texts).
    "FILTERED": (
        "The model provider's content filter rejected this message, so it was not processed. "
        "Ask a question about the loaded dataset."
    ),
}


def check(guard_llm, guard_prompt: str, previous: str | None, message: str) -> tuple[str, int, int]:
    """Classify one message. Returns (label, input tokens, output tokens)."""
    text = f"PREVIOUS QUESTION: {previous or '(none)'}\n\nLATEST MESSAGE: {message}"
    try:
        reply = guard_llm.invoke([SystemMessage(guard_prompt), HumanMessage(text)])
    except Exception as exc:  # some providers refuse suspicious input before the model runs
        if "content management policy" in str(exc) or "content_filter" in str(exc):
            return "FILTERED", 0, 0
        raise  # any other error (network, key, ...) is a real problem: do not hide it
    words = display.text_of(reply).strip().upper().split()
    first = words[0].strip(".,:;!*`\"'") if words else ""
    label = first if first in LABELS else "IN_SCOPE"  # unsure or garbled: let it through
    meta = reply.usage_metadata or {}
    return label, meta.get("input_tokens", 0), meta.get("output_tokens", 0)


def guarded_ask(app, guard_llm, guard_prompt: str, previous: str | None, question: str, thread_id: str) -> bool:
    """Run the guard, then the agent if allowed. Returns True if the agent ran."""
    label, tokens_in, tokens_out = check(guard_llm, guard_prompt, previous, question)
    print(f"\n{display.C.GREY}🛡  guard: {label}   (1 model call, tokens in: {tokens_in:,} out: {tokens_out:,}){display.C.END}")
    if label != "IN_SCOPE":
        display.show_question(question)
        display.banner(f"🛡  BLOCKED BY THE GUARD ({label})", display.C.YELLOW)
        print(REFUSALS[label])
        return False
    ask(app, question, thread_id)
    return True


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Data analyst agent with an input guard")
    p.add_argument("data", help="path to the CSV file to analyse")
    p.add_argument("question", nargs="?", help="question to ask (omit for interactive mode)")
    p.add_argument("--prompt", default="system", help="the agent's system prompt: name in prompts/ or a .md path")
    a = p.parse_args()

    try:
        load_dataset(a.data)
    except FileNotFoundError:
        raise SystemExit(
            f"{a.data} not found. Generate a sample dataset with "
            "`python generate_sales_data.py` or `python generate_factory_data.py`."
        )

    app = build_graph(Settings(prompt=a.prompt))   # the unchanged agent from agent.py
    guard_llm, guard_prompt = make_llm(), load_prompt("guard")
    display.show_header("Data Analyst Agent (guarded)", MODEL_LABEL, a.data,
                        {"system": a.prompt, "guard": "guard"}, "input guard")

    if a.question:
        guarded_ask(app, guard_llm, guard_prompt, None, a.question, thread_id="cli")
        return
    print("Ask a question about the data (blank line to quit). Follow-ups keep context.")
    previous = None
    while question := input(f"\n{display.C.BOLD}You ▸ {display.C.END}").strip():
        if guarded_ask(app, guard_llm, guard_prompt, previous, question, thread_id="interactive"):
            previous = question  # only questions the agent actually answered count as context


if __name__ == "__main__":
    main()
