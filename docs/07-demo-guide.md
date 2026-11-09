# 7. Demo guide (for presenters)

## The hidden story in the data (spoilers)

`generate_data.py` plants a story for the agent to discover:

- **East** revenue drops about 30% in Q3. Root cause: the **Pro** line had a stockout from
  mid-July (units = 0, status = `backordered`).
- **West** ran a Q3 discount campaign: volume up, margin down.
- Mess to clean: about 40 duplicate rows, missing `channel` values, an `"east "` region typo.

## Suggested flow (about 15 minutes)

1. **Show the building blocks** (2 min): open `prompts/system.md` (instructions, part of the context),
   the tool list in `tools.py`, and the four-block table in [01-concepts.md](01-concepts.md).
   "Reasoning, context, memory, tools: the loop connects them."
2. **Run the manual loop** (3 min): `python agent_manual_loop.py "Which region underperformed in Q3
   compared to Q2, and why?"`. Point at the 💭 / ▶ / ◀ lines: think, act, observe. Show
   `run_agent()`: "this loop is the agent".
3. **Show a self-correction** (1 min): when a red `✗ error` appears, say that the traceback goes
   back to the model and it fixes its own code.
4. **Show the token counter** (1 min): per-step `in=` grows; "the history is re-sent every time".
5. **Same thing in LangGraph** (2 min): `agent.py`, then the concept table in
   [03-langgraph-vs-manual.md](03-langgraph-vs-manual.md).
6. **Safety** (2 min): `python agent.py --approve "..."`. Reject one piece of code with feedback.
7. **Quality** (2 min): `--review`. Show the reviewer sending an answer back.
8. **Follow-up** (2 min): interactive mode, then "How much revenue did that cost us? Estimate it."
   Shows memory (same `thread_id`) and the persistent sandbox.

## Good prompts

1. "Which region underperformed in Q3 compared to Q2, and why?"
2. Follow-up: "How much revenue did that cost us? Estimate it."
3. "Did any region trade margin for growth?" (the West discounts)

## What to expect (and say out loud)

The agent is a small model and non-deterministic. In recorded runs it:

- reached the right region and the right product line every time;
- once claimed the drop was "not fulfillment related" because backordered revenue is $0, which is a
  faulty inference ([see](02-agentic-loop.md#the-loop-can-be-wrong)), and in another run did notice
  the fulfillment rate drop;
- made small coding mistakes (bare expressions, wrong column keys, a `/mnt/data` path) and fixed
  them from the traceback.

That is a feature of the demo: it makes the case for tracebacks-as-data, for `--review`, and for
checking an agent's reasoning, not only its numbers. Full transcripts:
[plain loop](transcripts/plain-loop.txt),
[manual loop](transcripts/manual-loop.txt),
[plan + review + budget + trim](transcripts/plan-review-trim-budget.txt),
[approval + budget](transcripts/approve-and-budget.txt).
Local file paths in the tracebacks were replaced with `<project>`.

## Things to try live

| Change | Shows |
|---|---|
| Delete the "explore first" step from `prompts/system.md` | Prompts steer behaviour |
| Remove "bare expressions are NOT echoed" from the `run_python` docstring | Docstrings are prompts; watch more wasted steps |
| `--max-steps 3` | A budget forces a degraded but graceful answer |
| Add the `column_values` tool from [04-tools.md](04-tools.md#adding-your-own-tool) | Tool choice is made by description |
| `--keep-outputs 1` with a long question | The input-token curve flattens |

## Regenerating the data and charts

```bash
python generate_data.py     # deterministic (seeded), safe to re-run
```

`data/`, `charts/` and `reports/` are git-ignored; they are produced by running the demo.
