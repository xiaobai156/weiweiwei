from __future__ import annotations

from collections.abc import Callable

from shawei.parsers.common import (
    extract_absolute_kill_section_records,
    extract_compact_records,
    extract_lead_compact_records,
    extract_table_records,
    extract_user_feed_records,
)
from shawei.parsers.dedicated import extract_dedicated_records


Parser = Callable[..., list]


SOURCE_PARSERS: dict[str, Parser] = {
    "section": extract_absolute_kill_section_records,
    "table": extract_table_records,
    "compact": extract_compact_records,
    "dedicated": extract_dedicated_records,
    "user_feed": extract_user_feed_records,
    "lead_compact": extract_lead_compact_records,
}


def parse_source(source: str, document: str, site_name: str, **kwargs):
    parser = SOURCE_PARSERS.get(source)
    if parser is None:
        raise LookupError(f"未知解析来源，拒绝兜底: {source}")
    return parser(document, site_name, **kwargs)
