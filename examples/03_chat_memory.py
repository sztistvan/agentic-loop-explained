"""
Step 3: a conversation. The model has no memory, so memory is a list that WE resend every time.

Part A sends only the latest message each turn: the model forgets everything.
Part B keeps a `history` list, appends both sides of every turn, and sends the whole list each time.
Memory is not a feature of the model. It is this list.

Try:
    python examples/03_chat_memory.py
"""
from client import MODEL, client

SYSTEM = {"role": "system", "content": "Answer in at most two short sentences."}
turns = [
    "My name is Ada and I analyse sales data.",
    "What is my name, and what do I analyse?",
]


def ask(messages):
    response = client.chat.completions.create(model=MODEL, messages=messages)
    return response.choices[0].message.content, response.usage.prompt_tokens


print("=== A: no memory (only the latest message is sent)")
for turn in turns:
    reply, tokens_in = ask([SYSTEM, {"role": "user", "content": turn}])
    print(f"you:   {turn}\nmodel: {reply}\n[messages sent: 2, tokens in={tokens_in}]\n")

print("=== B: with memory (the whole history is sent every turn)")
history = [SYSTEM]
for turn in turns:
    history.append({"role": "user", "content": turn})
    reply, tokens_in = ask(history)
    history.append({"role": "assistant", "content": reply})   # remember the model's side too
    print(f"you:   {turn}\nmodel: {reply}\n[messages sent: {len(history) - 1}, tokens in={tokens_in}]\n")
