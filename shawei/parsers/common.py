from __future__ import annotations

import re
from html.parser import HTMLParser

from shawei.config.constants import (
    CHINESE_DIGITS, DEFAULT_EXCLUDE_KEYWORDS, DRAW_RE, PERIOD_CHUNK_RE, PERIOD_RE,
    SECTION_KEYWORDS, SECTION_TAIL_KEYWORDS, TABLE_TAIL_HEADERS, TAIL_PATTERNS,
    TAIL_RE, TWO_TAIL_SITE_URLS, USER_FEED_TAIL_RE, WAVE_VALUE_RE,
)
from shawei.domain.models import Record
from shawei.domain.text import contains_any, contains_none, normalize_text


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.tables: list[list[list[str]]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._table: list[list[str]] | None = None
        self._table_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        lowered = tag.lower()
        if lowered == "table":
            if self._table_depth == 0:
                self._table = []
            self._table_depth += 1
        elif lowered == "tr":
            self._row = []
        elif lowered in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append(normalize_text("".join(self._cell)))
            self._cell = None
        elif lowered == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
                if self._table is not None:
                    self._table.append(self._row)
            self._row = None
            self._cell = None
        elif lowered == "table" and self._table_depth:
            self._table_depth -= 1
            if self._table_depth == 0:
                if self._table:
                    self.tables.append(self._table)
                self._table = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def extract_tail_number(text: str) -> int | None:
    """Return exactly one tail digit from one field; never truncate ambiguity."""
    normalized = normalize_text(text)
    numeric_match = re.fullmatch(
        r"[\[\(]?\s*(\d)\s*(?:尾)?\s*[\]\)]?",
        normalized,
    )
    if numeric_match:
        return int(numeric_match.group(1))
    chinese_match = re.fullmatch(
        r"[\[\(]?\s*([零〇一二三四五六七八九])\s*尾\s*[\]\)]?",
        normalized,
    )
    if chinese_match:
        return CHINESE_DIGITS[chinese_match.group(1)]
    return None


def matches_tail_signal(chunk: str, keywords: tuple[str, ...]) -> bool:
    normalized = normalize_text(chunk)
    if keywords:
        return contains_any(normalized, keywords)
    return _extract_tail_value(normalized) is not None


def _site_keyword_present(text: str, site_name: str) -> bool:
    normalized_name = normalize_text(site_name)
    if not normalized_name:
        return True
    return normalized_name in normalize_text(text)


def _tail_signal_keywords(keywords: tuple[str, ...], site_name: str) -> tuple[str, ...]:
    normalized_name = normalize_text(site_name)
    return tuple(keyword for keyword in keywords if normalize_text(keyword) != normalized_name)


def _keywords_require_site_keyword(keywords: tuple[str, ...], site_name: str, require_site_keyword: bool) -> bool:
    return require_site_keyword


def _compact_snippet(text: str, limit: int = 160) -> str:
    normalized = normalize_text(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."


def extract_draw_text(text: str) -> str:
    normalized = normalize_text(text)
    match = DRAW_RE.search(normalized)
    if not match:
        return ""
    return "开" + re.sub(r"\s+", "", match.group(1)).strip(":?")


def record_value(record: Record) -> str:
    if record.tail_values:
        return "、".join(str(value) for value in record.tail_values)
    return record.value_text or str(record.tail)


def is_valid_tail_record(record: Record) -> bool:
    value = record_value(record)
    if record.tail_values:
        return len(record.tail_values) == 2 and all(0 <= value <= 9 for value in record.tail_values)
    return re.fullmatch(r"\d", value) is not None


def is_two_tail_site_url(url: str) -> bool:
    return url.strip() in TWO_TAIL_SITE_URLS


def _prediction_text(chunk: str) -> str:
    normalized = normalize_text(chunk)
    # Only a real draw marker ends the prediction.  This avoids treating the
    # draw number as a tail while not cutting ordinary words such as 开奖栏目.
    draw_boundary = re.search(
        r"开\s*[:：?？]?\s*(?=(?:[鼠牛虎兔龙蛇马羊猴鸡狗猪]\s*)?\d|\?)",
        normalized,
    )
    if draw_boundary is not None:
        normalized = normalized[: draw_boundary.start()]
    return normalized.strip()


def _extract_tail_value(chunk: str) -> int | None:
    prediction = normalize_text(_prediction_text(chunk))
    if "尾" not in prediction:
        return None
    for pattern in TAIL_PATTERNS:
        match = pattern.search(prediction)
        if not match:
            continue
        raw_value = match.group(1)
        if re.fullmatch(r"\d", raw_value) is None:
            continue
        matched_text = normalize_text(match.group(0)).replace(" ", "")
        if raw_value == "1" and re.fullmatch(r"(?:绝杀|精准杀|稳杀|狠杀|主杀|课杀|杀掉|禁|杀)1尾", matched_text):
            continue
        # A single-tail parser must not silently select one value from a
        # multi-tail field such as 2、3尾 or 1尾 8尾.
        suffix = prediction[match.end() : match.end() + 16]
        if re.match(r"\s*(?:尾\s*)?(?:[、,，.．+＋/]\s*)?\d\s*尾", suffix):
            continue
        return int(raw_value)
    return None


def _period_window(chunk: str, max_span: int = 240) -> str:
    return normalize_text(chunk)[: max(80, max_span)]


def _has_draw_signal(chunk: str) -> bool:
    normalized = normalize_text(chunk)
    return any(signal in normalized for signal in ("开", "准", "错"))


def _strong_tail_candidate_window(
    chunk: str,
    keywords: tuple[str, ...],
    site_name: str = "",
    max_span: int = 240,
    require_draw_signal: bool = True,
    require_site_keyword: bool = True,
) -> str:
    window = _period_window(chunk, max_span)
    site_required = _keywords_require_site_keyword(keywords, site_name, require_site_keyword)
    if site_required and not _site_keyword_present(window, site_name):
        return ""
    signal_keywords = _tail_signal_keywords(keywords, site_name)
    if signal_keywords and not matches_tail_signal(window, signal_keywords):
        return ""
    if require_draw_signal and not _has_draw_signal(window):
        return ""
    if _extract_tail_value(window) is None and _extract_wave_value(window) == "":
        return ""
    return window


def _extract_wave_value(chunk: str) -> str:
    prediction = normalize_text(_prediction_text(chunk))
    if "半波" not in prediction:
        return ""
    match = WAVE_VALUE_RE.search(prediction)
    return match.group(1) if match else ""


def extract_table_records(
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
        anchor_positions = [document.find(keyword) for keyword in table_anchor_keywords if keyword and document.find(keyword) >= 0]
        if not anchor_positions:
            return []
        document = document[min(anchor_positions) :]
    if table_stop_keywords:
        stop_positions = [document.find(keyword) for keyword in table_stop_keywords if keyword and document.find(keyword) > 0]
        if stop_positions:
            document = document[: min(stop_positions)]

    parser = TableParser()
    try:
        parser.feed(document)
        parser.close()
    except Exception:
        return []

    records: list[Record] = []
    table_groups = parser.tables or ([parser.rows] if parser.rows else [])

    for table_rows in table_groups:
        tail_index: int | None = None
        draw_index: int | None = None
        for row in table_rows:
            row_text = " ".join(normalize_text(cell) for cell in row)
            detected_tail: int | None = None
            detected_draw: int | None = None
            for index, cell in enumerate(row):
                normalized = normalize_text(cell)
                if contains_any(normalized, table_headers) or ("禁" in normalized and "尾" in normalized):
                    detected_tail = index
                if "开奖结果" in normalized or "开奖" in normalized:
                    detected_draw = index

            if detected_tail is not None:
                if table_required_headers and not all(
                    header in row_text for header in table_required_headers
                ):
                    tail_index = None
                    draw_index = None
                    continue
                tail_index = detected_tail
                draw_index = detected_draw
                continue

            if tail_index is None or tail_index >= len(row):
                continue
            if exclude_keywords and not contains_none(row_text, exclude_keywords):
                continue
            period_match = PERIOD_RE.search(" ".join(row[:1]))
            tail_number = extract_tail_number(row[tail_index])
            if not period_match or tail_number is None:
                continue
            draw_source = row[draw_index] if draw_index is not None and draw_index < len(row) else " ".join(row)
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


def extract_compact_records(
    document: str,
    site_name: str,
    chunk_keywords: tuple[str, ...] = SECTION_TAIL_KEYWORDS,
    exclude_keywords: tuple[str, ...] = DEFAULT_EXCLUDE_KEYWORDS,
    max_chunk_span: int = 240,
    require_draw_signal: bool = True,
    require_site_keyword: bool = True,
) -> list[Record]:
    text = normalize_text(re.sub(r"<[^>]+>", " ", document))
    records: list[Record] = []
    chunks = [chunk.strip() for chunk in PERIOD_CHUNK_RE.split(text) if chunk.strip()]
    for chunk in chunks:
        period_match = PERIOD_RE.match(chunk)
        if not period_match:
            continue
        if exclude_keywords and not contains_none(chunk, exclude_keywords):
            continue
        window = _strong_tail_candidate_window(
            chunk,
            chunk_keywords,
            site_name=site_name,
            max_span=max_chunk_span,
            require_draw_signal=require_draw_signal,
            require_site_keyword=require_site_keyword,
        )
        if not window:
            continue
        period = int(period_match.group(1))
        tail = _extract_tail_value(window)
        if tail is not None:
            records.append(
                Record(
                    tail=tail,
                    period=period,
                    site_name=site_name,
                    draw_text=extract_draw_text(window),
                    source_snippet=_compact_snippet(window),
                )
            )
            continue
        wave_value = _extract_wave_value(window)
        if wave_value:
            records.append(
                Record(
                    tail=-1,
                    period=period,
                    site_name=site_name,
                    draw_text=extract_draw_text(chunk),
                    value_text=wave_value,
                    source_snippet=_compact_snippet(window),
                )
            )
    return records


def extract_absolute_kill_section_records(
    document: str,
    site_name: str,
    section_keywords: tuple[str, ...] = SECTION_KEYWORDS,
    section_stop_keywords: tuple[str, ...] = (),
    chunk_keywords: tuple[str, ...] = SECTION_TAIL_KEYWORDS,
    exclude_keywords: tuple[str, ...] = DEFAULT_EXCLUDE_KEYWORDS,
    max_section_span: int = 1500,
    max_chunk_span: int = 240,
    require_draw_signal: bool = True,
    require_site_keyword: bool = True,
) -> list[Record]:
    text = normalize_text(re.sub(r"<[^>]+>", " ", document))
    section_start = next((keyword for keyword in section_keywords if keyword in text), None)
    if section_start is None:
        return []

    section = text.split(section_start, 1)[1][: max(200, max_section_span)]
    stop_positions = [
        section.find(keyword)
        for keyword in section_stop_keywords
        if keyword and section.find(keyword) >= 0
    ]
    if stop_positions:
        section = section[: min(stop_positions)]
    # The section marker itself can be the site identity (for example
    # ``飞龙在天 『绝杀一尾』``).  It is consumed when slicing ``section``,
    # so accept that proven marker instead of requiring the site name to be
    # repeated inside the rows.
    if require_site_keyword and not (
        _site_keyword_present(section, site_name)
        or _site_keyword_present(section_start, site_name)
    ):
        return []
    signal_keywords = _tail_signal_keywords(chunk_keywords, site_name)
    if signal_keywords and not matches_tail_signal(section, signal_keywords):
        return []
    records: list[Record] = []
    chunks = [chunk.strip() for chunk in PERIOD_CHUNK_RE.split(section) if chunk.strip()]
    for chunk in chunks:
        period_match = PERIOD_RE.match(chunk)
        if not period_match:
            continue
        if exclude_keywords and not contains_none(chunk, exclude_keywords):
            continue
        window = _strong_tail_candidate_window(
            chunk,
            chunk_keywords,
            site_name=site_name,
            max_span=max_chunk_span,
            require_draw_signal=require_draw_signal,
            require_site_keyword=require_site_keyword,
        )
        if not window:
            continue
        tail = _extract_tail_value(window)
        if tail is None:
            continue
        records.append(
            Record(
                tail=tail,
                period=int(period_match.group(1)),
                site_name=site_name,
                draw_text=extract_draw_text(window),
                source_snippet=_compact_snippet(window),
            )
        )
    return records


def extract_user_feed_records(
    document: str,
    site_name: str,
    chunk_keywords: tuple[str, ...] = SECTION_TAIL_KEYWORDS,
    exclude_keywords: tuple[str, ...] = DEFAULT_EXCLUDE_KEYWORDS,
    max_chunk_span: int = 240,
    require_draw_signal: bool = True,
    require_site_keyword: bool = True,
) -> list[Record]:
    text = normalize_text(re.sub(r"<[^>]+>", " ", document))
    records: list[Record] = []
    for match in USER_FEED_TAIL_RE.finditer(text):
        snippet = text[match.start() : min(len(text), match.start() + max(80, max_chunk_span))]
        if require_site_keyword and not _site_keyword_present(snippet, site_name):
            continue
        site_required = _keywords_require_site_keyword(chunk_keywords, site_name, require_site_keyword)
        if site_required and not _site_keyword_present(snippet, site_name):
            continue
        signal_keywords = _tail_signal_keywords(chunk_keywords, site_name)
        if signal_keywords and not matches_tail_signal(snippet, signal_keywords):
            continue
        if require_draw_signal and not _has_draw_signal(snippet):
            continue
        if exclude_keywords and not contains_none(snippet, exclude_keywords):
            continue
        raw_tail = match.group(2)
        if re.fullmatch(r"\d", raw_tail) is None:
            continue
        draw_text = extract_draw_text(snippet)
        records.append(
            Record(
                tail=int(raw_tail),
                period=int(match.group(1)),
                site_name=site_name,
                draw_text=draw_text,
                source_snippet=_compact_snippet(f"{site_name} {snippet}"),
            )
        )
    return records


def extract_lead_compact_records(
    document: str,
    site_name: str,
    chunk_keywords: tuple[str, ...] = SECTION_TAIL_KEYWORDS,
    exclude_keywords: tuple[str, ...] = DEFAULT_EXCLUDE_KEYWORDS,
    lead_span: int = 700,
    max_chunk_span: int = 240,
    require_draw_signal: bool = True,
    require_site_keyword: bool = True,
) -> list[Record]:
    text = normalize_text(re.sub(r"<[^>]+>", " ", document))
    snippet = text[: max(200, lead_span)]
    records = extract_compact_records(
        snippet,
        site_name,
        chunk_keywords=chunk_keywords,
        exclude_keywords=exclude_keywords,
        max_chunk_span=max_chunk_span,
        require_draw_signal=require_draw_signal,
        require_site_keyword=require_site_keyword,
    )
    if not records:
        return records
    anchor = records[0].period
    return [record for record in records if abs(record.period - anchor) <= 40]


extract_tail_value = _extract_tail_value
