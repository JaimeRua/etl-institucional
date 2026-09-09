import argparse
import importlib
import subprocess
import uuid
import os

from shared.audit import RunContext, init_schema, start_run, finish_run
from shared.config import load_settings
from shared.db_postgres import get_pg_engine


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run")
    run.add_argument("--pipeline", required=True)
    run.add_argument("--env", required=True)
    run.add_argument(
        "--table",
        action="append",
        default=[],
        help="Tabla a cargar (dbo.TABLA, TABLA o nombre raw). Repetible.",
    )
    run.add_argument("--chunk-size", type=int, default=10_000)
    run.add_argument("--continue-on-error", action="store_true")
    run.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.cmd == "run":
        os.environ["APP_ENV"] = args.env

        settings = load_settings(args.env)
        audit_engine = get_pg_engine(settings.postgres)
        init_schema(audit_engine)
        run_id = str(uuid.uuid4())
        ctx = RunContext(
            run_id=run_id,
            pipeline=args.pipeline,
            env=args.env,
            git_sha=git_sha(),
            options={
                "tables": args.table,
                "chunk_size": args.chunk_size,
                "continue_on_error": args.continue_on_error,
                "dry_run": args.dry_run,
            },
        )
        start_run(audit_engine, ctx)

        try:
            mod = importlib.import_module(f"pipelines.{args.pipeline}.pipeline")
            rows_in, rows_out = mod.run(ctx, settings)
            finish_run(
                audit_engine, run_id, "SUCCESS", rows_in=rows_in, rows_out=rows_out
            )
        except Exception as e:
            finish_run(audit_engine, run_id, "FAILED", error=str(e))
            raise


if __name__ == "__main__":
    main()
