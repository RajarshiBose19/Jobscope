"""DuckDB connection helpers."""
from pathlib import Path
import duckdb

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
VIEWS_PATH = Path(__file__).parent / "views.sql"

def open_rw(db_path: Path) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))

def open_ro(db_path: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path), read_only=True)

def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply schema.sql and views.sql. Idempotent (CREATE IF NOT EXISTS / OR REPLACE)."""
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute(VIEWS_PATH.read_text(encoding="utf-8"))
