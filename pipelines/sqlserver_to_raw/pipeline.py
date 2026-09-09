from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg import sql

from pipelines.sqlserver_to_raw.manifest import (
    TableMapping,
    load_manifest,
    select_tables,
)
from shared.audit import RunContext, finish_table_run, start_table_run
from shared.config import Settings
from shared.db_postgres import get_pg_connection, get_pg_engine
from shared.db_sqlserver import get_mssql_connection


@dataclass(frozen=True)
class TableLoadResult:
    rows_in: int
    rows_out: int


class RawLoadError(RuntimeError):
    pass


def quote_mssql(identifier: str) -> str:
    return f"[{identifier.replace(']', ']]')}]"


def build_source_select(table: TableMapping, *, empty: bool = False) -> str:
    columns = ", ".join(quote_mssql(column.source) for column in table.columns)
    top = "TOP (0) " if empty else ""
    return (
        f"SELECT {top}{columns} FROM "
        f"{quote_mssql(table.source_schema)}.{quote_mssql(table.source_table)}"
    )


def validate_target(pg_cursor: Any, target_schema: str, table: TableMapping) -> None:
    pg_cursor.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_schema = %s AND table_name = %s
        """,
        (target_schema, table.target_table),
    )
    actual = {str(row[0]) for row in pg_cursor.fetchall()}
    required = {column.target for column in table.columns} | {
        "_etl_batch_id",
        "_etl_source_database",
        "_etl_source_schema",
        "_etl_source_table",
    }
    missing = sorted(required - actual)
    if missing:
        raise RawLoadError(
            f"Destino {target_schema}.{table.target_table} inexistente o incompleto; "
            f"faltan columnas: {', '.join(missing)}"
        )


def load_table(
    source_connection: Any,
    pg_connection: Any,
    *,
    table: TableMapping,
    target_schema: str,
    source_database: str,
    batch_id: str,
    chunk_size: int,
    dry_run: bool,
) -> TableLoadResult:
    if chunk_size < 1:
        raise ValueError("chunk_size debe ser mayor que cero")

    source_cursor = source_connection.cursor()
    source_cursor.arraysize = chunk_size
    source_cursor.execute(build_source_select(table, empty=dry_run))

    with pg_connection.cursor() as pg_cursor:
        validate_target(pg_cursor, target_schema, table)
        if dry_run:
            pg_connection.rollback()
            return TableLoadResult(rows_in=0, rows_out=0)

        target = sql.SQL("{}.{}").format(
            sql.Identifier(target_schema), sql.Identifier(table.target_table)
        )
        pg_cursor.execute(sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY").format(target))

        target_columns = [column.target for column in table.columns] + [
            "_etl_batch_id",
            "_etl_source_database",
            "_etl_source_schema",
            "_etl_source_table",
        ]
        copy_statement = sql.SQL("COPY {} ({}) FROM STDIN").format(
            target,
            sql.SQL(", ").join(sql.Identifier(name) for name in target_columns),
        )

        rows_in = 0
        with pg_cursor.copy(copy_statement) as copy:
            while batch := source_cursor.fetchmany(chunk_size):
                for source_row in batch:
                    copy.write_row(
                        tuple(source_row)
                        + (
                            batch_id,
                            source_database,
                            table.source_schema,
                            table.source_table,
                        )
                    )
                rows_in += len(batch)

        pg_cursor.execute(
            sql.SQL("SELECT count(*) FROM {} WHERE {} = %s").format(
                target, sql.Identifier("_etl_batch_id")
            ),
            (batch_id,),
        )
        rows_out = int(pg_cursor.fetchone()[0])
        if rows_in != rows_out:
            raise RawLoadError(
                f"Conteo inconsistente en {table.source_key}: "
                f"origen={rows_in}, raw={rows_out}"
            )

    pg_connection.commit()
    return TableLoadResult(rows_in=rows_in, rows_out=rows_out)


def run(ctx: RunContext, settings: Settings) -> tuple[int, int]:
    manifest = load_manifest()
    requested = [str(value) for value in ctx.options.get("tables", [])]
    tables = select_tables(manifest, requested)
    chunk_size = int(ctx.options.get("chunk_size", 10_000))
    continue_on_error = bool(ctx.options.get("continue_on_error", False))
    dry_run = bool(ctx.options.get("dry_run", False))

    audit_engine = get_pg_engine(settings.postgres)
    source_connection = get_mssql_connection(settings.sqlserver)
    pg_connection = get_pg_connection(settings.postgres)
    total_in = 0
    total_out = 0
    failures: list[str] = []

    try:
        for position, table in enumerate(tables, start=1):
            batch_id = f"{ctx.run_id}:{table.target_table}"
            start_table_run(
                audit_engine,
                ctx,
                source_schema=table.source_schema,
                source_table=table.source_table,
                target_schema=manifest.target_schema,
                target_table=table.target_table,
                batch_id=batch_id,
            )
            print(
                f"[sqlserver_to_raw] {position}/{len(tables)} "
                f"{table.source_key} -> {manifest.target_schema}.{table.target_table}"
            )
            try:
                result = load_table(
                    source_connection,
                    pg_connection,
                    table=table,
                    target_schema=manifest.target_schema,
                    source_database=settings.sqlserver.db,
                    batch_id=batch_id,
                    chunk_size=chunk_size,
                    dry_run=dry_run,
                )
            except Exception as exc:
                pg_connection.rollback()
                finish_table_run(
                    audit_engine,
                    ctx,
                    source_schema=table.source_schema,
                    source_table=table.source_table,
                    status="FAILED",
                    error=str(exc),
                )
                failures.append(f"{table.source_key}: {exc}")
                if not continue_on_error:
                    raise
                continue

            total_in += result.rows_in
            total_out += result.rows_out
            finish_table_run(
                audit_engine,
                ctx,
                source_schema=table.source_schema,
                source_table=table.source_table,
                status="VALIDATED" if dry_run else "SUCCESS",
                rows_in=result.rows_in,
                rows_out=result.rows_out,
            )
    finally:
        source_connection.close()
        pg_connection.close()

    if failures:
        preview = "; ".join(failures[:5])
        suffix = f"; y {len(failures) - 5} más" if len(failures) > 5 else ""
        raise RawLoadError(f"Fallaron {len(failures)} tabla(s): {preview}{suffix}")

    print(
        f"[sqlserver_to_raw] run_id={ctx.run_id} tablas={len(tables)} "
        f"rows_in={total_in} rows_out={total_out} dry_run={dry_run}"
    )
    return total_in, total_out
