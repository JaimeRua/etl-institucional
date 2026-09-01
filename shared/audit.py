from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import text
from shared.db import get_engine

@dataclass
class RunContext:
    run_id: str
    pipeline: str
    env: str
    git_sha: str

def init_schema() -> None:
    engine = get_engine()
    with engine.begin() as cxn:
        cxn.execute(text("""
        CREATE TABLE IF NOT EXISTS etl_run (
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
        """))

def start_run(ctx: RunContext) -> None:
    engine = get_engine()
    with engine.begin() as cxn:
        cxn.execute(text("""
          INSERT INTO etl_run(run_id,pipeline,env,git_sha,started_at,status)
          VALUES (:run_id,:pipeline,:env,:git_sha,:started_at,'RUNNING')
        """), {
            "run_id": ctx.run_id,
            "pipeline": ctx.pipeline,
            "env": ctx.env,
            "git_sha": ctx.git_sha,
            "started_at": datetime.now(timezone.utc),
        })

def finish_run(run_id: str, status: str, rows_in: int = 0, rows_out: int = 0, error: Optional[str] = None) -> None:
    engine = get_engine()
    with engine.begin() as cxn:
        cxn.execute(text("""
          UPDATE etl_run
          SET finished_at=:finished_at, status=:status, rows_in=:rows_in, rows_out=:rows_out, error=:error
          WHERE run_id=:run_id
        """), {
            "finished_at": datetime.now(timezone.utc),
            "status": status,
            "rows_in": rows_in,
            "rows_out": rows_out,
            "error": error,
            "run_id": run_id,
        })