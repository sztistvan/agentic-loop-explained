"""
Data Analyst Agent -- a LangGraph tutorial.

The agent answers business questions about a CSV by calling tools: it profiles
the data, writes and runs Python, reads the output, fixes its own errors, makes
charts and, when asked, saves a report.

KEY CONCEPTS (each one maps to a numbered section below)

    1. The four building blocks of an agent:
         Reasoning  the model decides the next step            (make_llm, agent_node)
         Context    system prompt + message history            (prompts/, AgentState)
         Memory     checkpointer per thread_id, sandbox state  (MemorySaver, tools.NAMESPACE)
         Tools      functions the model can request            (tools.py)
    2. State             = the message list the loop grows      (AgentState)
    3. The agentic loop  = model -> tool calls? -> run tools -> model -> ...
    4. Memory in detail  = a checkpointer keyed by thread_id    (MemorySaver)
    5. Optional behaviours, each behind a flag, off by default:
         --approve        human approves code before it runs
         --max-steps N    step budget the model can see
         --plan           plan first, then act
         --review         a reviewer node checks the answer
         --keep-outputs N trim old tool outputs from the model's view

THE GRAPH (with every flag on)

    START -> [plan] -> agent --tool calls?--> [approval] -> tools --+
                        ^   \\                                       |
                        |    +--(final answer)--> [review] -> END   |
                        +------------------------------------------+
    (nodes in [brackets] exist only when their flag is set)

agent_manual_loop.py is the same loop without LangGraph; docs/ compares them.

Usage:
    python agent.py data/sales.csv "Which region underperformed in Q3, and why?"
    python agent.py data/sales.csv        # interactive, follow-ups keep context
    python agent.py data/sales.csv --approve --plan --review --max-steps 10 --keep-outputs 2 "..."
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

import display
from config import MODEL, load_prompt, make_llm
from tools import TOOLS, load_dataset, set_question

MAX_REVISIONS = 1  # how many times the reviewer may send the answer back


@dataclass
class Settings:
    """The optional behaviours. All off by default = the plain loop."""
    approve: bool = False
    plan: bool = False
    review: bool = False
    max_steps: int | None = None
    keep_outputs: int | None = None
    prompt: str = "system"  # name in prompts/ or a path to a .md file


# ===========================================================================
# 2. STATE
# The graph's state is a dict that every node reads and updates. MessagesState
# gives us `messages`: a list that nodes APPEND to (it never overwrites).
# That list IS the agent's working memory: it is what the model sees each turn.
# ===========================================================================
class AgentState(MessagesState):
    steps: int       # tool-calling turns used for the current question (for --max-steps)
    reviews: int     # how many times the reviewer has looked at the answer
    review_ok: bool  # did the last review approve?


# Token accounting: every model call goes through call_model() so we can sum usage.
class Usage:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.calls = self.input_tokens = self.output_tokens = 0

    def add(self, reply: AIMessage) -> None:
        meta = reply.usage_metadata or {}
        self.calls += 1
        self.input_tokens += meta.get("input_tokens", 0)
        self.output_tokens += meta.get("output_tokens", 0)


USAGE = Usage()


def call_model(model, messages: list) -> AIMessage:
    reply = model.invoke(messages)
    USAGE.add(reply)
    return reply


# ---------------------------------------------------------------------------
# Helpers for the optional behaviours
# ---------------------------------------------------------------------------
def trim_history(messages: list, keep: int | None) -> list:
    """--keep-outputs: context hygiene.

    Every step re-sends the WHOLE history, so a big tool output printed at step 2
    is paid for again at every later step. Here we replace all but the last `keep`
    tool outputs with a one-line stub. This is truncation, not summarization:
    no LLM call, deterministic, and only the copy sent to the model shrinks --
    the stored state keeps everything. The model's own text is never touched,
    which is why the system prompt tells it to write findings down as it goes.
    """
    if keep is None:
        return messages
    tool_indexes = [i for i, m in enumerate(messages) if isinstance(m, ToolMessage)]
    old = set(tool_indexes[:-keep] if keep > 0 else tool_indexes)
    trimmed = []
    for i, m in enumerate(messages):
        if i in old and len(str(m.content)) > 300:
            stub = f"[output omitted to save context: {len(str(m.content)):,} chars. Re-run the code if you need it.]"
            m = m.model_copy(update={"content": stub})
        trimmed.append(m)
    return trimmed


def transcript(messages: list, max_tool_chars: int = 1500) -> str:
    """Flatten a conversation to plain text (for the planner and reviewer)."""
    lines = []
    for m in messages:
        if isinstance(m, HumanMessage):
            lines.append(f"USER: {m.content}")
        elif isinstance(m, AIMessage):
            for call in m.tool_calls:
                lines.append(f"ANALYST CALLED {call['name']}: {call['args'].get('code', call['args'])}")
            if display.text_of(m).strip():
                lines.append(f"ANALYST: {display.text_of(m).strip()}")
        elif isinstance(m, ToolMessage):
            lines.append(f"TOOL OUTPUT: {str(m.content)[:max_tool_chars]}")
    return "\n\n".join(lines)


# ===========================================================================
# 3. THE GRAPH  (the agentic loop)
# A node is a function: state in -> partial state update out.
# An edge says which node runs next; a *conditional* edge picks by looking at state.
# ===========================================================================
def build_graph(s: Settings):
    # --- The building blocks ---------------------------------------------------
    system_prompt = load_prompt(s.prompt)          # CONTEXT: the instructions part
    base_llm = make_llm()                          # REASONING: the model, no tools
    agent_llm = base_llm.bind_tools(TOOLS)         # + TOOLS: the schemas it can call

    # --- Nodes -----------------------------------------------------------------
    def agent_node(state: AgentState) -> dict:
        """THE MODEL TURN: send the history, get back either text or tool calls."""
        history = trim_history(state["messages"], s.keep_outputs)
        messages = [SystemMessage(system_prompt), *history]
        steps, model = state.get("steps", 0), agent_llm

        if s.max_steps is not None:  # --max-steps: tell the model how much budget is left
            left = s.max_steps - steps
            if left > 0:
                messages.append(SystemMessage(f"[Budget: {left} tool-calling step(s) left. Plan to finish before it runs out.]"))
            else:  # out of budget: take the tools away so the only option is to answer
                messages.append(SystemMessage("[Budget exhausted. Do not call tools. Give your final answer now from what you have, and say what you could not verify.]"))
                model = base_llm

        reply = call_model(model, messages)
        return {"messages": [reply], "steps": steps + (1 if reply.tool_calls else 0)}

    # ToolNode is prebuilt: for every tool call in the last AI message it runs the
    # matching function and appends a ToolMessage with the result.
    tools_node = ToolNode(TOOLS)

    def approval_node(state: AgentState) -> Command[Literal["tools", "agent"]]:
        """--approve: pause the graph and ask a human before code runs."""
        calls = state["messages"][-1].tool_calls
        for call in calls:
            if call["name"] == "run_python":
                # interrupt() freezes the graph here (state is saved by the
                # checkpointer) and hands this payload to the caller. The graph
                # resumes when the caller sends Command(resume=<answer>).
                answer = interrupt({"code": call["args"]["code"]})
                if answer != "y":  # rejected: every tool call still needs a result message
                    note = f"USER REJECTED this call. Feedback: {answer}. Adjust your approach."
                    rejections = [ToolMessage(note, tool_call_id=c["id"], name=c["name"]) for c in calls]
                    return Command(goto="agent", update={"messages": rejections})
        return Command(goto="tools")

    def plan_node(state: AgentState) -> dict:
        """--plan: one extra model call, no tools, that writes a plan up front."""
        reply = call_model(base_llm, [
            SystemMessage(load_prompt("planner")),
            HumanMessage(transcript(state["messages"])),
        ])
        # The plan joins the history, so the agent sees it on every later turn.
        return {"messages": [AIMessage(f"PLAN:\n{reply.content}")]}

    def review_node(state: AgentState) -> dict:
        """--review: a second 'persona' checks the answer against the evidence."""
        reply = call_model(base_llm, [
            SystemMessage(load_prompt("reviewer")),
            HumanMessage(transcript(state["messages"])),
        ])
        approved = reply.content.strip().upper().startswith("APPROVED")
        update = {"reviews": state.get("reviews", 0) + 1, "review_ok": approved}
        if not approved:  # feed the criticism back to the agent as a new user message
            update["messages"] = [HumanMessage(f"Reviewer feedback -- fix these and answer again:\n{reply.content}")]
        return update

    # --- Routing (the conditional edges) ---------------------------------------
    def route_after_agent(state: AgentState) -> str:
        last = state["messages"][-1]
        if last.tool_calls:                       # the model asked for a tool
            return "approval" if s.approve else "tools"
        if s.review and state.get("reviews", 0) < MAX_REVISIONS:
            return "review"                       # review once; the agent then gets one chance to revise
        return END                                # plain text = the final answer

    def route_after_review(state: AgentState) -> str:
        return END if state["review_ok"] else "agent"

    # --- Wiring ----------------------------------------------------------------
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_edge("tools", "agent")              # tool results always go back to the model

    if s.plan:
        graph.add_node("plan", plan_node)
        graph.add_edge(START, "plan")
        graph.add_edge("plan", "agent")
    else:
        graph.add_edge(START, "agent")

    targets = ["tools", END]
    if s.approve:
        graph.add_node("approval", approval_node)  # routes itself via Command(goto=...)
        targets.append("approval")
    if s.review:
        graph.add_node("review", review_node)
        graph.add_conditional_edges("review", route_after_review, ["agent", END])
        targets.append("review")
    graph.add_conditional_edges("agent", route_after_agent, targets)

    # --- MEMORY ---------------------------------------------------------------
    # The checkpointer saves the state after every node, keyed by thread_id.
    # Same thread_id on the next question = the model still sees the earlier
    # conversation. (RAM only: gone when the process exits.)
    return graph.compile(checkpointer=MemorySaver())


# ===========================================================================
# Running it
# ===========================================================================
def ask(app, question: str, thread_id: str) -> None:
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}
    payload = {"messages": [HumanMessage(question)], "steps": 0, "reviews": 0, "review_ok": False}
    USAGE.reset()
    step = 0
    display.show_question(question)
    set_question(question)  # so save_report can record it in the report header

    while True:
        pending = None
        # stream_mode="updates" yields {node_name: what_that_node_returned}
        for update in app.stream(payload, config, stream_mode="updates"):
            for node, output in update.items():
                if node == "__interrupt__":       # the graph paused (--approve)
                    pending = output[0].value
                    continue
                output = output or {}
                step += sum(isinstance(m, AIMessage) and bool(m.tool_calls) for m in output.get("messages", []))
                display.show_update(node, output, step)
        if pending is None:
            break
        # Resume the paused graph with the human's answer.
        payload = Command(resume=display.ask_approval(pending["code"]))

    display.show_usage(USAGE.calls, USAGE.input_tokens, USAGE.output_tokens)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="LangGraph data analyst agent")
    p.add_argument("data", help="path to the CSV file to analyse")
    p.add_argument("question", nargs="?", help="question to ask (omit for interactive mode)")
    p.add_argument("--prompt", default="system", help="system prompt: name in prompts/ or a .md path")
    p.add_argument("--approve", action="store_true", help="ask before running each piece of code")
    p.add_argument("--plan", action="store_true", help="write a plan before acting")
    p.add_argument("--review", action="store_true", help="a reviewer checks the final answer")
    p.add_argument("--max-steps", type=int, help="tool-calling step budget")
    p.add_argument("--keep-outputs", type=int, help="keep only the last N tool outputs in the model's view")
    a = p.parse_args()

    try:
        load_dataset(a.data)
    except FileNotFoundError:
        raise SystemExit(
            f"{a.data} not found. Generate a sample dataset with "
            "`python generate_sales_data.py` or `python generate_factory_data.py`."
        )

    settings = Settings(a.approve, a.plan, a.review, a.max_steps, a.keep_outputs, a.prompt)
    app = build_graph(settings)
    on = [f for f, v in vars(settings).items() if v and f != "prompt"]
    prompts = {"system": a.prompt}
    if settings.plan:
        prompts["planner"] = "planner"
    if settings.review:
        prompts["reviewer"] = "reviewer"
    display.show_header("Data Analyst Agent", MODEL, a.data, prompts, ", ".join(on) or "none (plain loop)")

    if a.question:
        ask(app, a.question, thread_id="cli")
        return
    print("Ask a question about the data (blank line to quit). Follow-ups keep context.")
    while question := input(f"\n{display.C.BOLD}You ▸ {display.C.END}").strip():
        ask(app, question, thread_id="interactive")


if __name__ == "__main__":
    main()
