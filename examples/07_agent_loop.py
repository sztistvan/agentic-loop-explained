"""
Step 7: the loop. Repeat step 6 until the model answers in plain text. This is an agent.

Step 6 did one round. Here the same thing runs in a loop: ask the model, run the tools it requests,
add the results to the history, ask again. The loop ends when the model replies without a tool call,
or after MAX_STEPS so a confused model cannot run forever.

The default question needs two dependent lookups: first find the customer's orders, then check each.
The model cannot know the order ids up front, so it must use the first result to plan the second call.
Errors come back as results too, so the model can read them and decide what to do next.

Try:
    python examples/07_agent_loop.py
    python examples/07_agent_loop.py "What is the status of order 1001?"    # no such id: see how it reacts to the error
"""
import sys

from client import MODEL, assistant_message, client
from toy_tools import TOOL_SPECS, run_tool

MAX_STEPS = 8
SYSTEM = {"role": "system", "content": "You answer questions about customer orders. Use the tools to look up facts. Do not guess."}

question = " ".join(sys.argv[1:]) or "Is any order for ada@example.com delayed, and why?"
messages = [SYSTEM, {"role": "user", "content": question}]
print("QUESTION:", question)

total_in = 0
for step in range(1, MAX_STEPS + 1):
    response = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOL_SPECS)
    total_in += response.usage.prompt_tokens
    message = response.choices[0].message
    messages.append(assistant_message(message))                 # THINK: the model's turn goes in the history

    if not message.tool_calls:                                  # DECIDE: plain text means it is done
        print(f"\nFINAL ANSWER (after {step} model calls): {message.content}")
        break

    for call in message.tool_calls:                             # ACT: run the tools it asked for
        result = run_tool(call.function.name, call.function.arguments)
        print(f"step {step}: {call.function.name}({call.function.arguments}) -> {result}   [tokens in so far: {response.usage.prompt_tokens}]")
        messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
else:
    print(f"\nStopped: reached MAX_STEPS={MAX_STEPS} without a final answer.")

print(f"[total input tokens: {total_in}   messages in the history: {len(messages)}]")
