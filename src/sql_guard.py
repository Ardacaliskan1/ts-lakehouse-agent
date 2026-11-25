"""Validate LLM-generated SQL before it touches the database.

Defence in depth: this guard + an in-memory DuckDB with external access
disabled and configuration locked (see agent.py).
"""
import re

FORBIDDEN = {
    "insert", "update", "delete", "drop", "create", "alter", "attach", "detach",
    "copy", "pragma", "install", "load", "export", "import", "call", "set",
    "read_csv", "read_csv_auto", "read_parquet", "read_json", "glob",
}
MAX_ROWS = 200


class UnsafeSQL(ValueError):
    pass


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    return re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)


def validate(sql: str) -> str:
    """Return a safe, row-limited version of `sql` or raise UnsafeSQL."""
    cleaned = _strip_comments(sql).strip().rstrip(";").strip()
    if not cleaned:
        raise UnsafeSQL("empty query")
    if ";" in cleaned:
        raise UnsafeSQL("only one statement allowed")
    if not re.match(r"(?is)^(select|with)\b", cleaned):
        raise UnsafeSQL("only SELECT queries are allowed")
    words = set(re.findall(r"[a-z_]+", cleaned.lower()))
    bad = words & FORBIDDEN
    if bad:
        raise UnsafeSQL(f"forbidden keyword(s): {', '.join(sorted(bad))}")
    return f"SELECT * FROM ({cleaned}) AS q LIMIT {MAX_ROWS}"
