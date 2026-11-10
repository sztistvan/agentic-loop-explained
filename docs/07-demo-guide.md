# 7. Demo guide (for presenters)

## The hidden stories in the data (spoilers)

Each generator plants a story for the agent to discover, plus some mess to clean. Both are seeded,
so they produce the same file every time.

### Sales data: `generate_sales_data.py`

One row per order, Jan to Sep 2026 (about 15,000 rows).

- **East** revenue drops about 30% in Q3. Root cause: the **Pro** line had a stockout from
  mid-July (units = 0, status = `backordered`).
- **West** ran a Q3 discount campaign: volume up, margin down.
- Mess to clean: about 40 duplicate rows, missing `channel` values, an `"east "` region typo.

### Factory sensor data: `generate_factory_data.py`

A time series: eight machines on two lines, one reading every five minutes for three weeks
(2026-03-02 to 2026-03-22, about 48,000 rows). Columns: `timestamp`, `machine_id`, `line`, `shift`,
`temperature_c`, `vibration_mm_s`, `pressure_bar`, `power_kw`, `units_produced`, `status`.

- **M06 is failing.** From 12 March its vibration creeps up, from 15 March its temperature follows,
  and it stops on 18 March at 14:35 (`status = fault`) until the repair on 19 March at 06:00.
- **The night shift** (22:00 to 06:00) produces about 18% fewer units than the other shifts.
- **Planned maintenance** every Sunday 06:00 to 08:00 (`status = maintenance`, units = 0).
- Mess to find:
  - a **network outage**: no rows for any machine from 14 March 22:00 to 15 March 02:30;
  - **M03's pressure sensor is stuck** at exactly 6.02 for two days (9 to 11 March);
  - from 20 March **M08 reports temperature in Fahrenheit** although the column says `temperature_c`;
  - 29 missing temperatures on M05, 30 one-off vibration spikes, and 40 duplicated rows.

The factory data is a good second demo because it is a time series and because its biggest trap
(the Fahrenheit readings) makes an agent that skips the consistency check name the wrong machine.

## Suggested flow (about 20 minutes)

1. **Show the building blocks** (2 min): open `prompts/system.md` (instructions, part of the context),
   the tool list in `tools.py`, and the four-block table in [01-concepts.md](01-concepts.md).
   "Reasoning, context, memory, tools: the loop connects them."
2. **Run the manual loop** (3 min): `python agent_manual_loop.py data/sales.csv "Which region
   underperformed in Q3 compared to Q2, and why?"`. Point at the 💭 / ▶ / ◀ lines: think, act, observe,
   and at the header, which records the question and the prompt used. Show `run_agent()`:
   "this loop is the agent".
3. **Show a self-correction** (1 min): when a red `✗ error` appears, say that the traceback goes
   back to the model and it fixes its own code.
4. **Show the token counter** (1 min): per-step `in=` grows; "the history is re-sent every time".
5. **Same thing in LangGraph** (2 min): `agent.py`, then the concept table in
   [03-langgraph-vs-manual.md](03-langgraph-vs-manual.md).
6. **Safety** (2 min): `python agent.py data/sales.csv --approve "..."`. Reject one piece of code with
   feedback.
7. **Quality** (2 min): `--review`. Show the reviewer sending an answer back.
8. **Follow-up** (2 min): interactive mode, then "How much revenue did that cost us? Estimate it."
   Shows memory (same `thread_id`) and the persistent sandbox.
9. **An unknown dataset** (5 min): `python agent.py data/factory_sensors.csv`. Do not say what is
   in it. Use the staged questions from [08-example-questions.md](08-example-questions.md): orient,
   data quality, then "Which machine needs attention?". If the agent names M08 or misses the
   Fahrenheit readings, ask the consistency question and let the audience see the difference.

## Good questions

A ladder for any dataset, plus questions for both sample datasets, is in
[08-example-questions.md](08-example-questions.md). Quick favourites for the sales data:

1. "Which region underperformed in Q3 compared to Q2, and why?"
2. Follow-up: "How much revenue did that cost us? Estimate it."
3. "Did any region trade margin for growth?" (the West discounts)

## What to expect (and say out loud)

The agent is a small model and non-deterministic. On the **sales data**, in recorded runs it:

- reached the right region and the right product line every time;
- once claimed the drop was "not fulfillment related" because backordered revenue is $0, which is a
  faulty inference ([see](02-agentic-loop.md#the-loop-can-be-wrong)), and in another run did notice
  the fulfillment rate drop;
- made small coding mistakes (bare expressions, wrong column keys, a `/mnt/data` path) and fixed
  them from the traceback.

On the **factory data**, in recorded runs it:

- described the columns well and found the duplicates, the missing temperatures and gaps in the
  timestamps, but called the 152.97 °C maximum "extremes or spikes" and missed that it was M08
  reporting in Fahrenheit;
- answered "which machine needs attention" with M08 in one run (fooled by those readings) and M06 in
  a fresh session, so the same question gave different answers;
- found M06's rising vibration when asked for trends (estimating the start as 9 March; the
  planted wear begins on 12 March) and flagged M08's rising temperature, which is really the unit
  change on 20 March.

That is a feature of the demo: it makes the case for tracebacks-as-data, for `--review`, for staged
questions, and for checking an agent's reasoning, not only its numbers.

Full transcripts, all in [transcripts/](transcripts/):

| Transcript | Data | What it shows |
|---|---|---|
| [plain-loop.txt](transcripts/plain-loop.txt) | sales | the plain LangGraph loop, step by step |
| [manual-loop.txt](transcripts/manual-loop.txt) | sales | the hand-written loop, with several self-corrections |
| [plan-review-trim-budget.txt](transcripts/plan-review-trim-budget.txt) | sales | `--plan --review --keep-outputs --max-steps` |
| [approve-and-budget.txt](transcripts/approve-and-budget.txt) | sales | `--approve` with rejections, and a budget running out |
| [factory-explore.txt](transcripts/factory-explore.txt) | factory | exploring an unknown dataset |
| [factory-diagnose.txt](transcripts/factory-diagnose.txt) | factory | one question that gets the wrong machine |
| [factory-followups.txt](transcripts/factory-followups.txt) | factory | a session with follow-up questions |

The four sales transcripts were recorded before the run header existed and with an earlier
version of the system prompt; each carries a note at the top giving the question and flags that
were used. The three factory transcripts were recorded with the current prompt, and their own header
shows the question and the prompt hash. Local file paths in the tracebacks were replaced with
`<project>`.

## Things to try live

| Change | Shows |
|---|---|
| Delete the "explore first" step from `prompts/system.md` | Prompts steer behaviour |
| Remove "bare expressions are NOT echoed" from the `run_python` docstring | Docstrings are prompts; watch more wasted steps |
| `--max-steps 3` | A budget forces a degraded but graceful answer |
| Add the `column_values` tool from [04-tools.md](04-tools.md#adding-your-own-tool) | Tool choice is made by description |
| `--keep-outputs 1` with a long question | The input-token curve flattens |
| Point the agent at your own CSV: `python agent.py your.csv` | The agent is not tied to the sample data |

## Regenerating the data and charts

```bash
python generate_sales_data.py      # data/sales.csv; deterministic (seeded), safe to re-run
python generate_factory_data.py    # data/factory_sensors.csv; accepts --seed N and --out FILE
```

`data/`, `charts/` and `reports/` are git-ignored; they are produced by running the demo.
