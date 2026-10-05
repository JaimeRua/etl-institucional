from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import create_engine, text

from pipelines.raw_to_stg_matricula.pipeline import (
    ensure_ddl,
    load_matrix,
    load_stage,
)
from shared.audit import RunContext, finish_run, init_schema, start_run

pytestmark = pytest.mark.integration
RAW_DDL_PATH = (
    Path(__file__).resolve().parents[2]
    / "pipelines"
    / "sqlserver_to_raw"
    / "sql"
    / "001_create_raw_tables.sql"
)


@pytest.fixture
def pg_dsn() -> str:
    value = os.getenv("TEST_PG_DSN")
    if not value:
        pytest.skip("TEST_PG_DSN no está configurado")
    return value


@pytest.fixture
def clean_postgres(pg_dsn: str):
    connection = psycopg.connect(pg_dsn)
    if not connection.info.dbname.endswith("_test"):
        connection.close()
        pytest.fail("La prueba de integración requiere una base terminada en _test")
    with connection.cursor() as cursor:
        cursor.execute("DROP SCHEMA IF EXISTS audit CASCADE")
        cursor.execute("DROP SCHEMA IF EXISTS stg CASCADE")
        cursor.execute("DROP SCHEMA IF EXISTS raw CASCADE")
    connection.commit()
    try:
        yield connection
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS audit CASCADE")
            cursor.execute("DROP SCHEMA IF EXISTS stg CASCADE")
            cursor.execute("DROP SCHEMA IF EXISTS raw CASCADE")
        connection.commit()
        connection.close()


def test_audit_run_lifecycle(pg_dsn: str, clean_postgres) -> None:
    engine = create_engine(pg_dsn)
    ctx = RunContext(
        run_id=str(uuid.uuid4()),
        pipeline="integration_test",
        env="test",
        git_sha="test-sha",
    )

    init_schema(engine)
    start_run(engine, ctx)
    finish_run(engine, ctx.run_id, "SUCCESS", rows_in=2, rows_out=2)

    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT status, rows_in, rows_out "
                "FROM audit.etl_run WHERE run_id=:run_id"
            ),
            {"run_id": ctx.run_id},
        ).one()
    engine.dispose()

    assert tuple(row) == ("SUCCESS", 2, 2)


def test_raw_ddl_executes_and_creates_the_complete_inventory(clean_postgres) -> None:
    connection = clean_postgres
    with connection.cursor() as cursor:
        cursor.execute(RAW_DDL_PATH.read_text(encoding="utf-8"))
        cursor.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'raw' AND table_type = 'BASE TABLE'"
        )
        assert int(cursor.fetchone()[0]) == 138
    connection.commit()


def test_raw_to_stg_separates_valid_and_rejected_rows(clean_postgres) -> None:
    connection = clean_postgres
    matrix = load_matrix()
    source_columns = ",\n".join(f'"{column.source}" text' for column in matrix.columns)
    with connection.cursor() as cursor:
        cursor.execute("CREATE SCHEMA raw")
        cursor.execute(
            f"""
            CREATE TABLE raw.bi_mat_sies_reporte (
                {source_columns},
                _etl_ingestion_id bigint PRIMARY KEY,
                _etl_batch_id text,
                _etl_loaded_at timestamptz NOT NULL,
                _etl_row_hash text
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO raw.bi_mat_sies_reporte (
                ano, total_matricula, cobertura_tes,
                _etl_ingestion_id, _etl_batch_id, _etl_loaded_at, _etl_row_hash
            ) VALUES
                ('2025', '10', '85,5', 1, 'batch-1', %s, 'hash-1'),
                ('1800', '-1', '101', 2, 'batch-1', %s, 'hash-2')
            """,
            (datetime.now(timezone.utc), datetime.now(timezone.utc)),
        )
    connection.commit()

    ensure_ddl(connection)
    result = load_stage(
        connection,
        matrix=matrix,
        run_id="integration-run",
        dry_run=False,
    )

    assert (result.rows_in, result.rows_out, result.rows_rejected) == (2, 1, 1)
    with connection.cursor() as cursor:
        cursor.execute("SELECT ano, total_matricula FROM stg.matricula_sies")
        assert cursor.fetchone() == (2025, 10)
        cursor.execute(
            "SELECT cardinality(errores) "
            "FROM stg.matricula_sies_rechazos "
            "WHERE _stg_run_id = 'integration-run'"
        )
        assert int(cursor.fetchone()[0]) == 3
