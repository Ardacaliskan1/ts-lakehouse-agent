"""Bronze (raw CSV) -> Silver (clean, partitioned Parquet) -> Gold (daily KPIs)."""
import shutil
from pathlib import Path

import duckdb

BRONZE = "data/bronze/reports.csv"
SILVER = "data/silver/reports"
GOLD = "data/gold/daily_kpis.parquet"


def build(bronze: str = BRONZE, silver: str = SILVER, gold: str = GOLD) -> None:
    con = duckdb.connect()
    for p in (silver, gold):
        path = Path(p)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
        path.parent.mkdir(parents=True, exist_ok=True)

    con.execute(f"CREATE TABLE bronze AS SELECT * FROM read_csv_auto('{bronze}')")

    # Silver: dedupe on report_id, normalise category, typed columns
    con.execute("""
        CREATE TABLE silver AS
        SELECT DISTINCT ON (report_id)
            report_id,
            CAST(created_at AS TIMESTAMP)      AS created_at,
            CAST(created_at AS DATE)           AS report_date,
            lower(trim(category))              AS category,
            CAST(severity AS TINYINT)          AS severity,
            country,
            status,
            resolution_hours
        FROM bronze
        ORDER BY report_id, created_at
    """)
    con.execute(f"COPY silver TO '{silver}' (FORMAT PARQUET, PARTITION_BY (report_date))")

    # Gold: aggregated KPIs per day and category
    con.execute(f"""
        COPY (
            SELECT
                report_date,
                category,
                count(*)                                         AS reports,
                round(avg(severity), 2)                          AS avg_severity,
                round(avg((status = 'resolved')::INTEGER), 3)    AS resolved_share,
                round(avg(resolution_hours), 1)                  AS avg_resolution_hours
            FROM silver
            GROUP BY report_date, category
            ORDER BY report_date, category
        ) TO '{gold}' (FORMAT PARQUET)
    """)
    n_b = con.execute("SELECT count(*) FROM bronze").fetchone()[0]
    n_s = con.execute("SELECT count(*) FROM silver").fetchone()[0]
    print(f"bronze={n_b} rows, silver={n_s} rows ({n_b - n_s} duplicates removed)")


if __name__ == "__main__":
    build()
