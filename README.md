# agentic-loop-explained

A readable tutorial on AI agents: reasoning, context, memory and tools, with a hand-written loop
and a LangGraph version side by side.

The example agent is a data analyst. It answers business questions about a CSV: it profiles the
data, **writes and runs Python**, reads the results, **fixes its own errors**, draws charts and,
on request, saves a report. It is built to teach how an agent works:

- what an agent is made of: **reasoning, context, memory and tools**,
- what the **agentic loop** does, step by step,
- how **state, memory and tools** fit in,
- how a framework (**LangGraph**) expresses the loop, side by side with the same loop written by hand.

```mermaid
flowchart LR
    Q([Question]) --> M[Model]
    M -->|asks for a tool| T[Run the tool]
    T -->|result goes back into the history| M
    M -->|plain text| A([Final answer])
```

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env              # then fill in AZURE_BASE_URL, AZURE_MODEL, AZURE_API_KEY
python generate_sales_data.py     # creates data/sales.csv
python generate_factory_data.py   # creates data/factory_sensors.csv (a time series)

# the data file is always the first argument; any CSV works
python agent.py data/sales.csv "Which region underperformed in Q3 compared to Q2, and why?"
python agent.py data/factory_sensors.csv      # interactive; follow-up questions keep context
python agent_manual_loop.py data/sales.csv "..."   # the same agent with a hand-written loop
```

Charts go to `charts/` and reports to `reports/` inside the project folder, wherever you launch the
command from. Any OpenAI-compatible endpoint works.

Every run starts with a header that records the model, the data file, the system prompt file (with
a short hash of its text), the active flags and your question, so a saved run explains itself.
Colors are shown in a terminal and switched off automatically when output goes to a file.

### Not sure what to ask? Explore an unknown dataset in steps

Start interactive (`python agent.py <your file>.csv`) and ask these one at a time:

1. "What is in this dataset? Explain what each row represents and what each column means."
2. "Check the data quality. What problems do you find, and how would you fix each one?"
3. "How do the key metrics change over time, or across groups? Look for trends and sudden changes."
4. "Take the most important finding and find its cause. What evidence supports it?"

The full ladder, tips, and questions for both sample datasets are in
[docs/08-example-questions.md](docs/08-example-questions.md).

## Where to look

| You want to... | Read |
|---|---|
| Understand the key terms (LLM, agent, agentic loop, workflow, harness, session) and the vocabulary | [docs/01-concepts.md](docs/01-concepts.md) |
| See one real run, message by message | [docs/02-agentic-loop.md](docs/02-agentic-loop.md) |
| Compare the LangGraph and hand-written loops | [docs/03-langgraph-vs-manual.md](docs/03-langgraph-vs-manual.md) |
| Learn how tools are defined and called | [docs/04-tools.md](docs/04-tools.md) |
| Try the optional behaviours (approval, plan, review...) | [docs/05-behaviours.md](docs/05-behaviours.md) |
| Know how the project is built and where state lives | [docs/06-architecture.md](docs/06-architecture.md) |
| Present or extend the demo | [docs/07-demo-guide.md](docs/07-demo-guide.md) |
| Find questions to ask, for any dataset | [docs/08-example-questions.md](docs/08-example-questions.md) |

Suggested reading order for the code: `prompts/system.md` → `tools.py` → `agent_manual_loop.py`
→ `agent.py`.

## Files

| File | Role |
|---|---|
| `prompts/system.md` | The agent's instructions: role and method, free of dataset specifics. Edit it freely. |
| `prompts/planner.md`, `prompts/reviewer.md` | Prompts for the optional `--plan` and `--review` steps. |
| `tools.py` | The three tools (`describe_dataset`, `run_python`, `save_report`) and the sandbox. |
| `agent_manual_loop.py` | The loop in ~20 lines of plain Python. |
| `agent.py` | The same agent as a LangGraph graph, plus optional behaviours. |
| `display.py` | Console output only (no agent logic). |
| `config.py` | Environment, model client, prompt loading. |
| `data/`, `charts/`, `reports/` | Generated data and agent output. Git-ignored. |
| `generate_sales_data.py` | Builds a synthetic sales dataset (rows are orders) with a planted story. |
| `generate_factory_data.py` | Builds a synthetic factory time series (sensor readings every 5 minutes) with a planted story. |

## Optional behaviours (`agent.py` flags, all off by default)

| Flag | What it adds | Concept |
|---|---|---|
| `--approve` | You approve (or reject with feedback) each piece of code before it runs | human-in-the-loop, `interrupt` |
| `--max-steps N` | The model sees its remaining budget; at zero it must answer | loop termination |
| `--plan` | A planning step runs before the first action | plan-then-act |
| `--review` | A reviewer node checks the answer against the evidence | multi-node graphs |
| `--keep-outputs N` | Only the last N tool outputs stay visible to the model | context hygiene |
| `--prompt FILE` | Use a different system prompt | prompts are configuration |

Token usage is always printed. Set `PRICE_INPUT_PER_M` and `PRICE_OUTPUT_PER_M` in `.env` to also
get a cost estimate. Details and real results: [docs/05-behaviours.md](docs/05-behaviours.md).

## Safety note

`run_python` runs model-written code with `exec` inside your own process. That is fine for a local
demo with a dataset you trust, and **not** safe for untrusted input. Use a container or a hosted
sandbox for anything real. Try `--approve` to see every piece of code before it runs.

## License

[MIT](LICENSE) © 2026 István Szatmári

## Models

Tested with Azure OpenAI `gpt-5.4-nano`; `gpt-4o` also works.
Pricing: https://azure.microsoft.com/en-us/pricing/details/azure-openai/
