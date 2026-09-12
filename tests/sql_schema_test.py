import os


def test_sql_schema_exists():
    path = "data/sql/create_tables.sql"
    assert os.path.exists(path)


def test_sql_schema_not_empty():
    with open("data/sql/create_tables.sql") as f:
        content = f.read().strip()
    assert len(content) > 0


def test_sql_schema_contains_tables():
    with open("data/sql/create_tables.sql") as f:
        content = f.read().lower()
    assert "create table" in content
