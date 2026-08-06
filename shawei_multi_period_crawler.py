# -*- coding: utf-8 -*-
"""Compatibility facade for V2 multi-period workflow."""
from __future__ import annotations

import argparse
import sys
import types
from pathlib import Path

import shawei_crawler as crawler
import shawei_duplicate_checker as site_config
from shawei.services import multi_period as _service


__all__ = ["crawler", "site_config"]
_BACKUPS: dict[str, object] = {}


def __getattr__(name: str):
    try:
        return getattr(_service, name)
    except AttributeError as exc:
        raise AttributeError(name) from exc


class _Facade(types.ModuleType):
    def __setattr__(self, name: str, value) -> None:
        if hasattr(_service, name):
            if name not in self.__dict__ and name not in _BACKUPS:
                _BACKUPS[name] = getattr(_service, name)
            setattr(_service, name, value)
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        if name in _BACKUPS:
            setattr(_service, name, _BACKUPS.pop(name))
        super().__delattr__(name)


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
        periods, Path(args.summary) if args.summary else None
    )
    print(f"多期汇总失败报告: {report}")
    return 1 if any(code != 0 for code in codes) else 0


sys.modules[__name__].__class__ = _Facade


if __name__ == "__main__":
    raise SystemExit(main())
