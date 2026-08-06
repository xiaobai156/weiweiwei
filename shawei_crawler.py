# -*- coding: utf-8 -*-
"""Compatibility facade for V2.

Business logic lives under ``shawei``.  This module preserves the existing
import surface while forwarding test/runtime patches to the owning modules.
"""
from __future__ import annotations

import sys
import types
from types import ModuleType

from shawei.cli import daily
from shawei.config import constants, paths, rules, sites
from shawei.domain import models, text
from shawei.fetch import browser, decoding, document_discovery, dynamic_article, http_client, profile
from shawei.parsers import common, dedicated, registry, topic
from shawei.persistence import atomic_file, cache_repository, health_repository, txt_writer
from shawei.services import batch_crawl, crawl_site
from shawei.validation import validator


_MODULES: tuple[ModuleType, ...] = (
    models,
    text,
    constants,
    paths,
    rules,
    sites,
    atomic_file,
    txt_writer,
    cache_repository,
    health_repository,
    decoding,
    http_client,
    dynamic_article,
    profile,
    browser,
    document_discovery,
    common,
    topic,
    dedicated,
    registry,
    validator,
    crawl_site,
    batch_crawl,
    daily,
)

_PARSER_SOURCES = {
    "extract_absolute_kill_section_records": "section",
    "extract_table_records": "table",
    "extract_compact_records": "compact",
    "extract_dedicated_records": "dedicated",
    "extract_user_feed_records": "user_feed",
    "extract_lead_compact_records": "lead_compact",
}


def _owners() -> dict[str, list[ModuleType]]:
    result: dict[str, list[ModuleType]] = {}
    for module in _MODULES:
        for name in vars(module):
            if not name.startswith("__"):
                result.setdefault(name, []).append(module)
    return result


_SYMBOL_OWNERS = _owners()
_FORWARD_BACKUPS: dict[str, tuple[tuple[ModuleType, object], ...]] = {}
SCRIPT_DIR = paths.ROOT_DIR
OUTPUT_DIR = paths.OUTPUT_DIR
FAIL_OUTPUT_DIR = paths.FAIL_OUTPUT_DIR
SITES_CSV_PATH = paths.SITES_CSV_PATH
SITES_JSON_PATH = paths.SITES_JSON_PATH
SITE_HEALTH_PATH = paths.SITE_HEALTH_PATH


def __getattr__(name: str):
    owners = _SYMBOL_OWNERS.get(name)
    if not owners:
        raise AttributeError(name)
    return getattr(owners[0], name)


class _FacadeModule(types.ModuleType):
    def __setattr__(self, name: str, value) -> None:
        owners = self.__dict__.get("_SYMBOL_OWNERS", {}).get(name, ())
        backups = self.__dict__.get("_FORWARD_BACKUPS", {})
        if owners and name not in self.__dict__ and name not in backups:
            backups[name] = tuple((owner, getattr(owner, name)) for owner in owners)
        for owner in owners:
            setattr(owner, name, value)
        source = self.__dict__.get("_PARSER_SOURCES", {}).get(name)
        if source:
            registry.SOURCE_PARSERS[source] = value
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        backups = self.__dict__.get("_FORWARD_BACKUPS", {})
        saved = backups.pop(name, ())
        for owner, value in saved:
            setattr(owner, name, value)
        source = self.__dict__.get("_PARSER_SOURCES", {}).get(name)
        if source and saved:
            registry.SOURCE_PARSERS[source] = saved[0][1]
        super().__delattr__(name)


sys.modules[__name__].__class__ = _FacadeModule


if __name__ == "__main__":
    raise SystemExit(daily.main())
