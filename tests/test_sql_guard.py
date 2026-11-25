import pytest
from src.sql_guard import UnsafeSQL, validate


def test_allows_select_and_adds_limit():
    out = validate("SELECT category, count(*) FROM silver_reports GROUP BY 1;")
    assert out.endswith("LIMIT 200")


def test_allows_cte():
    assert validate("WITH a AS (SELECT 1) SELECT * FROM a")


@pytest.mark.parametrize("sql", [
    "DROP TABLE silver_reports",
    "SELECT 1; DROP TABLE x",
    "SELECT * FROM read_csv('/etc/passwd')",
    "COPY silver_reports TO 'x.csv'",
    "",
    "DELETE FROM silver_reports",
])
def test_blocks_unsafe(sql):
    with pytest.raises(UnsafeSQL):
        validate(sql)


def test_comment_cannot_hide_statement():
    with pytest.raises(UnsafeSQL):
        validate("SELECT 1 -- harmless\n; DROP TABLE x")
