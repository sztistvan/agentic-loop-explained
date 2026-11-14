"""
Step 4: the history grows, and so does the bill. Three ways to handle the context.

Every turn re-sends the whole history, so input tokens grow with every turn. This script runs the
same seven-turn chat three ways and prints the input tokens of each turn:

  full      send everything (the model remembers everything; cost keeps growing)
  last 4    send only the system prompt and the last four messages (cheap; it forgets the start)
  summary   once the history is long, replace the old part with a model-written summary

The last question tests memory: "What is my name?" The name was given in turn 1.

Try:
    python examples/04_context_handling.py
"""
from client import MODEL, client

SYSTEM = {"role": "system", "content": "Answer in at most two short sentences."}
turns = [
    "My name is Ada and I analyse sales data.",
    "Name three common data quality problems.",
    "Which of them is the easiest to fix?",
    "Give one example of a duplicate row.",
    "What is a null value?",
    "Why do outliers matter?",
    "What is my name?",
]
tokens_used = {"in": 0}


def chat(messages):
    response = client.chat.completions.create(model=MODEL, messages=messages)
    tokens_used["in"] += response.usage.prompt_tokens
    return response.choices[0].message.content, response.usage.prompt_tokens


def send_full(history):
    return history


def send_last_4(history):
    return history[-4:]          # drop everything older: cheap, but it forgets


def send_summarised(history):
    """When the history is long, replace all but the last 4 messages by a summary the model writes."""
    if len(history) < 8:
        return history
    old, recent = history[:-4], history[-4:]
    text = "\n".join(f"{m['role']}: {m['content']}" for m in old)
    # How you ask matters. A first version said only "keep names and facts", and the summary read
    # "Ada says she analyses sales data": the model then did not realise the user IS Ada.
    # Asking for notes about "the user" fixes that.
    summary, _ = chat([{"role": "user", "content": (
        "Summarise this conversation in two sentences, as notes about 'the user' "
        "(for example: \"The user's name is ...\"). Keep names and facts.\n\n" + text)}])
    history[:] = [{"role": "user", "content": f"[Summary of the earlier conversation: {summary}]"}] + recent
    return history               # the compacted history is kept, so we do not summarise again next turn


for name, prepare in [("full", send_full), ("last 4", send_last_4), ("summary", send_summarised)]:
    tokens_used["in"] = 0
    history, per_turn = [], []
    for turn in turns:
        history.append({"role": "user", "content": turn})
        reply, tokens_in = chat([SYSTEM] + prepare(history))
        history.append({"role": "assistant", "content": reply})
        per_turn.append(tokens_in)
    print(f"=== {name}")
    print("input tokens per turn:", per_turn, "  total incl. summaries:", tokens_used["in"])
    print("answer to 'What is my name?':", reply, "\n")
