# 0. From one LLM call to an agent

This page builds an agent in seven small steps. Each step adds **one** idea and a few lines of code,
and each has a script you can run. The scripts use the plain `openai` SDK, with no LangChain and no
LangGraph, so you see exactly what is sent to the model and what comes back. Step 8 maps the result
onto the project's real code ([agent_manual_loop.py](../agent_manual_loop.py) and
[agent.py](../agent.py)).

The scripts are in [`examples/`](../examples/). They need the same `.env` as the agent, and they are
run from the project folder:

```bash
python examples/01_bare_call.py
```

They do not use the sample datasets. Every step makes only a few model calls, so the cost is tiny. The
outputs shown here are real, from one run each; yours will differ in wording.

## The ladder at a glance

| Step | Script | What you add | Building block ([01-concepts.md](01-concepts.md#the-four-building-blocks)) |
|---|---|---|---|
| 1 | `01_bare_call.py` | A user message, nothing else | Reasoning (the model alone) |
| 2 | `02_system_prompt.py` | A system prompt | Context: instructions |
| 3 | `03_chat_memory.py` | A history list, resent every turn | Memory, short-term |
| 4 | `04_context_handling.py` | Trimming and summarizing the history | Context management |
| 5 | `05_persistent_memory.py` | Saving the history to a file | Memory, persistent |
| 6 | `06_one_tool_call.py` | One tool call: the model asks, you act | Tools |
| 7 | `07_agent_loop.py` | A loop around step 6 | The agentic loop: **an agent** |
| 8 | (this page) | The same agent with LangChain and LangGraph | The harness |

Setup shared by all scripts is in [`examples/client.py`](../examples/client.py): it reads `.env` and
builds the client.

---

## Step 1: a bare call

**Run it** (from the project folder):

```bash
python examples/01_bare_call.py "In two sentences, what is a data analyst?"
```

Another question, to see what the model does not know:

```bash
python examples/01_bare_call.py "What day is it today?"
```

```python
messages = [{"role": "user", "content": "In two sentences, what is a data analyst?"}]
response = client.chat.completions.create(model=MODEL, messages=messages)
print(response.choices[0].message.content)
```

That list is the **entire request**, apart from the model name. Output (the script runs the same
request twice):

```text
--- attempt 1 ---
A data analyst is someone who collects, cleans, and analyzes data to find patterns, trends, and
insights. They then present their findings to help organizations make informed decisions.
[finish_reason=stop   tokens in=16   out=37]

--- attempt 2 ---
A data analyst is a professional who collects, cleans, and analyzes data to find patterns, trends,
and insights. They then communicate their findings to help organizations make better decisions.
[finish_reason=stop   tokens in=16   out=38]
```

What to notice:

- **There is no hidden system prompt.** The call cost 16 input tokens, about the length of the
  question plus a few formatting tokens. Nothing else was sent. *Chat apps are different:* they add
  their own hidden instructions. Anthropic publishes the prompts used in its apps and says they do not
  apply to its API ([System prompts](https://platform.claude.com/docs/en/release-notes/system-prompts)).
  The model also has behaviour from its training, which is not a prompt. The 16-token result here is for
  this tutorial's endpoint.
- **The two answers differ.** The model samples its words, so the same request does not always give
  the same answer.
- **The response carries more than text:** `finish_reason` (why it stopped) and the token counts.
  Tokens in and out are what you pay for.
- **The model knows nothing about now.** Try `python examples/01_bare_call.py "What day is it today?"`.

Block added: **Reasoning**, the model on its own. It has no instructions, memory or tools.

## Step 2: a system prompt

**Run it** (from the project folder):

```bash
python examples/02_system_prompt.py "Explain what a data analyst does."
```

A system prompt is one more message, with the role `system`, placed first:

```python
messages = [
    {"role": "system", "content": "Answer in one short sentence."},
    {"role": "user", "content": question},
]
```

The script asks the same question with four different system prompts. Input tokens grow, because the
system prompt is part of what is sent:

| System prompt | Tokens in | What came back |
|---|---|---|
| *(none)* | 13 | a long answer with headings and bullet lists (236 tokens out) |
| "Answer in one short sentence." | 23 | one sentence (21 out) |
| "Reply with JSON only, in this shape: ..." | 38 | `{"role":"assistant","tasks":["...", ...]}` |
| "You are a skeptical senior data analyst. Answer briefly and name one thing that could go wrong." | 36 | a short answer ending "One thing that could go wrong: garbage-in/incorrect assumptions…" |

Only the system prompt changed. The model and the question were the same.

Block added: **Context, the instructions part.** This is what `prompts/system.md` is in the real agent.

## Step 3: a conversation, and why it needs memory

**Run it** (from the project folder):

```bash
python examples/03_chat_memory.py
```

The model is **stateless**: each call knows only what is in that call's messages. The script shows it
in two parts.

**A. Only the latest message is sent each turn:**

```text
you:   My name is Ada and I analyse sales data.
model: Nice to meet you, Ada, ...
you:   What is my name, and what do I analyse?
model: I don't know your name from this chat, and I can't infer what you analyze ...
[messages sent: 2, tokens in=29]
```

**B. The whole history is sent each turn:**

```python
history.append({"role": "user", "content": turn})
reply = ask(history)
history.append({"role": "assistant", "content": reply})   # remember the model's side too
```

```text
you:   What is my name, and what do I analyse?
model: Your name is Ada, and you analyse sales data.
[messages sent: 4, tokens in=86]
```

**Memory is not a feature of the model. It is this list**, which you keep and resend. Notice the cost:
input tokens went from 29 to 86 for the same second question.

Block added: **Memory, short-term.**

## Step 4: handling a growing context

**Run it** (from the project folder):

```bash
python examples/04_context_handling.py
```

Every turn resends the whole history, so input tokens grow with every turn. The script runs a
seven-turn chat three ways. The first message says "My name is Ada...", and the last question is "What
is my name?".

| Strategy | Input tokens per turn | Total (incl. summary calls) | "What is my name?" |
|---|---|---|---|
| **full:** send everything | 28, 64, 108, 148, 202, 240, 271 | 1,061 | "Your name is Ada." |
| **last 4:** send only the system prompt and the last four messages | 28, 89, 120, 111, 124, 113, 101 | 686 | "I don't know your name from this chat." |
| **summary:** replace the old part with a model-written summary | 28, 72, 119, 173, 208, 255, 234 | 1,436 | "Your name is Ada." |

What to notice:

- **Trimming is cheap and forgets.** Dropping old messages flattens the cost but loses whatever was
  said early.
- **Summarizing keeps the meaning but costs extra calls.** At this short length it costs more than
  sending everything. It pays off in long conversations.
- **How you ask for the summary matters.** The first version of the script said only "keep names and
  facts". The summary read "Ada says she analyses sales data", and the model then did not realise the
  *user* is Ada, so it answered "I don't know your name". Asking for notes about "the user" fixed it.
- The exact numbers vary from run to run, and the three rows above come from separate runs.

In the real project, `--keep-outputs` is a form of trimming that keeps the model's own text and
stubs old tool outputs (see [05-behaviours.md](05-behaviours.md#--keep-outputs-n-context-hygiene)).
Anthropic describes summarizing a conversation near the context limit as *compaction* in
[Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).

Block added: **context management** (what the model sees, versus what is stored).

## Step 5: memory that survives a restart

**Run it** (from the project folder):

```bash
python examples/05_persistent_memory.py "My name is Ada."
```

```bash
python examples/05_persistent_memory.py "What is my name?"
```

```bash
python examples/05_persistent_memory.py --reset
```

In step 3 the history lived in a Python list and was gone when the program ended. Here each run loads
the list from a file, adds one turn, and saves it again:

```python
history = json.loads(MEMORY_FILE.read_text()) if MEMORY_FILE.exists() else []
history.append({"role": "user", "content": question})
...
history.append({"role": "assistant", "content": reply})
MEMORY_FILE.write_text(json.dumps(history, indent=2))
```

Run it as three separate commands. Each is a new process:

```text
$ python examples/05_persistent_memory.py "My name is Ada."
[loaded 0 earlier messages from chat_memory.json]
Nice to meet you, Ada! How can I help you today?
[saved 2 messages   tokens in=23]

$ python examples/05_persistent_memory.py "What is my name?"
[loaded 2 earlier messages from chat_memory.json]
Your name is Ada.
[saved 4 messages   tokens in=52]

$ python examples/05_persistent_memory.py --reset
memory cleared
```

This is the idea behind a **checkpointer** in agent frameworks: save the conversation after each step,
under a conversation id. The project's `MemorySaver` does this in RAM only (so it is lost when the
process ends), and it uses a `thread_id` to tell conversations apart. What a real persistent version
must also restore is covered in [06-architecture.md](06-architecture.md#state-lives-in-two-places).

**Persistent memory in LangGraph.** You do not write the file code yourself. You swap the checkpointer,
and the graph and nodes stay the same. The SQLite one stores everything in a single file:

```python
# pip install langgraph-checkpoint-sqlite
from langgraph.checkpoint.sqlite import SqliteSaver

with SqliteSaver.from_conn_string("checkpoints.db") as saver:
    app = graph.compile(checkpointer=saver)
    config = {"configurable": {"thread_id": "chat-1"}}      # same id after a restart = same conversation
    app.invoke({"messages": [HumanMessage("My name is Ada.")]}, config)
```

The state is saved after every node, so a run that stopped halfway can also be resumed. For a real
service there is `PostgresSaver`. Remembering facts *across* conversations is a separate mechanism, a
LangGraph *store*, which your nodes read and write explicitly. The project's `agent.py` uses the
in-memory `MemorySaver`.

Block added: **Memory, persistent.**

## Step 6: one tool call

**Run it** (from the project folder):

```bash
python examples/06_one_tool_call.py "What is the status of order A-1001, and why?"
```

A question that needs no tool:

```bash
python examples/06_one_tool_call.py "What is the capital of France?"
```

The model cannot look up an order. So we tell it which tools exist, and it replies with a **request**
to call one. It runs nothing itself. The tools are two toy functions in
[`examples/toy_tools.py`](../examples/toy_tools.py), each with a JSON description:

```json
{
  "type": "function",
  "function": {
    "name": "get_order_status",
    "description": "Get the status of one order, and the reason if it is delayed.",
    "parameters": {
      "type": "object",
      "properties": { "order_id": { "type": "string", "description": "for example A-1001" } },
      "required": ["order_id"]
    }
  }
}
```

This list goes in the request as `tools=TOOL_SPECS`. The script, with the real output:

```text
finish_reason: tool_calls

The model asked for these tool calls:
  id=call_5jf8...  name=get_order_status  arguments (a JSON string)={"order_id":"A-1001"}

We ran get_order_status -> {"order_id": "A-1001", "status": "delayed", "reason": "supplier stockout"}
```

Then we add two messages to the history and call the model again:

```json
{"role": "assistant", "content": null,
 "tool_calls": [{"id": "call_5jf8...", "type": "function",
                 "function": {"name": "get_order_status", "arguments": "{\"order_id\":\"A-1001\"}"}}]},
{"role": "tool", "tool_call_id": "call_5jf8...",
 "content": "{\"order_id\": \"A-1001\", \"status\": \"delayed\", \"reason\": \"supplier stockout\"}"}
```

```text
FINAL ANSWER: Order A-1001 is currently delayed due to a supplier stockout.
```

What to notice:

- **The model asks, our code acts.** `finish_reason` was `tool_calls`, not `stop`.
- **The call and its result are matched by `id`.** Without a result for every call, the API
  returns an error.
- **The tool result is just text** in a message with the role `tool`.
- Try a question that needs no tool, such as `python examples/06_one_tool_call.py "What is the
  capital of France?"`. The model answers directly, with no tool call.

Block added: **Tools.** [04-tools.md](04-tools.md) covers how tools are defined, bound and dispatched
in the real agent.

## Step 7: the loop, and an agent

**Run it** (from the project folder):

```bash
python examples/07_agent_loop.py "Is any order for ada@example.com delayed, and why?"
```

A wrong order id, to see how it reacts to an error:

```bash
python examples/07_agent_loop.py "What is the status of order 1001?"
```

Step 6 did one round. An agent repeats it until the model has what it needs:

```text
messages = [system prompt, user question]
repeat up to MAX_STEPS:
    reply = model(messages, tools)
    messages.append(reply)                      # THINK
    if reply has no tool calls: done            # DECIDE
    for each call: messages.append(result)      # ACT
```

```python
for step in range(1, MAX_STEPS + 1):
    response = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOL_SPECS)
    message = response.choices[0].message
    messages.append(assistant_message(message))
    if not message.tool_calls:
        print("FINAL ANSWER:", message.content)
        break
    for call in message.tool_calls:
        result = run_tool(call.function.name, call.function.arguments)
        messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
```

The default question needs two dependent lookups. The model cannot know the order ids up front, so it
must use the first result to plan the second call:

```text
QUESTION: Is any order for ada@example.com delayed, and why?
step 1: find_orders({"customer_email":"ada@example.com"}) -> ["A-1001", "A-1002"]   [tokens in so far: 217]
step 2: get_order_status({"order_id": "A-1001"}) -> {"order_id": "A-1001", "status": "delayed", ...}
step 2: get_order_status({"order_id": "A-1002"}) -> {"order_id": "A-1002", "status": "delivered", ...}

FINAL ANSWER (after 3 model calls): Yes. For ada@example.com, the delayed order is A-1001: supplier
stockout. The other order (A-1002) is delivered.     <- formatting shortened here
[total input tokens: 855   messages in the history: 8]
```

What to notice:

- **The model chose the order of the tools.** Nothing in the code says "find the orders first".
- **It asked for two tools in one turn** (the two `step 2` lines). Each got its own result message.
- **Errors come back as ordinary results.** With `python examples/07_agent_loop.py "What is the status
  of order 1001?"`, the tool answered `ERROR: no order '1001'. Valid order ids look like: A-1001, ...`.
  The model read it and, because the system prompt says "Do not guess", asked the user which order
  they meant instead of making one up.
- **`MAX_STEPS` is the safety stop**, so a confused model cannot loop forever.
- **The input tokens grow every step**, for the same reason as in step 3.

**This is an agent.** By Anthropic's usage it is an LLM using tools in a loop, and by the four
building blocks it is Reasoning, Context, Memory and Tools joined by a loop. See
[Terminology](01-concepts.md#terminology-how-the-words-relate) for how these words relate. The loop in
this step is the same loop as in [agent_manual_loop.py](../agent_manual_loop.py).

## Step 8: from this toy to the real agent

The scripts above use the raw SDK. The project's agents do the same things with LangChain and
LangGraph around the SDK. This table puts them side by side:

| | Raw SDK (steps 1 to 7) | LangChain: `agent_manual_loop.py` | LangGraph: `agent.py` |
|---|---|---|---|
| Calling the model | `client.chat.completions.create(model=..., messages=...)` | `ChatOpenAI(...)`, then `.invoke(messages)` (built in `make_llm()`) | the same `ChatOpenAI`, called inside a graph node |
| A message | a dict: `{"role": "user", "content": ...}` | an object: `HumanMessage`, `AIMessage`, `SystemMessage`, `ToolMessage` | the same objects, held in the graph state |
| Describing a tool | you write the JSON by hand (`TOOL_SPECS`) | `@tool` on a function; `bind_tools(TOOLS)` writes the JSON | the same |
| Running a tool | `run_tool(name, args_json)`, your lookup | `TOOLS_BY_NAME[call["name"]].invoke(call["args"])` | `ToolNode(TOOLS)` |
| The loop | `for step in range(...)` | `for step in range(...)` in `run_agent()` | a graph: `agent` and `tools` joined by edges |
| Stopping | `if not message.tool_calls: break` | `if not reply.tool_calls: return` | a conditional edge to `END` |
| Memory | a list, plus a JSON file in step 5 | a `history` list | graph state with a `MemorySaver` and a `thread_id` |
| Extras | none | none | `--approve`, `--plan`, `--review`, `--max-steps`, `--keep-outputs` |

The same ideas in the three styles, one at a time. The LangChain and LangGraph snippets use the
same toy tool as steps 6 and 7.

**1. Calling the model**

```python
# raw SDK
response = client.chat.completions.create(
    model=MODEL, messages=[{"role": "system", "content": system}, {"role": "user", "content": question}])
answer = response.choices[0].message.content

# LangChain
reply = llm.invoke([SystemMessage(system), HumanMessage(question)])
answer = reply.content

# LangGraph (the model call is hidden inside a node; you run the whole graph)
result = app.invoke({"messages": [HumanMessage(question)]}, config)
answer = result["messages"][-1].content
```

**2. Defining a tool** (the toy `get_order_status`, as in steps 6 and 7). The model needs a description
of the tool; the style decides who writes it:

```python
# raw SDK: you write the JSON by hand, next to a plain function
def get_order_status(order_id: str) -> str: ...

TOOL_SPECS = [{"type": "function", "function": {
    "name": "get_order_status",
    "description": "Get the status of one order, and the reason if it is delayed.",
    "parameters": {"type": "object",
                   "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]}}}]
response = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOL_SPECS)

# LangChain: @tool builds the same JSON from the signature and the docstring
@tool
def get_order_status(order_id: str) -> str:
    """Get the status of one order, and the reason if it is delayed."""

llm = make_llm().bind_tools([get_order_status])      # attaches the JSON to every request

# LangGraph: the same @tool function, the same bind_tools, inside the agent node
```

**3. Running the tool calls the model asked for**

```python
# raw SDK: look the name up yourself, then append a "tool" message
for call in message.tool_calls:
    result = run_tool(call.function.name, call.function.arguments)    # arguments is a JSON string
    messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

# LangChain: the tool object runs itself; you still build the ToolMessage
for call in reply.tool_calls:                                         # call["args"] is already a dict
    result = TOOLS_BY_NAME[call["name"]].invoke(call["args"])
    history.append(ToolMessage(content=result, tool_call_id=call["id"], name=call["name"]))

# LangGraph: a prebuilt node does both for every call in the last AI message
tools_node = ToolNode([get_order_status])
```

**4. The loop and the stop condition**

```python
# raw SDK and LangChain: a for loop, with the stop condition inside it
for step in range(MAX_STEPS):
    ...call the model...
    if not message.tool_calls:      # plain text: the model is done
        break
    ...run the tools...

# LangGraph: the same loop drawn as a graph. The edges are the loop.
graph = StateGraph(MessagesState)
graph.add_node("agent", agent_node)               # calls the model
graph.add_node("tools", ToolNode(TOOLS))          # runs the tool calls
graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", route)       # route() returns "tools" or END
graph.add_edge("tools", "agent")                  # results always go back to the model
app = graph.compile()
```

**5. Memory across questions**

```python
# raw SDK and LangChain: a list you keep and resend
history.append(user_message)
reply = call_the_model(history)
history.append(reply)

# LangGraph: a checkpointer stores the state; you send only the new message
app = graph.compile(checkpointer=MemorySaver())
config = {"configurable": {"thread_id": "chat-1"}}        # same id = same conversation
app.invoke({"messages": [HumanMessage("My name is Ada.")]}, config)
app.invoke({"messages": [HumanMessage("What is my name?")]}, config)   # it still remembers
```

The runnable versions are [agent_manual_loop.py](../agent_manual_loop.py) (LangChain) and
[agent.py](../agent.py) (LangGraph). They use the project's real tools instead of the toy ones.

What the real agent adds on top of step 7:

| Step 7 has | The real agent adds | Read |
|---|---|---|
| Two toy tools | Tools with real power: `run_python` in a sandbox, `describe_dataset`, `save_report`, with guardrails such as the chart-path check | [04-tools.md](04-tools.md) |
| A system prompt in the code | The system prompt as an editable file, kept free of dataset specifics | [01-concepts.md](01-concepts.md) |
| A history list | State kept by a checkpointer per `thread_id` | [06-architecture.md](06-architecture.md) |
| `MAX_STEPS` | A step budget the model can see, with a graceful forced answer | [05-behaviours.md](05-behaviours.md#--max-steps-n-bounded-loops) |
| Resending everything | Context hygiene: old tool outputs replaced by stubs | [05-behaviours.md](05-behaviours.md#--keep-outputs-n-context-hygiene) |
| Running every tool call | Human approval before code runs | [05-behaviours.md](05-behaviours.md#--approve-human-in-the-loop) |
| Straight to acting | An optional plan first, and an optional review after | [05-behaviours.md](05-behaviours.md#--plan-plan-then-act) |
| `print` | A run header, token totals and saved transcripts | [02-agentic-loop.md](02-agentic-loop.md) |

Next: [01-concepts.md](01-concepts.md) names the pieces you just built.
