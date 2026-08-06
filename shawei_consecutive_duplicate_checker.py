# -*- coding: utf-8 -*-
"""Compatibility facade for V2 consecutive duplicate checks."""
from __future__ import annotations

import argparse
import os
import sys
import types

import shawei_crawler as crawler
import shawei_duplicate_checker as strict_checker
from shawei.services import consecutive_duplicates as _service


__all__ = ["crawler", "strict_checker", "os"]
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
    parser = argparse.ArgumentParser(description="全站点连续重复检测")
    parser.add_argument("--period", default=0, type=int)
    parser.add_argument("--window", default=_service.WINDOW_SIZE, type=int)
    parser.add_argument("--consecutive", default=_service.CONSECUTIVE_REQUIRED, type=int)
    parser.add_argument("--timeout", default=_service.DEFAULT_TIMEOUT, type=int)
    parser.add_argument("--workers", default=_service.DEFAULT_WORKERS, type=int)
    parser.add_argument("--output", default=None)
    parser.add_argument("--fail-output", default=None)
    parser.add_argument("--recent-cache", default=None)
    parser.add_argument("--use-recent-cache", action="store_true")
    parser.add_argument("--no-write-cache", action="store_true")
    parser.add_argument("--cache-only", action="store_true")
    parser.set_defaults(use_recent_cache=True, no_write_cache=True)
    args = parser.parse_args(argv)
    return _service.run(
        period=args.period,
        window=args.window,
        consecutive=args.consecutive,
        timeout=args.timeout,
        workers=args.workers,
        output=args.output,
        fail_output=args.fail_output,
        recent_cache=args.recent_cache,
        use_recent_cache=args.use_recent_cache,
        write_cache=not args.no_write_cache,
        cache_only=args.cache_only,
    )


sys.modules[__name__].__class__ = _Facade


if __name__ == "__main__":
    raise SystemExit(main())
