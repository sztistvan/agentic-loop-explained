"""
Console rendering only. No agent logic lives here.

Both agents call show_message() so you can watch the loop happen:
    💭 the model's reasoning text
    ▶  a tool call (the code it wants to run)
    ◀  the tool result that goes back to the model
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage

from config import PRICE_INPUT_PER_M, PRICE_OUTPUT_PER_M


class C:
    BLUE, GREEN, YELLOW, RED, GREY, BOLD, END = (
        "\033[94m", "\033[92m", "\033[93m", "\033[91m", "\033[90m", "\033[1m", "\033[0m",
    )


def text_of(msg) -> str:
    """Message content is a string, or a list of typed blocks; return the text."""
    if isinstance(msg.content, str):
        return msg.content
    return "\n".join(b.get("text", "") for b in msg.content if b.get("type") == "text")


def banner(title: str, color: str = C.GREEN) -> None:
    print(f"\n{C.BOLD}{color}{'═' * 70}\n{title}\n{'═' * 70}{C.END}")


def show_message(msg, step: int) -> None:
    """Print one message from the conversation."""
    if isinstance(msg, AIMessage):
        thought = text_of(msg).strip()
        if msg.tool_calls:
            if thought:
                print(f"\n{C.BLUE}💭 {thought}{C.END}")
            for call in msg.tool_calls:
                print(f"\n{C.BOLD}{C.YELLOW}▶ Step {step}: {call['name']}{C.END}")
                args = call["args"]
                print(f"{C.GREY}{args.get('code') or args or '(no arguments)'}{C.END}")
        else:
            banner("✅ FINAL ANSWER")
            print(thought)
        usage = msg.usage_metadata
        if usage:
            print(f"{C.GREY}   tokens: in={usage['input_tokens']:,} out={usage['output_tokens']:,}{C.END}")
    elif isinstance(msg, ToolMessage):
        out = str(msg.content)
        failed = "ERROR:" in out
        label = "✗ error -- the agent will read it and self-correct" if failed else "◀ output"
        print(f"{C.RED if failed else C.END}{label}\n{out.strip()}{C.END}")


def show_update(node: str, output: dict, step: int) -> None:
    """Print what one graph node produced (LangGraph version)."""
    messages = output.get("messages", [])
    if node == "plan":
        banner("📝 PLAN", C.BLUE)
        print(messages[0].content)
    elif node == "review":
        if messages:
            banner("🔎 REVIEWER: problems found, sending back to the agent", C.RED)
            print(messages[0].content)
        else:
            print(f"\n{C.GREEN}🔎 Reviewer: approved{C.END}")
    else:
        for msg in messages:
            show_message(msg, step)


def ask_approval(code: str) -> str:
    """Human-in-the-loop prompt. Returns 'y', or free text = rejection feedback."""
    print(f"\n{C.BOLD}{C.YELLOW}✋ Approval needed -- the agent wants to run:{C.END}")
    print(f"{C.GREY}{code}{C.END}")
    answer = input(f"{C.BOLD}Run it? [y]es / type feedback to reject ▸ {C.END}").strip()
    return "y" if answer.lower() in ("", "y", "yes") else answer


def show_usage(calls: int, input_tokens: int, output_tokens: int) -> None:
    line = f"model calls: {calls}   tokens in: {input_tokens:,}   out: {output_tokens:,}"
    if PRICE_INPUT_PER_M or PRICE_OUTPUT_PER_M:
        cost = input_tokens / 1e6 * PRICE_INPUT_PER_M + output_tokens / 1e6 * PRICE_OUTPUT_PER_M
        line += f"   est. cost: ${cost:.4f}"
    print(f"\n{C.GREY}📈 {line}{C.END}")
