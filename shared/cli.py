import argparse
import importlib

def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run")
    run.add_argument("--pipeline", required=True)
    run.add_argument("--env", required=True)

    args = parser.parse_args()

    if args.cmd == "run":
        mod = importlib.import_module(f"pipelines.{args.pipeline}.pipeline")
        mod.run(args.env)

if __name__ == "__main__":
    main()
