"""Shared pytest fixtures."""
from pathlib import Path
import pytest
import duckdb

FIXTURE_DIR = Path(__file__).parent / "fixtures"

@pytest.fixture
def fresh_duckdb(tmp_path):
    """In-memory DuckDB initialized with our schema."""
    from jobscope.db.connection import init_schema
    db_path = tmp_path / "test.duckdb"
    conn = duckdb.connect(str(db_path))
    init_schema(conn)
    yield conn
    conn.close()
