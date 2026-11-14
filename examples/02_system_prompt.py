"""
Step 2: add a system prompt. Same question, different instructions, different behaviour.

A system prompt is just another message with the role "system", placed first. The model reads it
before the user's question. Notice that the system prompt costs input tokens too.

Try:
    python examples/02_system_prompt.py
    python examples/02_system_prompt.py "Why do outliers matter?"
"""
import sys

from client import MODEL, client

question = " ".join(sys.argv[1:]) or "Explain what a data analyst does."

system_prompts = {
    "(none)": None,
    "one short sentence": "Answer in one short sentence.",
    "JSON only": 'Reply with JSON only, in this shape: {"role": "...", "tasks": ["..."]}',
    "skeptical senior analyst": "You are a skeptical senior data analyst. Answer briefly and name one thing that could go wrong.",
}

for name, system in system_prompts.items():
    messages = [{"role": "user", "content": question}]
    if system:
        messages.insert(0, {"role": "system", "content": system})   # the only difference between runs

    response = client.chat.completions.create(model=MODEL, messages=messages)
    print(f"=== system prompt: {name}")
    print(response.choices[0].message.content)
    print(f"[tokens in={response.usage.prompt_tokens}   out={response.usage.completion_tokens}]\n")
