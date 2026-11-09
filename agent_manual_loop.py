"""
The same data analyst agent WITHOUT a framework: the agentic loop written by hand.

Same model, same system prompt, same tools as agent.py. The only difference is
that here you can see the loop as plain Python. Read run_agent() -- that is
the entire idea of an agent:

    repeat:
        ask the model what to do next            (send the whole history)
        if it answered in plain text -> done
        else run each tool it asked for, append the results, loop

This version is deliberately minimal: no flags, no checkpointer. Memory across
questions is just the `history` list that we keep passing in.

Usage:
    python agent_manual_loop.py "Which region underperformed in Q3, and why?"
    python agent_manual_loop.py            # interactive
"""
from __future__ import annotations

import argparse
import sys

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

import display
from config import MODEL, load_prompt, make_llm
from tools import TOOLS, load_dataset

MAX_STEPS = 15  # safety net so a confused model cannot loop forever
TOOLS_BY_NAME = {t.name: t for t in TOOLS}


def run_agent(llm, system_prompt: str, history: list, question: str) -> None:
    """One question, answered by looping model <-> tools. `history` is the state."""
    history.append(HumanMessage(question))

    for step in range(1, MAX_STEPS + 1):
        # 1. THINK: the model sees the system prompt + everything so far.
        reply = llm.invoke([SystemMessage(system_prompt), *history])
        history.append(reply)
        display.show_message(reply, step)

        # 2. DECIDE: no tool calls means the model is giving its final answer.
        if not reply.tool_calls:
            return

        # 3. ACT: run every tool the model asked for and feed the results back.
        for call in reply.tool_calls:
            result = TOOLS_BY_NAME[call["name"]].invoke(call["args"])
            tool_message = ToolMessage(content=result, tool_call_id=call["id"], name=call["name"])
            history.append(tool_message)
            display.show_message(tool_message, step)

    print(f"Stopped: reached MAX_STEPS={MAX_STEPS} without a final answer.")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Data analyst agent, hand-written loop")
    p.add_argument("question", nargs="?", help="question to ask (omit for interactive mode)")
    p.add_argument("--csv", default="data/sales.csv", help="path to the dataset")
    a = p.parse_args()

    try:
        load_dataset(a.csv)
    except FileNotFoundError:
        raise SystemExit(f"{a.csv} not found. Run `python generate_data.py` first.")

    llm = make_llm().bind_tools(TOOLS)       # the model, told about the tools
    system_prompt = load_prompt("system")
    history: list = []                       # the agent's entire memory
    print(f"{display.C.BOLD}📊 Data Analyst Agent (manual loop){display.C.END} ({MODEL}) -- dataset: {a.csv}")

    if a.question:
        run_agent(llm, system_prompt, history, a.question)
        return
    print("Ask a question about the data (blank line to quit). Follow-ups keep context.")
    while question := input(f"\n{display.C.BOLD}You ▸ {display.C.END}").strip():
        run_agent(llm, system_prompt, history, question)


if __name__ == "__main__":
    main()
