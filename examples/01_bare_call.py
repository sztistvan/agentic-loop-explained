"""
Step 1: the simplest possible LLM call. One user message, nothing else.

There is no system prompt here, and the API adds none: the list below is the whole request.
(Chat apps add their own hidden instructions; a plain API call does not.) Look at the token count in
the output: it is about the length of the question and nothing more.

Try:
    python examples/01_bare_call.py
    python examples/01_bare_call.py "What day is it today?"     # the model has no clock
"""
import json
import sys

from client import MODEL, client

question = " ".join(sys.argv[1:]) or "In two sentences, what is a data analyst?"

messages = [{"role": "user", "content": question}]   # the entire request, apart from the model name
print("REQUEST messages:", json.dumps(messages))

# The same request twice: the answers differ, because the model samples its words.
for attempt in (1, 2):
    response = client.chat.completions.create(model=MODEL, messages=messages)
    choice = response.choices[0]
    print(f"\n--- attempt {attempt} ---")
    print(choice.message.content)
    print(f"[finish_reason={choice.finish_reason}   tokens in={response.usage.prompt_tokens}"
          f"   out={response.usage.completion_tokens}]")
