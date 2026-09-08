"""Multi-period command-line entry point."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shawei.services import multi_period as _service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="多期抓取杀尾，不更新缓存。")
    parser.add_argument("--periods", nargs="+", required=True)
    parser.add_argument("--timeout", type=int, default=None)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--summary", default=None)
    args = parser.parse_args(argv)
    try:
        periods = _service.parse_periods(args.periods)
    except ValueError as exc:
        print(f"参数错误: {exc}", file=sys.stderr)
        return 2
    codes = [
        _service.run_period(period, args.timeout, args.workers) for period in periods
    ]
    report = _service.build_summary(
        periods,
        Path(args.summary) if args.summary else None,
        run_codes=dict(zip(periods, codes)),
    )
    print(f"多期汇总失败报告: {report}")
    return 1 if any(code != 0 for code in codes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
