"""Generate synthetic Trust & Safety report data (bronze layer, raw CSV).

All data is fake. The output is intentionally a little dirty (duplicates,
inconsistent category spelling) so the silver step has real work to do.
"""
import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

CATEGORIES = ["spam", "harassment", "hate_speech", "scam", "misinformation", "nudity", "violence"]
WEIGHTS = [30, 18, 8, 20, 10, 8, 6]
COUNTRIES = ["DE", "TR", "US", "FR", "GB", "ES", "IT", "PL"]
STATUSES = ["open", "resolved", "escalated"]


def generate_rows(n: int, days: int, seed: int, now: datetime) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        created = now - timedelta(seconds=rng.randint(0, days * 86400))
        category = rng.choices(CATEGORIES, weights=WEIGHTS)[0]
        status = rng.choices(STATUSES, weights=[15, 75, 10])[0]
        resolution = None if status == "open" else round(rng.expovariate(1 / 12), 1)
        # dirty data: inconsistent spelling
        if rng.random() < 0.03:
            category = rng.choice([category.upper(), f" {category} "])
        rows.append({
            "report_id": f"R{i:07d}",
            "created_at": created.strftime("%Y-%m-%d %H:%M:%S"),
            "category": category,
            "severity": rng.choices([1, 2, 3, 4, 5], weights=[25, 30, 25, 15, 5])[0],
            "country": rng.choice(COUNTRIES),
            "status": status,
            "resolution_hours": resolution,
        })
    # dirty data: exact duplicates (~2%)
    rows += rng.sample(rows, k=max(1, n // 50))
    rng.shuffle(rows)
    return rows


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--rows", type=int, default=50_000)
    p.add_argument("--days", type=int, default=60)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default="data/bronze/reports.csv")
    args = p.parse_args()

    rows = generate_rows(args.rows, args.days, args.seed, datetime.now())
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
