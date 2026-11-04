from __future__ import annotations

from collections.abc import Callable

from shawei.parsers import common as common_parser_module
from shawei.parsers import topic as topic_parser_module
from shawei.parsers.common import (
    extract_absolute_kill_section_records,
    extract_compact_records,
    extract_lead_compact_records,
    extract_user_feed_records,
)
from shawei.parsers.safe_table import StrictTableParser, extract_strict_table_records

# Every topic parser that consumes DOM text must see source order.  The legacy
# helper grouped parent text before child text and could reorder period/value
# pairs.  Keep one authoritative implementation for all existing topic paths.
topic_parser_module._dynamic_node_text = topic_parser_module._dynamic_node_text_in_order

# Dedicated parsers import TableParser/extract_table_records from common at
# module import time.  Patch those shared entry points before importing
# dedicated so every table path gets the strict table-scope implementation.
common_parser_module.TableParser = StrictTableParser
common_parser_module.extract_table_records = extract_strict_table_records

from shawei.parsers.dedicated import extract_dedicated_records
from shawei.parsers.safe_static_article import extract_safe_static_article_body_records
from shawei.parsers.safety_guards import enforce_parsed_records


Parser = Callable[..., list]


SOURCE_PARSERS: dict[str, Parser] = {
    "section": extract_absolute_kill_section_records,
    "table": extract_strict_table_records,
    "compact": extract_compact_records,
    "dedicated": extract_dedicated_records,
    "user_feed": extract_user_feed_records,
    "lead_compact": extract_lead_compact_records,
}


_STATIC_ARTICLE_PARSERS = frozenset({
    "article_static_single_tail",
    "article_static_two_tail",
})


def parse_source(source: str, document: str, site_name: str, **kwargs):
    parser = SOURCE_PARSERS.get(source)
    if parser is None:
        raise LookupError(f"未知解析来源，拒绝兜底: {source}")
    parser_name = str(kwargs.get("parser_name") or "")
    if source == "dedicated" and parser_name in _STATIC_ARTICLE_PARSERS:
        records = extract_safe_static_article_body_records(
            document,
            site_name,
            kwargs.get("chunk_keywords") or (),
            two_tail=parser_name == "article_static_two_tail",
            exclude_keywords=kwargs.get("exclude_keywords") or (),
            max_chunk_span=int(kwargs.get("max_chunk_span") or 240),
            require_draw_signal=bool(kwargs.get("require_draw_signal", True)),
            require_site_keyword=bool(kwargs.get("require_site_keyword", True)),
        )
    else:
        records = parser(document, site_name, **kwargs)
    return enforce_parsed_records(
        records,
        source=source,
        parser_name=parser_name,
        document=document,
        site_name=site_name,
    )
