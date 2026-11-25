"""Natural-language question -> SQL (Claude tool use) -> result -> explanation."""
import os
import sys
from datetime import date

import anthropic
import duckdb
from dotenv import load_dotenv

from src.sql_guard import UnsafeSQL, validate

load_dotenv()
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
MAX_STEPS = 5

SCHEMA = """
Table silver_reports(report_id, created_at TIMESTAMP, report_date DATE, category,
  severity 1-5, country, status in ('open','resolved','escalated'), resolution_hours)
Table gold_daily_kpis(report_date DATE, category, reports, avg_severity,
  resolved_share, avg_resolution_hours)
Categories: spam, harassment, hate_speech, scam, misinformation, nudity, violence.
""".strip()

TOOL = {
    "name": "run_sql",
    "description": "Run a read-only DuckDB SQL SELECT query and return the rows.",
    "input_schema": {
        "type": "object",
        "properties": {"sql": {"type": "string", "description": "A single SELECT query"}},
        "required": ["sql"],
    },
}


def connect() -> duckdb.DuckDBPyConnection:
    """Load Parquet into memory, then lock the connection down."""
    con = duckdb.connect()
    con.execute("CREATE TABLE silver_reports AS "
                "SELECT * FROM read_parquet('data/silver/reports/*/*.parquet', hive_partitioning=true)")
    con.execute("CREATE TABLE gold_daily_kpis AS SELECT * FROM read_parquet('data/gold/daily_kpis.parquet')")
    con.execute("SET enable_external_access=false")
    con.execute("SET lock_configuration=true")
    return con


def run_query(con: duckdb.DuckDBPyConnection, sql: str) -> str:
    safe = validate(sql)
    cur = con.execute(safe)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    lines = [" | ".join(cols)] + [" | ".join(str(v) for v in r) for r in rows]
    return "\n".join(lines)


def ask(question: str) -> str:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return (
            "No ANTHROPIC_API_KEY found. Copy .env.example to .env and add your own key "
            "to run the agent. The data pipeline and tests work without it."
        )
    con = connect()
    client = anthropic.Anthropic()
    system = (
        f"You are a data analyst for a Trust & Safety team. Today is {date.today()}. "
        f"Answer questions by querying the data with run_sql. Schema:\n{SCHEMA}\n"
        "Show the SQL you used, then explain the result briefly. "
        "Never invent numbers; only use query results."
    )
    messages = [{"role": "user", "content": question}]
    for _ in range(MAX_STEPS):
        resp = client.messages.create(
            model=MODEL, max_tokens=1024, system=system, tools=[TOOL], messages=messages
        )
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text")
        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            try:
                out, is_err = run_query(con, block.input["sql"]), False
            except (UnsafeSQL, duckdb.Error) as e:
                out, is_err = f"Error: {e}", True
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": out, "is_error": is_err})
        messages.append({"role": "user", "content": results})
    return "Stopped: too many steps without a final answer."


if __name__ == "__main__":
    print(ask(" ".join(sys.argv[1:]) or "Which category had the most reports last week?"))
