# -*- coding: utf-8 -*-
"""Compatibility facade for the V2 duplicate admission service."""
from __future__ import annotations

import sys
import types

import shawei_crawler as crawler
from shawei.services import duplicate_check as _service


__all__ = ["crawler"]
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


sys.modules[__name__].__class__ = _Facade
