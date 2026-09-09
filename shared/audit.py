from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass
class RunContext:
    run_id: str
    pipeline: str
    env: str
    git_sha: str
    options: dict[str, Any] = field(default_factory=dict)


def init_schema(engine: Engine) -> None:
    with engine.begin() as cxn:
        cxn.execute(text("CREATE SCHEMA IF NOT EXISTS audit"))
        cxn.execute(
            text("""
            DO $migration$
            BEGIN
              IF to_regclass('audit.etl_run') IS NULL
                 AND to_regclass('public.etl_run') IS NOT NULL THEN
                ALTER TABLE public.etl_run SET SCHEMA audit;
              END IF;

              IF to_regclass('audit.etl_table_run') IS NULL
                 AND to_regclass('public.etl_table_run') IS NOT NULL THEN
                ALTER TABLE public.etl_table_run SET SCHEMA audit;
              END IF;
            END
            $migration$;
            """)
        )
        cxn.execute(
            text("""
        CREATE TABLE IF NOT EXISTS audit.etl_run (
          run_id TEXT PRIMARY KEY,
          pipeline TEXT NOT NULL,
          env TEXT NOT NULL,
          git_sha TEXT NOT NULL,
          started_at TIMESTAMPTZ NOT NULL,
          finished_at TIMESTAMPTZ NULL,
          status TEXT NOT NULL,
          rows_in BIGINT DEFAULT 0,
          rows_out BIGINT DEFAULT 0,
          error TEXT NULL
        );
        """)
        )
        cxn.execute(
            text("""
        CREATE TABLE IF NOT EXISTS audit.etl_table_run (
          run_id TEXT NOT NULL REFERENCES audit.etl_run(run_id),
          source_schema TEXT NOT NULL,
          source_table TEXT NOT NULL,
          target_schema TEXT NOT NULL,
          target_table TEXT NOT NULL,
          batch_id TEXT NOT NULL,
          started_at TIMESTAMPTZ NOT NULL,
          finished_at TIMESTAMPTZ NULL,
          status TEXT NOT NULL,
          rows_in BIGINT DEFAULT 0,
          rows_out BIGINT DEFAULT 0,
          error TEXT NULL,
          PRIMARY KEY (run_id, source_schema, source_table)
        );
        """)
        )


def start_run(engine: Engine, ctx: RunContext) -> None:
    with engine.begin() as cxn:
        cxn.execute(
            text("""
          INSERT INTO audit.etl_run(run_id,pipeline,env,git_sha,started_at,status)
          VALUES (:run_id,:pipeline,:env,:git_sha,:started_at,'RUNNING')
        """),
            {
                "run_id": ctx.run_id,
                "pipeline": ctx.pipeline,
                "env": ctx.env,
                "git_sha": ctx.git_sha,
                "started_at": datetime.now(timezone.utc),
            },
        )


def finish_run(
    engine: Engine,
    run_id: str,
    status: str,
    rows_in: int = 0,
    rows_out: int = 0,
    error: str | None = None,
) -> None:
    with engine.begin() as cxn:
        cxn.execute(
            text("""
          UPDATE audit.etl_run
          SET finished_at=:finished_at, status=:status, rows_in=:rows_in, rows_out=:rows_out, error=:error
          WHERE run_id=:run_id
        """),
            {
                "finished_at": datetime.now(timezone.utc),
                "status": status,
                "rows_in": rows_in,
                "rows_out": rows_out,
                "error": error,
                "run_id": run_id,
            },
        )


def start_table_run(
    engine: Engine,
    ctx: RunContext,
    *,
    source_schema: str,
    source_table: str,
    target_schema: str,
    target_table: str,
    batch_id: str,
) -> None:
    with engine.begin() as cxn:
        cxn.execute(
            text("""
              INSERT INTO audit.etl_table_run(
                run_id, source_schema, source_table, target_schema, target_table,
                batch_id, started_at, status
              ) VALUES (
                :run_id, :source_schema, :source_table, :target_schema, :target_table,
                :batch_id, :started_at, 'RUNNING'
              )
            """),
            {
                "run_id": ctx.run_id,
                "source_schema": source_schema,
                "source_table": source_table,
                "target_schema": target_schema,
                "target_table": target_table,
                "batch_id": batch_id,
                "started_at": datetime.now(timezone.utc),
            },
        )


def finish_table_run(
    engine: Engine,
    ctx: RunContext,
    *,
    source_schema: str,
    source_table: str,
    status: str,
    rows_in: int = 0,
    rows_out: int = 0,
    error: str | None = None,
) -> None:
    with engine.begin() as cxn:
        cxn.execute(
            text("""
              UPDATE audit.etl_table_run
                 SET finished_at=:finished_at, status=:status,
                     rows_in=:rows_in, rows_out=:rows_out, error=:error
               WHERE run_id=:run_id
                 AND source_schema=:source_schema
                 AND source_table=:source_table
            """),
            {
                "finished_at": datetime.now(timezone.utc),
                "status": status,
                "rows_in": rows_in,
                "rows_out": rows_out,
                "error": error,
                "run_id": ctx.run_id,
                "source_schema": source_schema,
                "source_table": source_table,
            },
        )
