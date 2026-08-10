"""Unified command-line interface for Case Monitor."""
from __future__ import annotations

import argparse
from typing import List, Optional

from .logging_utils import setup_logging
from .openai_mode import run_openai
from .scrape import run_scrape


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monitor NGT case updates")
    parser.add_argument(
        "--mode",
        choices=("scrape", "openai"),
        default="scrape",
        help="Monitoring backend to use.",
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Fail if OpenAI monitoring is unavailable instead of falling back to scraping.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    setup_logging()
    args = build_parser().parse_args(argv)

    if args.mode == "scrape":
        run_scrape()
    else:
        run_openai(allow_fallback=not args.no_fallback)


if __name__ == "__main__":
    main()
