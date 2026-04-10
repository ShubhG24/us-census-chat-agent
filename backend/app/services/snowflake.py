import logging
import re
import asyncio
import queue
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from datetime import date, datetime
from typing import Any, Optional

import snowflake.connector

from app.config import Settings

logger = logging.getLogger(__name__)

_POOL_SIZE = 4
_POOL_ACQUIRE_TIMEOUT = 5
_LIMIT_RE = re.compile(r'\bLIMIT\b', re.IGNORECASE)


def _convert_value(value: Any) -> Any:
    """Convert Snowflake types to JSON-serializable Python types."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return value


def _convert_row(columns: list[str], row: tuple) -> dict[str, Any]:
    """Convert a row tuple to a JSON-serializable dict."""
    return {col: _convert_value(val) for col, val in zip(columns, row)}


class SnowflakeService:
    """Service for interacting with Snowflake database."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._pool: queue.Queue[snowflake.connector.SnowflakeConnection] = queue.Queue(maxsize=_POOL_SIZE)
        self._pool_initialized = False
        self.schema_cache: dict[str, Any] = {}
        self._schema_summary: Optional[str] = None
        self.executor = ThreadPoolExecutor(max_workers=_POOL_SIZE)
        self._refresh_task: Optional[asyncio.Task] = None

    @property
    def is_healthy(self) -> bool:
        """Thread-safe health check — verifies pool has connections without disturbing it."""
        if not self._pool_initialized:
            return False
        try:
            conn = self._pool.get_nowait()
        except queue.Empty:
            return False
        try:
            healthy = not conn.is_closed()
            return healthy
        except Exception:
            return False
        finally:
            self._release(conn)

    @property
    def connection(self) -> Optional[snowflake.connector.SnowflakeConnection]:
        """Backwards-compat: returns a truthy sentinel when healthy, None otherwise."""
        if not self.is_healthy:
            return None
        try:
            conn = self._pool.get_nowait()
            self._pool.put_nowait(conn)
            return conn
        except queue.Empty:
            return None

    def _create_connection(self) -> snowflake.connector.SnowflakeConnection:
        return snowflake.connector.connect(
            account=self.settings.snowflake_account,
            user=self.settings.snowflake_user,
            password=self.settings.snowflake_password,
            database=self.settings.snowflake_database,
            schema=self.settings.snowflake_schema,
            warehouse=self.settings.snowflake_warehouse,
        )

    def _acquire(self) -> snowflake.connector.SnowflakeConnection:
        """Get a connection from the pool, reconnecting stale ones."""
        try:
            conn = self._pool.get(timeout=_POOL_ACQUIRE_TIMEOUT)
        except queue.Empty:
            raise ConnectionError(
                "All Snowflake connections are busy. Try again shortly."
            )
        try:
            if conn.is_closed():
                conn = self._create_connection()
        except Exception:
            conn = self._create_connection()
        return conn

    def _release(self, conn: snowflake.connector.SnowflakeConnection) -> None:
        """Return a connection to the pool."""
        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            conn.close()

    async def initialize(self) -> None:
        """Initialize connection pool and cache schema metadata."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self.executor, self._init_pool)
        await self.refresh_schema_cache()
        self._refresh_task = asyncio.create_task(
            self._periodic_schema_refresh(self.settings.schema_refresh_minutes)
        )
    
    def _init_pool(self) -> None:
        for _ in range(_POOL_SIZE):
            self._pool.put(self._create_connection())
        self._pool_initialized = True
    
    async def _periodic_schema_refresh(self, interval_minutes: int) -> None:
        """Background task that keeps the schema cache fresh."""
        while True:
            await asyncio.sleep(interval_minutes * 60)
            try:
                await self.refresh_schema_cache()
                logger.info("Schema cache refreshed on schedule")
            except Exception as e:
                logger.warning(f"Scheduled schema refresh failed: {e}")
    
    def close(self) -> None:
        """Drain the pool, cancel background tasks, and shut down the executor."""
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
        self.executor.shutdown(wait=True)
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except Exception:
                pass
        self._pool_initialized = False
    
    async def refresh_schema_cache(self) -> None:
        """Refresh the cached schema information."""
        loop = asyncio.get_running_loop()
        self.schema_cache = await loop.run_in_executor(
            self.executor, self._fetch_schema_info
        )
        self._schema_summary = None
    
    def _fetch_schema_info(self) -> dict[str, Any]:
        """Fetch schema information from Snowflake."""
        if not self._pool_initialized:
            return {}

        conn = self._acquire()
        try:
            return self._fetch_schema_with_conn(conn)
        finally:
            self._release(conn)

    def _fetch_schema_with_conn(self, conn: snowflake.connector.SnowflakeConnection) -> dict[str, Any]:
        schema_info: dict[str, Any] = {
            "tables": [],
            "table_details": {},
            "database": self.settings.snowflake_database,
            "schema": self.settings.snowflake_schema,
        }
        
        db = self.settings.snowflake_database
        schema = self.settings.snowflake_schema
        
        cursor = conn.cursor()
        try:
            cursor.execute(f'USE DATABASE "{db}"')
            cursor.execute(f'USE SCHEMA "{schema}"')
            
            logger.info(f"Connected to database: {db}, schema: {schema}")
            
            cursor.execute(
                f'SELECT TABLE_NAME, TABLE_TYPE, ROW_COUNT, COMMENT '
                f'FROM "{db}".INFORMATION_SCHEMA.TABLES '
                f'WHERE TABLE_SCHEMA = %s '
                f'AND TABLE_TYPE = %s '
                f'ORDER BY TABLE_NAME',
                (schema, 'BASE TABLE'),
            )
            
            tables = cursor.fetchall()
            logger.info(f"Found {len(tables)} tables in {db}.{schema}")

            def _is_key_table(name: str) -> bool:
                if "GEOMETRY" in name or "PATTERNS" in name:
                    return False
                if "_CBG_B" in name or "_CBG_C" in name:
                    return True
                if "METADATA" in name or "REDISTRICTING" in name:
                    return True
                return False

            def _should_fetch_columns(name: str) -> bool:
                core = {
                    "B01", "B02", "B03",        # Population, Race, Hispanic
                    "B08", "B11",                # Commuting, Household Type
                    "B15", "B17", "B19",         # Education, Poverty (family), Income
                    "B23", "B25", "B27",         # Employment, Housing, Health Insurance
                    "C17",                       # Individual Poverty Ratio
                }
                if "METADATA" in name and "FIELD_DESCRIPTIONS" not in name:
                    return True
                for c in core:
                    if f"_CBG_{c}" in name:
                        return True
                return False

            tables_to_fetch_columns = []
            for table in tables:
                table_name = table[0]
                is_key_table = _is_key_table(table_name)
                
                table_entry = {
                    "name": table_name,
                    "type": table[1],
                    "row_count": table[2],
                    "comment": table[3],
                    "is_key_table": is_key_table
                }
                schema_info["tables"].append(table_entry)
                
                if _should_fetch_columns(table_name):
                    tables_to_fetch_columns.append(table_name)

            if tables_to_fetch_columns:
                placeholders = ", ".join(["%s"] * len(tables_to_fetch_columns))
                cursor.execute(
                    f'SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, ORDINAL_POSITION '
                    f'FROM "{db}".INFORMATION_SCHEMA.COLUMNS '
                    f'WHERE TABLE_SCHEMA = %s '
                    f'AND TABLE_NAME IN ({placeholders}) '
                    f'ORDER BY TABLE_NAME, ORDINAL_POSITION',
                    (schema, *tables_to_fetch_columns),
                )
                
                all_columns = cursor.fetchall()
                
                from collections import defaultdict
                columns_by_table: dict[str, list] = defaultdict(list)
                for row in all_columns:
                    tbl, col_name, dtype, nullable, _ = row
                    columns_by_table[tbl].append({
                        "name": col_name,
                        "type": dtype,
                        "nullable": nullable == "YES",
                    })
                
                for tbl, cols in columns_by_table.items():
                    limit = 200 if "_CBG_B25" in tbl else 120
                    schema_info["table_details"][tbl] = {"columns": cols[:limit]}
            
            logger.info(f"Schema cache populated with {len(schema_info['tables'])} tables")
            return schema_info
            
        except Exception as e:
            logger.exception(f"Error fetching schema: {e}")
            return {}
        finally:
            cursor.close()
    
    def _ensure_limit(self, query: str) -> str:
        """Wrap the query with a LIMIT if one isn't already present,
        so Snowflake doesn't scan unbounded rows on wide tables."""
        if _LIMIT_RE.search(query):
            return query
        limit = self.settings.max_result_rows
        return f"SELECT * FROM ({query.rstrip().rstrip(';')}) AS __q LIMIT {limit}"

    async def execute_query(
        self, 
        query: str, 
        timeout: Optional[int] = None
    ) -> dict[str, Any]:
        """Execute a SQL query and return results."""
        if not self._pool_initialized:
            raise ConnectionError("Snowflake connection not established")
        
        timeout = timeout or self.settings.query_timeout_seconds
        safe_query = self._ensure_limit(query)
        loop = asyncio.get_running_loop()
        
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    self.executor, 
                    lambda: self._execute_query_sync(safe_query)
                ),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Query timed out after {timeout} seconds. Try a simpler query.",
                "data": None,
                "columns": None,
                "row_count": 0
            }
    
    def _execute_query_sync(self, query: str) -> dict[str, Any]:
        """Synchronous query execution — each call gets its own pooled connection."""
        conn = self._acquire()
        try:
            cursor = conn.cursor()
            try:
                cursor.execute(query)
                
                rows = cursor.fetchmany(self.settings.max_result_rows)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                
                has_more = len(rows) == self.settings.max_result_rows
                
                data = [_convert_row(columns, row) for row in rows]
                
                return {
                    "success": True,
                    "error": None,
                    "data": data,
                    "columns": columns,
                    "row_count": len(rows),
                    "has_more": has_more
                }
                
            except Exception as e:
                logger.error(f"Query execution error: {e}")
                safe_error = str(e).split('\n')[0][:200]
                return {
                    "success": False,
                    "error": f"Query failed: {safe_error}",
                    "data": None,
                    "columns": None,
                    "row_count": 0
                }
            finally:
                cursor.close()
        finally:
            self._release(conn)
    
    def get_schema_summary(self) -> str:
        """Get a formatted summary of the schema for LLM context (cached)."""
        if not self.schema_cache:
            return "Schema information not available."
        if self._schema_summary is not None:
            return self._schema_summary

        db = self.schema_cache.get("database", "")
        schema = self.schema_cache.get("schema", "PUBLIC")
        
        lines = [
            f"## Database: {db}",
            f"## Schema: {schema}",
            "",
            "### Key Tables for Analysis:",
            ""
        ]
        
        for table in self.schema_cache.get("tables", []):
            if not table.get("is_key_table"):
                continue
                
            table_name = table["name"]
            row_count = table.get("row_count", "unknown")
            
            lines.append(f'**"{table_name}"**')
            lines.append(f"- Rows: {row_count:,}" if isinstance(row_count, int) else f"- Rows: {row_count}")

            details = self.schema_cache.get("table_details", {}).get(table_name, {})
            cols = details.get("columns", [])
            if cols:
                names = [c["name"] for c in cols]
                max_show = 30
                shown = names[:max_show]
                more = len(names) - max_show
                col_line = ", ".join(f'"{n}"' for n in shown)
                if more > 0:
                    col_line += f" … (+{more} more)"
                lines.append(f"- Columns: {col_line}")

            lines.append("")
        
        other_tables = [t["name"] for t in self.schema_cache.get("tables", []) if not t.get("is_key_table")]
        if other_tables:
            lines.append("### Other Available Tables:")
            lines.append(", ".join(f'"{t}"' for t in other_tables[:20]))
            if len(other_tables) > 20:
                lines.append(f"... and {len(other_tables) - 20} more")
        
        self._schema_summary = "\n".join(lines)
        return self._schema_summary

    def get_table_names(self) -> list[str]:
        """Get list of available table names."""
        return [t["name"] for t in self.schema_cache.get("tables", [])]
