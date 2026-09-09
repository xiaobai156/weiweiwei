from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser

from shawei.config.constants import DEFAULT_EXCLUDE_KEYWORDS, PERIOD_RE, TABLE_TAIL_HEADERS
from shawei.domain.models import Record
from shawei.domain.text import contains_any, contains_none, normalize_text
from shawei.parsers.common import (
    _compact_snippet,
    _site_keyword_present,
    extract_draw_text,
    extract_tail_number,
)


@dataclass
class _TableContext:
    rows: list[list[str]] = field(default_factory=list)
    row: list[str] | None = None
    cell: list[str] | None = None


class StrictTableParser(HTMLParser):
    """Keep every HTML table in its own scope, including nested tables."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.tables: list[list[list[str]]] = []
        self._stack: list[_TableContext] = []
        self._loose = _TableContext()

    def _context(self) -> _TableContext:
        return self._stack[-1] if self._stack else self._loose

    def handle_starttag(self, tag: str, attrs) -> None:
        lowered = tag.lower()
        if lowered == "table":
            self._stack.append(_TableContext())
            return
        ctx = self._context()
        if lowered == "tr":
            ctx.row = []
            ctx.cell = None
        elif lowered in {"td", "th"} and ctx.row is not None:
            ctx.cell = []

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered == "table":
            if not self._stack:
                return
            ctx = self._stack.pop()
            if ctx.row:
                ctx.rows.append(ctx.row)
                self.rows.append(ctx.row)
            if ctx.rows:
                self.tables.append(ctx.rows)
            return

        ctx = self._context()
        if lowered in {"td", "th"} and ctx.row is not None and ctx.cell is not None:
            ctx.row.append(normalize_text("".join(ctx.cell)))
            ctx.cell = None
        elif lowered == "tr" and ctx.row is not None:
            if ctx.row:
                ctx.rows.append(ctx.row)
                self.rows.append(ctx.row)
            ctx.row = None
            ctx.cell = None

    def handle_data(self, data: str) -> None:
        ctx = self._context()
        if ctx.cell is not None:
            ctx.cell.append(data)

    def close(self) -> None:
        super().close()
        if self._loose.rows and not self.tables:
            self.tables.append(self._loose.rows)


def _looks_like_header(row: list[str], row_text: str) -> bool:
    first = normalize_text(row[0]) if row else ""
    if PERIOD_RE.search(first):
        return False
    return bool(
        "期数" in row_text
        or "期号" in row_text
        or "开奖结果" in row_text
        or any("开奖" in normalize_text(cell) for cell in row)
    )


def extract_strict_table_records(
    document: str,
    site_name: str,
    table_headers: tuple[str, ...] = TABLE_TAIL_HEADERS,
    table_anchor_keywords: tuple[str, ...] = (),
    table_required_headers: tuple[str, ...] = (),
    table_stop_keywords: tuple[str, ...] = (),
    exclude_keywords: tuple[str, ...] = DEFAULT_EXCLUDE_KEYWORDS,
    require_site_keyword: bool = True,
) -> list[Record]:
    if require_site_keyword and not _site_keyword_present(document, site_name):
        return []

    if table_anchor_keywords:
        positions = [
            document.find(keyword)
            for keyword in table_anchor_keywords
            if keyword and document.find(keyword) >= 0
        ]
        if not positions:
            return []
        document = document[min(positions) :]

    if table_stop_keywords:
        positions = [
            document.find(keyword)
            for keyword in table_stop_keywords
            if keyword and document.find(keyword) > 0
        ]
        if positions:
            document = document[: min(positions)]

    parser = StrictTableParser()
    try:
        parser.feed(document)
        parser.close()
    except Exception:
        return []

    records: list[Record] = []
    for table_rows in parser.tables:
        tail_index: int | None = None
        draw_index: int | None = None

        for row in table_rows:
            row_text = " ".join(normalize_text(cell) for cell in row)
            detected_tail: int | None = None
            detected_draw: int | None = None

            for index, cell in enumerate(row):
                normalized = normalize_text(cell)
                if contains_any(normalized, table_headers) or (
                    "禁" in normalized and "尾" in normalized
                ):
                    detected_tail = index
                if "开奖结果" in normalized or "开奖" in normalized:
                    detected_draw = index

            if _looks_like_header(row, row_text) or detected_tail is not None:
                tail_index = None
                draw_index = None
                if detected_tail is None:
                    continue
                if table_required_headers and not all(
                    header in row_text for header in table_required_headers
                ):
                    continue
                tail_index = detected_tail
                draw_index = detected_draw
                continue

            if tail_index is None or tail_index >= len(row):
                continue
            if exclude_keywords and not contains_none(row_text, exclude_keywords):
                continue

            period_match = PERIOD_RE.search(normalize_text(row[0]) if row else "")
            if period_match is None:
                continue

            tail_number = extract_tail_number(row[tail_index])
            if tail_number is None:
                continue

            draw_source = (
                row[draw_index]
                if draw_index is not None and draw_index < len(row)
                else row_text
            )
            records.append(
                Record(
                    tail=tail_number,
                    period=int(period_match.group(1)),
                    site_name=site_name,
                    draw_text=extract_draw_text(draw_source),
                    source_snippet=_compact_snippet(row_text),
                )
            )

    return records
