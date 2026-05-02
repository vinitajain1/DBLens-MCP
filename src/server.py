import re
import sqlite3
from typing import Any

from mcp.server.fastmcp import FastMCP

try:
    from src.config import get_instance_path, get_instances
    from src.guardrails import UnsafeQueryError, prepare_read_query
except ModuleNotFoundError:
    from config import get_instance_path, get_instances
    from guardrails import UnsafeQueryError, prepare_read_query


mcp = FastMCP("DBLens MCP")

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_identifier(identifier: str) -> None:
    if not IDENTIFIER_PATTERN.fullmatch(identifier):
        raise ValueError(f"Invalid table_name: {identifier}")


def list_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [row[0] for row in rows]


def get_table_columns(conn: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
    validate_identifier(table_name)

    rows = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    return [
        {
            "table_name": table_name,
            "column_name": row[1],
            "data_type": row[2],
            "is_not_null": bool(row[3]),
            "default_value": row[4],
            "is_primary_key": bool(row[5]),
        }
        for row in rows
    ]


@mcp.tool()
def list_instances() -> dict[str, list[str]]:
    """List configured SQLite database instances."""
    return {"instances": list(get_instances())}


@mcp.tool()
def inspect_schema(instance_id: str, table_name: str | None = None) -> dict[str, Any]:
    """Inspect tables and columns for a configured SQLite database instance."""
    try:
        db_path = get_instance_path(instance_id)
        if table_name:
            validate_identifier(table_name)
    except ValueError as exc:
        return {
            "error": "Invalid schema inspection request",
            "details": str(exc),
            "available_instances": list(get_instances()),
        }

    if not db_path.exists():
        return {
            "error": "Database file not found",
            "instance_id": instance_id,
            "db_path": str(db_path),
        }

    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        tables = list_tables(conn)

        if table_name:
            if table_name not in tables:
                return {
                    "error": "Unknown table_name",
                    "table_name": table_name,
                    "available_tables": tables,
                }
            tables = [table_name]

        columns = []
        for table in tables:
            columns.extend(get_table_columns(conn, table))

    return {
        "instance_id": instance_id,
        "tables": tables,
        "columns": columns,
    }


def to_json_value(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    return str(value)


@mcp.tool()
def execute_read_query(instance_id: str, sql: str) -> dict[str, Any]:
    """Execute a safe read-only SQL query against a configured SQLite database."""
    try:
        db_path = get_instance_path(instance_id)
    except ValueError as exc:
        return {
            "error": "Invalid query request",
            "details": str(exc),
            "available_instances": list(get_instances()),
        }

    if not db_path.exists():
        return {
            "error": "Database file not found",
            "instance_id": instance_id,
            "db_path": str(db_path),
        }

    try:
        safe_sql = prepare_read_query(sql)
    except UnsafeQueryError as exc:
        return {
            "error": "Unsafe SQL rejected",
            "reason": str(exc),
        }

    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(safe_sql).fetchall()
    except sqlite3.Error as exc:
        return {
            "error": "SQL execution failed",
            "details": str(exc),
            "sql_executed": safe_sql,
        }

    json_rows = [
        {key: to_json_value(row[key]) for key in row.keys()}
        for row in rows
    ]

    return {
        "sql_executed": safe_sql,
        "row_count": len(json_rows),
        "rows": json_rows,
    }


if __name__ == "__main__":
    mcp.run()
