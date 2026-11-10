"""
The agent's tools, plus the sandbox the code-running tool uses.

WHAT IS A TOOL?
A tool is an ordinary Python function that the model may ask us to call.
The @tool decorator turns three things into the contract the model sees:

    function name      -> the tool's name
    docstring          -> the tool's description (this is how the model decides
                          WHEN and HOW to use it, so write it for the model)
    type hints         -> the JSON schema of the arguments

The model never runs anything itself. It replies with a *tool call*
("call run_python with code=..."), our program runs the function, and the
return value is sent back as a *tool result* message.

Three tools, from most general to most specific:

    run_python        powerful and open-ended (any pandas / matplotlib code)
    describe_dataset  narrow, safe, read-only, deterministic
    save_report       a side effect (writes a file), used only when the user asks
"""
from __future__ import annotations

import contextlib
import io
import os
import re
import traceback
import warnings
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: charts are saved to files, never shown

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from langchain_core.tools import tool
from matplotlib.figure import Figure

# Outputs go next to this file, NOT into the current working directory. A relative
# Path("charts") would land wherever you happened to launch the command from.
PROJECT_ROOT = Path(__file__).resolve().parent
CHART_DIR = PROJECT_ROOT / "charts"
REPORT_DIR = PROJECT_ROOT / "reports"
MAX_OUTPUT_CHARS = 6_000  # keep tool results small so the context stays lean

# ---------------------------------------------------------------------------
# Sandbox: a persistent Python namespace shared across run_python calls,
# like a Jupyter kernel. Variables created in one step survive to the next.
#
# NOTE: this runs model-written code in-process with exec(). Fine for a demo;
# use a real sandbox (container, E2B, ...) for anything untrusted.
# ---------------------------------------------------------------------------
NAMESPACE: dict = {}
_raw_df: pd.DataFrame | None = None  # untouched copy, used by describe_dataset


# Guardrail: charts may only be written inside CHART_DIR.
# Asking the model nicely (in the prompt) is not enough: once it saved a chart to "../charts/"
# and it landed outside the project. This check turns a wrong path into an error message that
# the model reads and fixes on its next turn, like any other error in run_python.
_original_savefig = Figure.savefig


def _checked_savefig(self, fname, *args, **kwargs):
    if isinstance(fname, (str, os.PathLike)):
        target = Path(os.path.abspath(fname))
        if CHART_DIR.resolve() not in target.resolve().parents:
            raise ValueError(
                f"Chart not saved: {str(fname)!r} is outside the charts folder. "
                "Save inside CHART_DIR, for example "
                "plt.savefig(f'{CHART_DIR}/<name>.png', dpi=150, bbox_inches='tight')"
            )
    return _original_savefig(self, fname, *args, **kwargs)


Figure.savefig = _checked_savefig

# What the current run is about. The agents fill it in; save_report writes it into the
# report header, so the exact question and data file are recorded by code, not by the model.
RUN_CONTEXT: dict = {"dataset": "", "question": ""}


def set_question(question: str) -> None:
    """Called by the agent loop at the start of every question."""
    RUN_CONTEXT["question"] = question


def load_dataset(csv_path: str) -> None:
    """Load the CSV and (re)build the sandbox namespace."""
    global _raw_df
    CHART_DIR.mkdir(exist_ok=True)
    RUN_CONTEXT["dataset"] = str(csv_path)
    _raw_df = pd.read_csv(csv_path)
    NAMESPACE.clear()
    NAMESPACE.update(
        pd=pd,
        np=np,
        plt=plt,
        df=_raw_df.copy(),  # the model may modify its own copy freely
        CHART_DIR=str(CHART_DIR),
    )


# ---------------------------------------------------------------------------
# Tool 1: run_python  (general purpose)
# ---------------------------------------------------------------------------
@tool
def run_python(code: str) -> str:
    """Execute Python code in a persistent session and return its printed output.

    - A pandas DataFrame `df` is preloaded with the raw dataset.
    - pd, np and plt are already imported. Variables persist between calls.
    - Use print() to see results; bare expressions are NOT echoed.
    - Save charts with plt.savefig(f"{CHART_DIR}/<descriptive_name>.png", dpi=150,
      bbox_inches="tight") and then plt.close(). Always use CHART_DIR: saving anywhere
      else fails with an error. Saved charts are listed as "[charts saved: charts/<name>.png]".
    - If the code raises, the full traceback is returned so you can fix it.
    """
    charts_before = set(CHART_DIR.glob("*.png"))
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            exec(code, NAMESPACE)
        result = buffer.getvalue() or "(code ran successfully, nothing was printed)"
    except Exception:
        # Errors are returned as ordinary text, NOT raised. The model reads the
        # traceback on its next turn and fixes its own code. This is the
        # self-correction mechanism of the whole agent.
        result = buffer.getvalue() + "\nERROR:\n" + traceback.format_exc(limit=3)

    new_charts = sorted(set(CHART_DIR.glob("*.png")) - charts_before)
    if new_charts:
        # Report paths relative to the project: short for the model, and portable.
        result += "\n[charts saved: " + ", ".join(c.relative_to(PROJECT_ROOT).as_posix() for c in new_charts) + "]"

    if len(result) > MAX_OUTPUT_CHARS:
        result = result[:MAX_OUTPUT_CHARS] + "\n...[output truncated -- print less]"
    return result


# ---------------------------------------------------------------------------
# Tool 2: describe_dataset  (narrow, safe, deterministic)
# ---------------------------------------------------------------------------
def _time_range(s: pd.Series) -> str:
    """If a text column holds timestamps, return ', time range A to B, typical step X'."""
    if pd.api.types.is_numeric_dtype(s):
        return ""
    values = s.dropna()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sample = pd.to_datetime(values.iloc[:100], errors="coerce")
        if len(sample) == 0 or sample.notna().mean() < 0.9:
            return ""  # not a date column
        stamps = pd.to_datetime(values, errors="coerce").dropna()
    unique = stamps.drop_duplicates().sort_values()
    out = f", time range {unique.iloc[0]} to {unique.iloc[-1]}"
    if len(unique) > 1:
        out += f", typical step {unique.diff().median()}"
    return out



@tool
def describe_dataset() -> str:
    """Profile the raw dataset: size, duplicates, and per-column dtype, nulls,
    distinct values, ranges and top categories, plus a few sample rows.
    Takes no arguments and never modifies anything. Call this FIRST."""
    df = _raw_df
    if df is None:
        return "ERROR: no dataset loaded."
    lines = [
        f"Rows: {len(df):,}   Columns: {df.shape[1]}",
        f"Exact duplicate rows: {int(df.duplicated().sum())}",
        "",
        "Columns:",
    ]
    for col in df.columns:
        s = df[col]
        line = f"- {col} ({s.dtype}): {int(s.isna().sum())} nulls, {s.nunique()} distinct"
        if pd.api.types.is_numeric_dtype(s):
            line += f", min={s.min():g}, mean={s.mean():.2f}, max={s.max():g}"
        elif s.nunique() <= 12:
            line += ", values=" + str(s.value_counts(dropna=False).to_dict())
        else:
            line += f", e.g. {s.dropna().iloc[:3].tolist()}"
            line += _time_range(s)
        lines.append(line)
    lines += ["", "First 3 rows:", df.head(3).to_string(index=False)]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 3: save_report  (a side effect)
# ---------------------------------------------------------------------------
@tool
def save_report(title: str, markdown: str) -> str:
    """Save the analysis as a Markdown report in reports/ and return its path.

    Call this ONLY if the user asked for a report or a written summary, and call it once,
    after the analysis is finished.

    - `title`: short report title (also used for the file name).
    - `markdown`: the report body. Reference charts as ![caption](charts/<name>.png),
      using the same path that run_python printed in "[charts saved: ...]".
    The user's question, the data file and the date are added to the top automatically,
    so do not repeat them.
    """
    REPORT_DIR.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "report"
    path = REPORT_DIR / f"{slug}.md"
    # The model uses ONE path form for charts everywhere (charts/<name>.png). The report sits one
    # folder below the project root, so the links inside it need a "../": added here, by code,
    # instead of asking the model to remember a second form (that is what caused the bug).
    markdown = re.sub(r"\]\((?:\.\./)?charts/", "](../charts/", markdown)
    question =RUN_CONTEXT["question"].strip().replace("\n", "\n> ")
    header = (
        f"> **Question:** {question}\n>\n"
        f"> **Data file:** {RUN_CONTEXT['dataset']}  \n"
        f"> **Generated:** {datetime.now():%Y-%m-%d %H:%M}"
    )
    path.write_text(f"# {title}\n\n{header}\n\n{markdown}\n", encoding="utf-8")
    return f"Report saved to {path.relative_to(PROJECT_ROOT).as_posix()}"


# The list handed to the model (and to the tool-running node / manual loop).
TOOLS = [describe_dataset, run_python, save_report]
