"""Consecutive-duplicate report command-line entry point."""
from __future__ import annotations

import argparse

from shawei.services import consecutive_duplicates as _service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="全站点连续重复检测")
    parser.add_argument("--period", default=0, type=int)
    parser.add_argument("--output", default=None)
    parser.add_argument("--recent-cache", default=None)
    parser.add_argument("--cache-only", action="store_true")
    args = parser.parse_args(argv)
    return _service.run(
        period=args.period,
        output=args.output,
        recent_cache=args.recent_cache,
        cache_only=args.cache_only,
    )


if __name__ == "__main__":
    raise SystemExit(main())
