"""Command-line entry point: ``healer run`` and ``healer diff``."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from healer import pipeline
from healer.diff import diff
from healer.spec import load_file


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="healer", description="Keep an API test suite in sync with the API's OpenAPI spec."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run one healing cycle")
    run.add_argument(
        "--base-url",
        default=os.environ.get("API_BASE_URL", "http://127.0.0.1:8000"),
        help="target API (default: $API_BASE_URL or http://127.0.0.1:8000)",
    )
    run.add_argument("--spec-url", help="current contract URL (default: <base-url>/openapi.json)")
    run.add_argument("--baseline", type=Path, default=Path("api-spec/openapi.json"))
    run.add_argument("--tests", type=Path, default=Path("tests/api"))
    run.add_argument("--runs-dir", type=Path, default=Path("runs"))
    run.add_argument("--max-attempts", type=int, default=3)
    run.add_argument("--retries", type=int, default=3)
    run.add_argument("--retry-delay", type=float, default=1.0, help=argparse.SUPPRESS)
    run.add_argument("--publish", choices=("local", "github"), default="local")
    run.add_argument(
        "--apply",
        action="store_true",
        help="local mode: write repaired tests and the new baseline into the working tree",
    )

    show = sub.add_parser("diff", help="list changes between two OpenAPI files")
    show.add_argument("old", type=Path)
    show.add_argument("new", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "diff":
        for change in diff(load_file(args.old), load_file(args.new)):
            flag = "breaking" if change.breaking else "non-breaking"
            print(f"{change.id} [{flag}] {change.describe()}")
        return 0

    if args.max_attempts < 1 or args.retries < 0:
        print("healer: --max-attempts must be >= 1 and --retries >= 0", file=sys.stderr)
        return 2
    for path in (args.baseline, args.tests):
        if not path.exists():
            print(f"healer: {path} does not exist", file=sys.stderr)
            return 2
    base_url = args.base_url.rstrip("/")
    config = pipeline.Config(
        root=Path.cwd(),
        base_url=base_url,
        spec_url=args.spec_url or f"{base_url}/openapi.json",
        baseline=args.baseline,
        tests=args.tests,
        runs_dir=args.runs_dir,
        max_attempts=args.max_attempts,
        retries=args.retries,
        retry_delay=args.retry_delay,
        publish_mode=args.publish,
        apply=args.apply,
    )
    return pipeline.run(config).exit_code


if __name__ == "__main__":
    sys.exit(main())
