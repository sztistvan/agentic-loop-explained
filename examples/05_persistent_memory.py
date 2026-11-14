"""
Step 5: memory that survives a restart. Save the history to a file, load it next time.

In step 3 the history lived in a Python list, so it was gone when the program ended. Here every run
loads the list from a JSON file, adds one turn, and saves it again. This is the idea behind a
"checkpointer" in agent frameworks: save the conversation after each step, keyed by a conversation id.

Run these as three separate commands:
    python examples/05_persistent_memory.py "My name is Ada."
    python examples/05_persistent_memory.py "What is my name?"
    python examples/05_persistent_memory.py --reset
"""
import json
import sys
from pathlib import Path

from client import MODEL, client

MEMORY_FILE = Path(__file__).parent / "chat_memory.json"
SYSTEM = {"role": "system", "content": "Answer in at most two short sentences."}

if sys.argv[1:] == ["--reset"]:
    MEMORY_FILE.unlink(missing_ok=True)
    raise SystemExit("memory cleared")

history = json.loads(MEMORY_FILE.read_text(encoding="utf-8")) if MEMORY_FILE.exists() else []
print(f"[loaded {len(history)} earlier messages from {MEMORY_FILE.name}]")

question = " ".join(sys.argv[1:]) or "Hello! What do you remember about me?"
history.append({"role": "user", "content": question})

response = client.chat.completions.create(model=MODEL, messages=[SYSTEM] + history)
reply = response.choices[0].message.content
history.append({"role": "assistant", "content": reply})

MEMORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")
print(reply)
print(f"[saved {len(history)} messages   tokens in={response.usage.prompt_tokens}]")
