import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("nba-postgres")


def get_conn():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set in .env")
    return psycopg2.connect(database_url)


@mcp.tool()
def list_tables() -> str:
    """List all user-created tables in the database."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
                """
            )
            rows = cur.fetchall()
    if not rows:
        return "No tables found."
    return "\n".join(row[0] for row in rows)


@mcp.tool()
def get_schema(table_name: str) -> str:
    """Return column names and types for a given table."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                ORDER BY ordinal_position;
                """,
                (table_name,),
            )
            rows = cur.fetchall()
    if not rows:
        return f"Table '{table_name}' not found or has no columns."
    lines = [f"{col:<30} {dtype}" for col, dtype in rows]
    return "\n".join(lines)


@mcp.tool()
def run_query(sql: str) -> str:
    """Execute a read-only SQL query and return results as a formatted string."""
    sql_stripped = sql.strip().upper()
    if not (sql_stripped.startswith("SELECT") or sql_stripped.startswith("WITH")):
        return "Error: only SELECT queries are allowed."

    with get_conn() as conn:
        conn.set_session(readonly=True)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()

    if not rows:
        return "Query returned no results."

    columns = list(rows[0].keys())
    col_widths = {col: max(len(col), max(len(str(row[col])) for row in rows)) for col in columns}
    header = " | ".join(col.ljust(col_widths[col]) for col in columns)
    separator = "-+-".join("-" * col_widths[col] for col in columns)
    data_lines = [
        " | ".join(str(row[col]).ljust(col_widths[col]) for col in columns)
        for row in rows
    ]
    return "\n".join([header, separator] + data_lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
