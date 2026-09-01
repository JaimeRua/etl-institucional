import argparse
import importlib
import subprocess
import uuid
import os

from shared.audit import RunContext, init_schema, start_run, finish_run

def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"

def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run")
    run.add_argument("--pipeline", required=True)
    run.add_argument("--env", required=True)

    args = parser.parse_args()

    if args.cmd == "run":
        os.environ["APP_ENV"] = args.env

        init_schema()
        run_id = str(uuid.uuid4())
        ctx = RunContext(run_id=run_id, pipeline=args.pipeline, env=args.env, git_sha=git_sha())
        start_run(ctx)

        try:
            mod = importlib.import_module(f"pipelines.{args.pipeline}.pipeline")
            rows_in, rows_out = mod.run(ctx)  # estándar nuevo
            finish_run(run_id, "SUCCESS", rows_in=rows_in, rows_out=rows_out)
        except Exception as e:
            finish_run(run_id, "FAILED", error=str(e))
            raise

if __name__ == "__main__":
    main()