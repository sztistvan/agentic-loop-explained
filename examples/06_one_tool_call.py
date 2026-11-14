"""
Step 6: one tool call. The model asks, we act.

The model cannot look up an order. We tell it that two tools exist (their JSON descriptions go in the
request), and it replies with a *request to call one*. It runs nothing itself. We run the function and
send the result back as a "tool" message; then the model writes its answer.

Try:
    python examples/06_one_tool_call.py
    python examples/06_one_tool_call.py "What is the capital of France?"     # no tool needed
"""
import json
import sys

from client import MODEL, assistant_message, client
from toy_tools import TOOL_SPECS, run_tool

question = " ".join(sys.argv[1:]) or "What is the status of order A-1001, and why?"
messages = [{"role": "user", "content": question}]

# 1. Ask, and tell the model which tools exist.
first = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOL_SPECS)
message = first.choices[0].message
print("finish_reason:", first.choices[0].finish_reason)

if not message.tool_calls:
    raise SystemExit(f"The model answered directly, with no tool: {message.content}")

# 2. The model did NOT run anything. It asked us to.
print("\nThe model asked for these tool calls:")
for call in message.tool_calls:
    print(f"  id={call.id}  name={call.function.name}  arguments (a JSON string)={call.function.arguments}")

# 3. We run each tool, and send back one result per call, matched by the call's id.
messages.append(assistant_message(message))          # the request, kept in the history
for call in message.tool_calls:
    result = run_tool(call.function.name, call.function.arguments)
    print(f"\nWe ran {call.function.name} -> {result}")
    messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

print("\nThe history we now send back to the model:")
print(json.dumps(messages, indent=2))

# 4. The model reads the result and answers in plain text.
second = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOL_SPECS)
print("\nFINAL ANSWER:", second.choices[0].message.content)
print(f"[tokens in: first call {first.usage.prompt_tokens}, second call {second.usage.prompt_tokens}]")
