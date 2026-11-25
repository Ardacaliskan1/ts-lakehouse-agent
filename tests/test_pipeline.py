import csv
from datetime import datetime

import duckdb
from src.build_lakehouse import build
from src.generate_data import generate_rows


def test_generation_is_deterministic():
    now = datetime(2026, 1, 1)
    assert generate_rows(100, 7, 1, now) == generate_rows(100, 7, 1, now)


def test_silver_removes_duplicates_and_normalises(tmp_path):
    rows = generate_rows(500, 14, 7, datetime(2026, 1, 1))
    bronze = tmp_path / "b.csv"
    with bronze.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    silver, gold = str(tmp_path / "silver"), str(tmp_path / "gold.parquet")
    build(str(bronze), silver, gold)
    con = duckdb.connect()
    df = con.execute(f"SELECT report_id, category FROM read_parquet('{silver}/*/*.parquet')").fetchall()
    assert len({r[0] for r in df}) == len(df) == 500
    assert all(c == c.lower().strip() for _, c in df)
