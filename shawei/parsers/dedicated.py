from __future__ import annotations

import html
import re
from dataclasses import dataclass

from shawei.config.constants import (
    DEFAULT_EXCLUDE_KEYWORDS,
    PERIOD_CHUNK_RE,
    PERIOD_RE,
    QVUU_TWO_TAIL_PATTERNS,
)
from shawei.domain.models import Record
from shawei.domain.text import contains_none, is_bottom_pick, normalize_text
from shawei.parsers.common import (
    TableParser, _compact_snippet, _has_draw_signal, _period_window,
    _site_keyword_present, extract_draw_text, extract_table_records,
)
from shawei.parsers.topic import (
    TOPIC_MAIN_DEDICATED_PARSERS, _DynamicHtmlParser, _dynamic_class_tokens,
    _dynamic_node_text_in_order, _extract_topic_main_dedicated_records,
    _topic_main_select_contiguous_segment, extract_topic_published_body_records,
    extract_lainan_yixin_bottom_records, extract_qingqingdandan_topic_records,
)


@dataclass(frozen=True)
class DedicatedContext:
    exclude_keywords: tuple[str, ...] = DEFAULT_EXCLUDE_KEYWORDS
    chunk_keywords: tuple[str, ...] = ()
    max_chunk_span: int = 240
    require_draw_signal: bool = True
    require_site_keyword: bool = True
    target_period: int | None = None
    pick: str = "top"
    anchor_span: int = 1500
    allow_same_period_records: bool = False


_CURRENT_DRAW_ZODIAC = "鼠牛虎兔龙蛇马羊猴鸡狗猪"


_EXACT_CURRENT_TOPIC_PATTERNS = {
    "danyu_current_tail": re.compile(
        rf"精\s*杀\s*一\s*尾\s*[\[【]\s*(\d)\s*[\]】]"
        rf"\s*开\s*(?:[{_CURRENT_DRAW_ZODIAC}])\s*\d{{2}}\s*(?:准|错)"
    ),
    "jingtingnianhua_current_tail": re.compile(
        rf"绝\s*杀\s*一\s*尾\s*[\[【]\s*(\d)\s*尾\s*[\]】]"
        rf"\s*中\s*开\s*[:：]?\s*(?:[{_CURRENT_DRAW_ZODIAC}])\s*\d{{2}}\s*(?:准|错)"
    ),
    "yidianhong_current_tail": re.compile(
        rf"绝\s*杀\s*1\s*尾\s*\[\s*(\d)\s*\]"
        rf"\s*开\s*[:：]?\s*(?:(?:[{_CURRENT_DRAW_ZODIAC}])\s*\d{{2}}|0{{4}})\s*(?:准|错)"
    ),
    "shashaxionger_current_tail": re.compile(
        rf"绝\s*杀\s*1\s*尾[^0-9]{{0,8}}〖\s*\d{{0,2}}(\d)\s*〗"
        rf"\s*开\s*[:：]?\s*(?:[{_CURRENT_DRAW_ZODIAC}])\s*\d{{2}}\s*(?:准|错)"
    ),
    "linlinjinzhi_current_tail": re.compile(
        rf"绝\s*杀\s*一\s*尾\s*〖\s*(\d)\s*尾\s*〗"
        rf"\s*开\s*[:：]?\s*(?:[{_CURRENT_DRAW_ZODIAC}])\s*\d{{2}}\s*(?:准|错)"
    ),
    "yeyuehuazhao_current_tail": re.compile(
        rf"精\s*杀\s*一\s*尾\s*◆\s*(\d)\s*尾"
        rf"\s*开\s*[:：]?\s*(?:(?:[{_CURRENT_DRAW_ZODIAC}])\s*\d{{2}}|0{{2}})\s*(?:准|错)"
    ),
    "xukong_current_tail": re.compile(
        rf"精\s*杀\s*一\s*尾\s*◆\s*(\d)\s*尾"
        rf"\s*开\s*[:：]?\s*(?:(?:[{_CURRENT_DRAW_ZODIAC}])\s*\d{{2}}|[?？]?0{{2,4}})\s*(?:准|错)"
    ),
    "dongfang_current_tail": re.compile(
        rf"精\s*杀\s*一\s*尾\s*✠?\s*[（(]\s*(\d)\s*尾\s*[）)]"
        rf"\s*开\s*[:：]?\s*(?:(?:[{_CURRENT_DRAW_ZODIAC}])\s*\d{{2}}|0{{4}})\s*(?:准|错)"
    ),
}


_EXACT_CURRENT_TOPIC_VALUE_PATTERNS = {
    "danyu_current_tail": re.compile(r"精\s*杀\s*一\s*尾\s*[\[【]\s*(\d)\s*[\]】]"),
    "jingtingnianhua_current_tail": re.compile(
        r"绝\s*杀\s*一\s*尾\s*[\[【]\s*(\d)\s*尾\s*[\]】]"
    ),
    "yidianhong_current_tail": re.compile(r"绝\s*杀\s*1\s*尾\s*\[\s*(\d)\s*\]"),
    "shashaxionger_current_tail": re.compile(
        r"绝\s*杀\s*1\s*尾[^0-9]{0,8}〖\s*\d{0,2}(\d)\s*〗"
    ),
    "linlinjinzhi_current_tail": re.compile(
        r"绝\s*杀\s*一\s*尾\s*〖\s*(\d)\s*尾\s*〗"
    ),
    "yeyuehuazhao_current_tail": re.compile(r"精\s*杀\s*一\s*尾\s*◆\s*(\d)\s*尾"),
    "xukong_current_tail": re.compile(r"精\s*杀\s*一\s*尾\s*◆\s*(\d)\s*尾"),
    "dongfang_current_tail": re.compile(
        r"精\s*杀\s*一\s*尾\s*✠?\s*[（(]\s*(\d)\s*尾\s*[）)]"
    ),
}


_QVUU_ONE_TAIL_PATTERNS = {
    "qvuu_zhiyang_one_tail": re.compile(
        r"绝\s*杀\s*一\s*尾\s*[\[【]\s*(\d{1,3})\s*[\]】]\s*开"
    ),
    "qvuu_siren_lanqiu_one_tail": re.compile(
        r"绝\s*杀\s*一\s*尾\s*[\[【]\s*(\d{1,3})\s*[\]】]\s*开"
    ),
    "qvuu_tianmi_tudou_one_tail": re.compile(
        r"杀\s*一\s*尾\s*[（(]\s*(\d{1,3})\s*尾\s*[）)]\s*开"
    ),
    "qvuu_reai_huoguo_one_tail": re.compile(
        r"[（(]\s*绝\s*杀\s*一\s*尾\s*[）)]\s*[（(]\s*(\d{1,3})\s*尾\s*[）)]\s*开"
    ),
    "qvuu_minjian_bixia_one_tail": re.compile(
        r"杀\s*一\s*尾\s*[（(]\s*(\d{1,3})\s*尾\s*[）)]\s*开"
    ),
}


_MANAGER_TAIL_PATTERNS = {
    "huangjia_cima_manager_tail": re.compile(
        r"皇家赐码[^0-9\r\n]{0,48}绝\s*杀\s*(?:1|一)\s*尾"
        r"[^0-9\r\n]{0,24}[\[【]\s*(\d)\s*[\]】]"
        r"[^0-9\r\n]{0,24}开\s*[:：]?\s*\d{2}\s*(?:准|错)"
    ),
    "dazao_huihuang_manager_tail": re.compile(
        r"打造辉煌[^0-9\r\n]{0,48}绝\s*杀\s*(?:1|一)\s*尾"
        r"[^0-9\r\n]{0,24}[\[【]\s*(\d)\s*[\]】]"
        r"[^0-9\r\n]{0,24}开\s*[:：]?\s*\d{2}\s*(?:准|错)"
    ),
    "yehei_fenggao_manager_tail": re.compile(
        r"夜黑风高[^0-9\r\n]{0,48}绝\s*杀\s*(?:1|一)\s*尾"
        r"[^0-9\r\n]{0,24}[\[【]\s*(\d)\s*[\]】]"
        r"[^0-9\r\n]{0,24}开\s*[:：]?\s*\d{2}\s*(?:准|错)"
    ),
    "chennian_laojiu_manager_tail": re.compile(
        r"陈年老酒[^0-9\r\n]{0,48}绝\s*杀\s*(?:1|一)\s*尾"
        r"[^0-9\r\n]{0,24}[\[【]\s*(\d)\s*[\]】]"
        r"[^0-9\r\n]{0,24}开\s*[:：]?\s*\d{2}\s*(?:准|错)"
    ),
    "aocai_zhi_jia_manager_tail": re.compile(
        r"澳彩之家[^0-9\r\n]{0,48}绝\s*杀\s*(?:1|一)\s*尾"
        r"[^0-9\r\n]{0,24}[\[【]\s*(\d)\s*[\]】]"
        r"[^0-9\r\n]{0,24}开\s*[:：]?\s*\d{2}\s*(?:准|错)"
    ),
    "jingying_zhandui_manager_tail": re.compile(
        r"精英战队[^0-9\r\n]{0,48}绝\s*杀\s*(?:1|一)\s*尾"
        r"[^0-9\r\n]{0,24}[\[【]\s*(\d)\s*[\]】]"
        r"[^0-9\r\n]{0,24}开\s*[:：]?\s*\d{2}\s*(?:准|错)"
    ),
    "huangjia_jinbao_manager_tail": re.compile(
        r"皇家金堡[^0-9\r\n]{0,48}绝\s*杀\s*(?:1|一)\s*尾"
        r"[^0-9\r\n]{0,24}[\[【]\s*(\d)\s*[\]】]"
        r"[^0-9\r\n]{0,24}开\s*[:：]?\s*\d{2}\s*(?:准|错)"
    ),
}


_JIANGYU_BOTTOM_CYCLE_PATTERN = re.compile(
    r"[?？]\s*绝\s*杀\s*一\s*尾\s*[?？]\s*"
    r"[\[【]\s*(\d)\s*尾\s*[\]】]\s*"
    r"开\s*[:：]?\s*\d{2}\s*(?:准|错)"
)


_QVUU_UNPUBLISHED_DRAW_PATTERN = re.compile(
    r"(?:开|中\s*开)\s*[:：]?\s*(?:[?？]\s*0{2,}|0{2,})(?:准|错)?"
)


_UNPUBLISHED_DRAW_PATTERN = re.compile(
    r"(?:开|中\s*开)\s*[:：]?\s*(?:[?？]\s*0{2,}|0{4,})"
    r"(?:准|错)?"
)


_CURRENT_TOPIC_PENDING_DRAW_PARSERS = frozenset({
    "yidianhong_current_tail",
    "dongfang_current_tail",
    "xukong_current_tail",
})


_CURRENT_TOPIC_REQUIRED_ANCHORS = {
    "dongfang_current_tail": ("作者:东方黑看", "网红帖", "精杀一尾"),
}


_CURRENT_TOPIC_TARGET_SEGMENT_PARSERS = frozenset({
    "danyu_current_tail",
    "jingtingnianhua_current_tail",
    "linlinjinzhi_current_tail",
    "yeyuehuazhao_current_tail",
    "xukong_current_tail",
})


_YEYUE_EXACT_PENDING_DRAW_PATTERN = re.compile(
    r"开\s*[:：]?\s*0{2}(?!0)\s*(?:准|错)"
)


def _extract_exact_current_topic_records(
    document: str,
    site_name: str,
    parser_name: str,
    exclude_keywords: tuple[str, ...],
    max_chunk_span: int,
    require_draw_signal: bool,
    target_period: int | None,
    require_site_keyword: bool,
    pick: str,
) -> list[Record]:
    """Parse only the site's complete prediction-and-draw row shape.

    The source page embeds an older, unpublished copy beside the current row
    history. A generic tail regex accepts both copies, so these URL-bound
    parsers require the site's full line shape. Standalone placeholder copies
    stay rejected; explicitly listed current parsers may keep the kill-tail
    value before the separate draw field is filled.
    """
    pattern = _EXACT_CURRENT_TOPIC_PATTERNS.get(parser_name)
    if pattern is None:
        return []
    value_pattern = _EXACT_CURRENT_TOPIC_VALUE_PATTERNS[parser_name]

    def row_matches(row_text: str) -> bool:
        return pattern.search(row_text) is not None or bool(
            target_period is not None
            and _UNPUBLISHED_DRAW_PATTERN.search(row_text)
            and value_pattern.search(row_text)
        )

    full_text = normalize_text(re.sub(r"<[^>]+>", " ", document))
    required_anchors = _CURRENT_TOPIC_REQUIRED_ANCHORS.get(parser_name, ())
    if required_anchors and not all(anchor in full_text for anchor in required_anchors):
        return []
    target_segment_parser = parser_name in _CURRENT_TOPIC_TARGET_SEGMENT_PARSERS
    if (
        target_segment_parser
        and "<" in document
        and require_site_keyword
        and normalize_text(site_name) not in full_text
    ):
        return []

    def make_record(period: int, row_text: str) -> Record | None:
        if exclude_keywords and not contains_none(row_text, exclude_keywords):
            return None
        if require_draw_signal and not _has_draw_signal(row_text):
            return None
        exact_yeyue_pending = bool(
            parser_name == "yeyuehuazhao_current_tail"
            and _YEYUE_EXACT_PENDING_DRAW_PATTERN.search(row_text)
        )
        placeholder = bool(
            (
                parser_name not in _CURRENT_TOPIC_PENDING_DRAW_PARSERS
                or (target_segment_parser and "<" in document and require_site_keyword)
            )
            and _UNPUBLISHED_DRAW_PATTERN.search(row_text)
            and not exact_yeyue_pending
        )
        match = pattern.search(row_text)
        if match is None:
            if not placeholder or target_period is None:
                return None
            match = value_pattern.search(row_text)
            if match is None:
                return None
        if placeholder and target_period is None:
            return None
        return Record(
            tail=int(match.group(1)),
            period=period,
            site_name=site_name,
            draw_text=extract_draw_text(row_text),
            source_snippet=_compact_snippet(
                f"{site_name} {_period_window(row_text, max_chunk_span)}"
            ),
            validation_error="开0000占位记录" if placeholder else "",
        )

    rows: list[tuple[int, str]] = []
    candidates: list[list[tuple[int, str]]] = []
    if "<" in document and ">" in document:
        parser = _DynamicHtmlParser()
        try:
            parser.feed(document)
            parser.close()
        except Exception:
            return []
        stack = [parser.root]
        while stack:
            node = stack.pop()
            classes = _dynamic_class_tokens(node)
            if classes & {"content", "d-content", "topic-content"}:
                node_rows: list[tuple[int, str]] = []
                for child in node.children:
                    if child.tag in {"script", "style", "noscript"}:
                        continue
                    row_text = normalize_text(_dynamic_node_text_in_order(child))
                    chunks = (
                        PERIOD_CHUNK_RE.split(row_text)
                        if target_segment_parser
                        else [row_text]
                    )
                    for chunk in chunks:
                        chunk = chunk.strip()
                        period_match = PERIOD_RE.match(chunk)
                        if period_match is None or not row_matches(chunk):
                            continue
                        node_rows.append((int(period_match.group(1)), chunk))
                if node_rows:
                    candidates.append(node_rows)
            stack.extend(reversed(node.children))
        if candidates:
            # The current article body is the candidate whose first valid row
            # is bound to the article title period.  In particular, the
            # 夜月花朝 page also exposes a longer historical mirror; selecting
            # it by length can move the direction boundary away from the
            # current row.  Keep all groups until title_period is known below.
            rows = candidates[0] if parser_name == "yeyuehuazhao_current_tail" else max(candidates, key=len)
        elif target_period is None and _UNPUBLISHED_DRAW_PATTERN.search(full_text):
            return []
        else:
            text = full_text
            chunks = [chunk.strip() for chunk in PERIOD_CHUNK_RE.split(text) if chunk.strip()]
            for chunk in chunks:
                period_match = PERIOD_RE.match(chunk)
                if period_match is None or not row_matches(chunk):
                    continue
                rows.append((int(period_match.group(1)), chunk))
    else:
        text = full_text
        chunks = [chunk.strip() for chunk in PERIOD_CHUNK_RE.split(text) if chunk.strip()]
        for chunk in chunks:
            period_match = PERIOD_RE.match(chunk)
            if period_match is None or not row_matches(chunk):
                continue
            rows.append((int(period_match.group(1)), chunk))

    if not rows:
        return []

    first_period = PERIOD_RE.search(full_text)
    title_period: int | None = None
    if target_segment_parser and "<" in document and ">" in document:
        parser = _DynamicHtmlParser()
        try:
            parser.feed(document)
            parser.close()
        except Exception:
            return []
        marker = "精杀一尾" if "精杀一尾" in full_text else "绝杀一尾"
        stack = [parser.root]
        while stack and title_period is None:
            node = stack.pop()
            classes = _dynamic_class_tokens(node)
            if classes & {
                "forum-head",
                "big-tit",
                "big-title",
                "title",
                "topic-title",
                "topic-head",
            }:
                node_text = normalize_text(_dynamic_node_text_in_order(node))
                if site_name in node_text or marker in node_text:
                    title_match = PERIOD_RE.search(node_text)
                    if title_match is not None:
                        title_period = int(title_match.group(1))
            stack.extend(reversed(node.children))
        if title_period is None and require_site_keyword:
            return []
    if title_period is None and first_period is not None:
        title_window = full_text[
            max(0, first_period.start() - 80) : first_period.end() + 100
        ]
        if site_name in title_window or (
            "<" in document
            and ("精杀一尾" in title_window or "绝杀一尾" in title_window)
        ):
            title_period = int(first_period.group(1))
    if title_period is None:
        title_period = max(period for period, _ in rows)

    if parser_name == "yeyuehuazhao_current_tail" and candidates:
        title_bound_candidates = [
            candidate
            for candidate in candidates
            if any(period == title_period for period, _ in candidate)
        ]
        if not title_bound_candidates:
            return []
        rows = next(
            (
                candidate
                for candidate in title_bound_candidates
                if candidate and candidate[0][0] == title_period
            ),
            title_bound_candidates[0],
        )

    if target_segment_parser:
        wanted_period = target_period if target_period is not None else title_period
        if wanted_period > title_period:
            return []

        valid_rows: list[tuple[int, str]] = []
        for period, row_text in rows:
            if (
                target_period is None
                and period > title_period
            ) or make_record(period, row_text) is None:
                continue
            valid_rows.append((period, row_text))
        if not valid_rows:
            return []

        if target_period is not None:
            return [
                record
                for period, row_text in valid_rows
                if (record := make_record(period, row_text)) is not None
            ]

        segments: list[list[tuple[int, str]]] = []
        current_segment = [valid_rows[0]]
        direction = 0
        for row in valid_rows[1:]:
            delta = row[0] - current_segment[-1][0]
            if delta in {-1, 1} and (direction == 0 or direction == delta):
                current_segment.append(row)
                direction = delta
                continue
            segments.append(current_segment)
            current_segment = [row]
            direction = 0
        segments.append(current_segment)

        selected_segments = [
            segment
            for segment in segments
            if any(period == wanted_period for period, _ in segment)
        ]
        if not selected_segments:
            return []
        selected_segments = [
            selected_segments[-1] if is_bottom_pick(pick) else selected_segments[0]
        ]
        return [
            record
            for segment in selected_segments
            for period, row_text in segment
            if (record := make_record(period, row_text)) is not None
        ]

    primary_rows = (
        rows if target_period is not None else _topic_main_select_contiguous_segment(rows, pick)
    )
    if not primary_rows:
        return []

    # A standalone legacy document contains an unpublished placeholder. It has
    # no article shell to identify it, so reject the whole document rather than
    # allowing its earlier rows to conflict with the current article.
    if "<" not in document and _UNPUBLISHED_DRAW_PATTERN.search(full_text):
        return []

    records: list[Record] = []
    for period, row_text in primary_rows:
        if target_period is None and period > title_period:
            continue
        record = make_record(period, row_text)
        if record is not None:
            records.append(record)
    return records


def _parse_liuxuan(document: str, site_name: str, parser_name: str, context: DedicatedContext) -> list[Record]:
    max_chunk_span = context.max_chunk_span
    text = normalize_text(re.sub('<[^>]+>', ' ', document))
    compact = text.replace(' ', '')
    required_anchors = ('澳彩六玄网[综合绝杀]', '澳彩最准开奖:87127.com')
    if not all((anchor in compact for anchor in required_anchors)):
        return []
    row_pattern = re.compile('绝\\s*杀\\s*\\[\\s*\\d\\s*头\\s*[.．]\\s*(\\d)\\s*尾\\s*[.．]\\s*(?:红|蓝|绿)\\s*(?:单|双)\\s*[.．]\\s*(?:龙|蛇|虎|羊|牛|猴|鼠|鸡|兔|猪|狗|马)\\s*肖\\s*\\]\\s*开\\s*([^\\s]{1,12})\\s*准')
    records: list[Record] = []
    for chunk in (part.strip() for part in PERIOD_CHUNK_RE.split(text) if part.strip()):
        period_match = PERIOD_RE.match(chunk)
        if period_match is None:
            continue
        match = row_pattern.search(chunk)
        if match is None:
            continue
        records.append(Record(tail=int(match.group(1)), period=int(period_match.group(1)), site_name=site_name, draw_text=extract_draw_text(chunk), source_snippet=_compact_snippet(f'{site_name} 澳彩六玄网 综合绝杀 {chunk}', max(80, max_chunk_span))))
    return records


def _parse_qvuu_two_tail(document: str, site_name: str, parser_name: str, context: DedicatedContext) -> list[Record]:
    exclude_keywords = context.exclude_keywords
    max_chunk_span = context.max_chunk_span
    require_draw_signal = context.require_draw_signal
    text = normalize_text(re.sub('<[^>]+>', ' ', document))
    pattern = QVUU_TWO_TAIL_PATTERNS[parser_name]
    records: list[Record] = []
    for chunk in (part.strip() for part in PERIOD_CHUNK_RE.split(text) if part.strip()):
        period_match = PERIOD_RE.match(chunk)
        if period_match is None:
            continue
        if exclude_keywords and (not contains_none(chunk, exclude_keywords)):
            continue
        if require_draw_signal and (not _has_draw_signal(chunk)):
            continue
        match = pattern.search(chunk)
        if match is None:
            continue
        first_tail, second_tail = (int(match.group(1)), int(match.group(2)))
        records.append(Record(tail=first_tail, period=int(period_match.group(1)), site_name=site_name, draw_text=extract_draw_text(chunk), source_snippet=_compact_snippet(f'{site_name} {chunk}', max(80, max_chunk_span)), tail_values=(first_tail, second_tail)))
    return records


def _parse_qvuu_one_tail(document: str, site_name: str, parser_name: str, context: DedicatedContext) -> list[Record]:
    exclude_keywords = context.exclude_keywords
    max_chunk_span = context.max_chunk_span
    require_draw_signal = context.require_draw_signal
    text = normalize_text(re.sub('<[^>]+>', ' ', document))
    pattern = _QVUU_ONE_TAIL_PATTERNS[parser_name]
    records: list[Record] = []
    for chunk in (part.strip() for part in PERIOD_CHUNK_RE.split(text) if part.strip()):
        period_match = PERIOD_RE.match(chunk)
        if period_match is None:
            continue
        if exclude_keywords and (not contains_none(chunk, exclude_keywords)):
            continue
        if require_draw_signal and (not _has_draw_signal(chunk)):
            continue
        match = pattern.search(chunk)
        if match is None:
            continue
        records.append(Record(tail=int(match.group(1)[-1]), period=int(period_match.group(1)), site_name=site_name, draw_text=extract_draw_text(chunk), source_snippet=_compact_snippet(f'{site_name} {chunk}', max(80, max_chunk_span))))
    return records


def _parse_manager_tail(document: str, site_name: str, parser_name: str, context: DedicatedContext) -> list[Record]:
    exclude_keywords = context.exclude_keywords
    max_chunk_span = context.max_chunk_span
    require_draw_signal = context.require_draw_signal
    require_site_keyword = context.require_site_keyword
    text = normalize_text(re.sub('<[^>]+>', ' ', document))
    if require_site_keyword and (not _site_keyword_present(text, site_name)):
        return []
    pattern = _MANAGER_TAIL_PATTERNS[parser_name]
    records: list[Record] = []
    for chunk in (part.strip() for part in PERIOD_CHUNK_RE.split(text) if part.strip()):
        period_match = PERIOD_RE.match(chunk)
        if period_match is None:
            continue
        if exclude_keywords and (not contains_none(chunk, exclude_keywords)):
            continue
        if require_draw_signal and (not _has_draw_signal(chunk)):
            continue
        match = pattern.search(chunk)
        if match is None:
            continue
        records.append(Record(tail=int(match.group(1)), period=int(period_match.group(1)), site_name=site_name, draw_text=extract_draw_text(chunk), source_snippet=_compact_snippet(f'{site_name} {chunk}', max(80, max_chunk_span))))
    return records


def _parse_huishouqiankun(document: str, site_name: str, parser_name: str, context: DedicatedContext) -> list[Record]:
    exclude_keywords = context.exclude_keywords
    max_chunk_span = context.max_chunk_span
    require_site_keyword = context.require_site_keyword
    text = normalize_text(re.sub('<[^>]+>', ' ', document))
    if require_site_keyword and (not _site_keyword_present(text, site_name)):
        return []
    records: list[Record] = []
    row_pattern = re.compile(f'{re.escape(site_name)}.{{0,40}}?绝\\s*杀\\s*一\\s*尾.{{0,20}}?\\[\\s*(\\d)\\s*\\].{{0,20}}?开\\s*:?\\s*(\\d{{2}})\\s*(准|错)')
    for chunk in (part.strip() for part in PERIOD_CHUNK_RE.split(text) if part.strip()):
        period_match = PERIOD_RE.match(chunk)
        if period_match is None or (exclude_keywords and (not contains_none(chunk, exclude_keywords))):
            continue
        match = row_pattern.search(chunk)
        if match is None:
            continue
        records.append(Record(tail=int(match.group(1)), period=int(period_match.group(1)), site_name=site_name, draw_text=extract_draw_text(chunk), source_snippet=_compact_snippet(_period_window(chunk, max_chunk_span))))
    return records


def _parse_jiangyu_bottom_cycle(
    document: str,
    site_name: str,
    parser_name: str,
    context: DedicatedContext,
) -> list[Record]:
    text = normalize_text(re.sub(r"<[^>]+>", " ", document))
    if "绝杀料" not in text or f"作者:{site_name}" not in text:
        return []
    rows: list[tuple[int, str, int]] = []
    for chunk in (part.strip() for part in PERIOD_CHUNK_RE.split(text) if part.strip()):
        period_match = PERIOD_RE.match(chunk)
        match = _JIANGYU_BOTTOM_CYCLE_PATTERN.search(chunk)
        if period_match is None or match is None:
            continue
        if context.exclude_keywords and not contains_none(chunk, context.exclude_keywords):
            continue
        if context.require_draw_signal and not _has_draw_signal(chunk):
            continue
        rows.append((int(period_match.group(1)), chunk, int(match.group(1))))
    if len(rows) < 6:
        return []
    selected = set(
        _topic_main_select_contiguous_segment(
            [(period, chunk) for period, chunk, _ in rows],
            context.pick,
        )
    )
    return [
        Record(
            tail=tail,
            period=period,
            site_name=site_name,
            draw_text=extract_draw_text(chunk),
            source_snippet=_compact_snippet(
                f"{site_name} 尾部主帖当前周期 {_period_window(chunk, context.max_chunk_span)}"
            ),
        )
        for period, chunk, tail in rows
        if (period, chunk) in selected
    ]


def _parse_caifu_table(document: str, site_name: str, parser_name: str, context: DedicatedContext) -> list[Record]:
    require_site_keyword = context.require_site_keyword
    unescaped = html.unescape(document)
    records = extract_table_records(unescaped, site_name, table_headers=('杀一尾',), table_anchor_keywords=('财富高手论坛【绝杀专区】',), table_required_headers=('期数', '杀一肖', '杀一尾', '杀一头', '开奖结果'), require_site_keyword=require_site_keyword)
    return [Record(tail=record.tail, period=record.period, site_name=record.site_name, draw_text=record.draw_text, value_text=record.value_text, source_snippet=_compact_snippet(f'{site_name} 绝杀专区 杀一尾 {record.source_snippet}')) for record in records]


_TTSS_LIST_DETAIL_TITLES = {
    "大江东": "大江东◆每期精杀一尾",
    "杀庄小子": "杀庄小子◆实战禁一尾",
    "想次方": "想次方精杀一尾专项区",
}
_TTSS_LIST_TAIL_RE = re.compile(r"[\[【]\s*(\d)\s*尾\s*[\]】]")


def _parse_ttss_list_article(
    document: str,
    site_name: str,
    parser_name: str,
    context: DedicatedContext,
) -> list[Record]:
    del parser_name
    title = _TTSS_LIST_DETAIL_TITLES.get(site_name)
    if title is None or "<" not in document or ">" not in document:
        return []

    parser = _DynamicHtmlParser()
    try:
        parser.feed(document)
        parser.close()
    except Exception:
        return []

    matching_details = []
    stack = [parser.root]
    normalized_title = normalize_text(title)
    while stack:
        node = stack.pop()
        if node.tag in {"script", "style", "noscript"}:
            continue
        if "detail" in _dynamic_class_tokens(node):
            direct_titles = [
                normalize_text(_dynamic_node_text_in_order(child))
                for child in node.children
                if "big-tit" in _dynamic_class_tokens(child)
            ]
            if any(normalized_title in text for text in direct_titles):
                matching_details.append(node)
        stack.extend(reversed(node.children))

    if not matching_details:
        return []
    if len(matching_details) > 1:
        raise LookupError(f"{site_name}详情标题区块不唯一")

    records: list[Record] = []
    invalid_periods: dict[int, str] = {}
    detail = matching_details[0]
    for child in detail.children:
        if child.tag != "p":
            continue
        row_text = normalize_text(_dynamic_node_text_in_order(child))
        period_match = PERIOD_RE.match(row_text)
        if period_match is None:
            continue
        period = int(period_match.group(1))
        tail_match = _TTSS_LIST_TAIL_RE.search(row_text)
        if tail_match is None:
            invalid_periods[period] = row_text
            continue
        records.append(
            Record(
                tail=int(tail_match.group(1)),
                period=period,
                site_name=site_name,
                draw_text=extract_draw_text(row_text),
                source_snippet=_compact_snippet(
                    f"{site_name} {title} {row_text}"
                ),
            )
        )

    if context.target_period in invalid_periods:
        raise LookupError(
            f"{context.target_period}期{site_name}详情杀尾字段无效"
        )
    return records


_KAIJIANGFACAI_SECTION_OPEN_RE = re.compile(
    r"<div\b(?=[^>]*\bid\s*=\s*['\"]yxym['\"])[^>]*>",
    re.IGNORECASE,
)
_KAIJIANGFACAI_TITLE = "开奖发财【综合杀料】11447.COM"
_KAIJIANGFACAI_HEADERS = ("期数", "杀尾", "杀肖", "杀合", "杀波", "开奖")
_KAIJIANGFACAI_TITLE_RE = re.compile(
    r"<div\b[^>]*\bclass\s*=\s*['\"][^'\"]*\blist-title\b[^'\"]*['\"][^>]*>"
    r"(?P<title>.*?)</div\s*>",
    re.IGNORECASE | re.DOTALL,
)


def _kaijiangfacai_table_scopes(document: str) -> list[str]:
    """Return complete target tables from the exact URL-bound section only."""
    unescaped = html.unescape(document)
    scopes: list[str] = []
    for section_match in _KAIJIANGFACAI_SECTION_OPEN_RE.finditer(unescaped):
        table_end = re.search(r"</table\s*>", unescaped[section_match.end():], re.IGNORECASE)
        if table_end is None:
            continue
        end = section_match.end() + table_end.end()
        scope = unescaped[section_match.start():end]
        title_match = _KAIJIANGFACAI_TITLE_RE.search(scope)
        if title_match is None:
            continue
        title = normalize_text(re.sub(r"<[^>]+>", " ", title_match.group("title")))
        if title == normalize_text(_KAIJIANGFACAI_TITLE):
            scopes.append(scope)
    return scopes


def _parse_kaijiangfacai_table(
    document: str,
    site_name: str,
    parser_name: str,
    context: DedicatedContext,
) -> list[Record]:
    scopes = _kaijiangfacai_table_scopes(document)
    if not scopes:
        return []
    if len(scopes) > 1:
        raise LookupError("开奖发财目标栏目区块不唯一")

    parser = TableParser()
    try:
        parser.feed(scopes[0])
        parser.close()
    except Exception:
        return []
    if not parser.rows or tuple(parser.rows[0]) != _KAIJIANGFACAI_HEADERS:
        return []

    records: list[Record] = []
    invalid_by_period: dict[int, str] = {}
    values_by_period: dict[int, set[int]] = {}
    seen_presentations: set[tuple[int, int]] = set()
    for row in parser.rows[1:]:
        if len(row) != len(_KAIJIANGFACAI_HEADERS):
            continue
        period_match = re.fullmatch(r"(\d{1,3})期", normalize_text(row[0]))
        if period_match is None:
            continue
        period = int(period_match.group(1))
        raw_tail = normalize_text(row[1])
        tail_match = re.fullmatch(r"([0-9])尾", raw_tail)
        if tail_match is None:
            invalid_by_period[period] = raw_tail or "空值"
            continue
        tail = int(tail_match.group(1))
        values_by_period.setdefault(period, set()).add(tail)
        if len(values_by_period[period]) > 1:
            values = "、".join(str(value) for value in sorted(values_by_period[period]))
            raise LookupError(f"{period}期存在多个候选且数据冲突: {values}")
        presentation = (period, tail)
        if presentation in seen_presentations:
            continue
        seen_presentations.add(presentation)
        row_text = " ".join(normalize_text(cell) for cell in row)
        records.append(
            Record(
                tail=tail,
                period=period,
                site_name=site_name,
                draw_text=normalize_text(row[5]),
                source_snippet=_compact_snippet(
                    f"{site_name} {_KAIJIANGFACAI_TITLE} {row_text}"
                ),
            )
        )

    if context.target_period in invalid_by_period:
        raw_tail = invalid_by_period[context.target_period]
        raise LookupError(
            f"{context.target_period}期杀尾字段无效: {raw_tail}"
        )
    return records


def _parse_exact_current_topic(document: str, site_name: str, parser_name: str, context: DedicatedContext) -> list[Record]:
    exclude_keywords = context.exclude_keywords
    max_chunk_span = context.max_chunk_span
    require_draw_signal = context.require_draw_signal
    target_period = context.target_period
    require_site_keyword = context.require_site_keyword
    pick = context.pick
    return _extract_exact_current_topic_records(
        document,
        site_name,
        parser_name,
        exclude_keywords,
        max_chunk_span,
        require_draw_signal,
        target_period,
        require_site_keyword,
        pick,
    )


def _parse_topic_main(document: str, site_name: str, parser_name: str, context: DedicatedContext) -> list[Record]:
    exclude_keywords = context.exclude_keywords
    max_chunk_span = context.max_chunk_span
    require_draw_signal = context.require_draw_signal
    target_period = context.target_period
    pick = context.pick
    return _extract_topic_main_dedicated_records(
        document,
        site_name,
        parser_name,
        exclude_keywords,
        max_chunk_span,
        require_draw_signal,
        target_period,
        pick,
        context.allow_same_period_records,
    )


def _parse_published_topic_body(document: str, site_name: str, parser_name: str, context: DedicatedContext) -> list[Record]:
    return extract_topic_published_body_records(
        document,
        site_name,
        context.chunk_keywords,
        context.exclude_keywords,
        context.max_chunk_span,
        context.require_draw_signal,
        context.target_period,
        context.pick,
        context.allow_same_period_records,
    )


def _parse_qingqingdandan_topic(document: str, site_name: str, parser_name: str, context: DedicatedContext) -> list[Record]:
    return extract_qingqingdandan_topic_records(
        document,
        site_name,
        context.chunk_keywords,
        context.exclude_keywords,
        context.max_chunk_span,
        context.require_draw_signal,
        context.target_period,
        context.pick,
        context.allow_same_period_records,
    )


def _parse_generic_dedicated(document: str, site_name: str, parser_name: str, context: DedicatedContext) -> list[Record]:
    exclude_keywords = context.exclude_keywords
    max_chunk_span = context.max_chunk_span
    require_draw_signal = context.require_draw_signal
    require_site_keyword = context.require_site_keyword
    anchor_span = context.anchor_span
    text = normalize_text(re.sub('<[^>]+>', ' ', document))
    if require_site_keyword and (not _site_keyword_present(text, site_name)):
        return []
    patterns = {'lainan_yixin_parenthesized': re.compile('绝\\s*杀\\s*一\\s*尾[^0-9]{0,80}(?:[=＝〓:：]\\s*)?[【\\[\\(（]\\s*(\\d{1,3})\\s*[】\\]\\)）]?'), 'zao_che_kill_tail': re.compile('绝\\s*杀\\s*一\\s*尾[^0-9]{0,80}[【\\[\\(（]?\\s*杀\\s*(\\d)\\s*尾'), 'xukong_precision_tail': re.compile('精\\s*杀\\s*一\\s*尾[^0-9]{0,80}(\\d)\\s*尾'), 'ziche_precise_tail': re.compile('精准\\s*杀\\s*尾[^0-9]{0,12}\\[\\s*(\\d)\\s*\\]'), 'saodi_kill_one_tail': re.compile('绝\\s*杀\\s*(?:1|一)\\s*尾[^0-9]{0,12}\\[\\s*(\\d)\\s*\\]'), 'fengwu_kill_one_tail': re.compile('凤舞九天.{0,20}?绝\\s*杀\\s*(?:1|一)\\s*尾[^0-9]{0,20}\\[\\s*(\\d)\\s*\\]'), 'hengcai_kill_one_tail': re.compile('横财聚彩.{0,20}?绝\\s*杀\\s*(?:1|一)\\s*尾[^0-9]{0,20}\\[\\s*(\\d)\\s*\\]'), 'renyoupiaobo_art_zhuanqu_tail': re.compile('\\[\\s*任由漂泊杀尾数\\s*\\]\\s*[\\[【]\\s*(\\d)\\s*[\\]】]'), 'zhiqiuwending_art_zhuanqu_tail': re.compile('绝\\s*杀\\s*一\\s*尾\\s*[\\[【]\\s*(\\d)\\s*[\\]】]'), 'yanhuo_current_tail': re.compile('杀\\s*一\\s*尾\\s*\\[\\s*(\\d{1,3})\\s*尾\\s*\\]'), 'shanhaijing_current_tail': re.compile('杀\\s*一\\s*尾\\s*\\(\\s*(\\d)\\s*尾\\s*\\)'), 'xiaoge_current_tail': re.compile('[『【\\[]\\s*笑歌戏舞\\s*[』】\\]]\\s*杀\\s*[【\\[\\(（]\\s*(\\d{1,3})\\s*[】\\]\\)）]\\s*尾'), 'baihua_current_tail': re.compile('绝\\s*杀\\s*一\\s*尾\\s*[\\(（]\\s*(\\d{1,3})\\s*[\\)）]'), 'liangxiao_current_tail': re.compile('绝\\s*杀\\s*一\\s*尾\\s*[】\\]]?\\s*[【\\[]\\s*(\\d{1,3})\\s*[】\\]]'), 'dongxin_current_tail': re.compile('绝\\s*杀\\s*一\\s*尾\\s*\\]\\s*\\[\\s*(\\d)\\s*\\]'), 'liuhehongtu_manager_tail': re.compile('六合宏图.{0,20}?绝\\s*杀\\s*1\\s*尾[^0-9]{0,20}\\[\\s*(\\d)\\s*\\]'), 'duzhancaijing_manager_tail': re.compile('独占财经.{0,20}?绝\\s*杀\\s*一\\s*尾[^0-9]{0,20}\\[\\s*(\\d)\\s*\\]'), 'dishengzhuangba_manager_tail': re.compile('低声妆罢.{0,20}?绝\\s*杀\\s*一\\s*尾[^0-9]{0,20}[\\[【]\\s*(\\d)\\s*[\\]】]'), 'wangebanxia_manager_tail': re.compile('挽歌半夏.{0,20}?绝\\s*杀\\s*一\\s*尾[^0-9]{0,20}\\[\\s*(\\d)\\s*\\]'), 'zhouyi_qvuu_tail': re.compile('绝\\s*杀\\s*一\\s*尾[^0-9]{0,12}[\\[【《(（]?\\s*(\\d)\\s*[\\]】》)）]?'), 'zengshi_qvuu_tail': re.compile('曾氏\\s*绝\\s*杀\\s*一\\s*尾[^0-9]{0,16}[\\[【《(（]?\\s*(\\d)\\s*[\\]】》)）]?'), 'dute_zhaopai_profile_tail': re.compile('精\\s*杀\\s*一\\s*尾\\s*专区[^0-9]{0,12}[◆◇:：]?\\s*(\\d)\\s*开'), 'zhuhong_doujiang_profile_tail': re.compile('绝\\s*杀\\s*1\\s*尾\\s*[\\[【《(（]?\\s*(\\d)\\s*[\\]】》)）]?\\s*尾\\s*开'), 'jianchi_139779_topic_tail': re.compile('坚持战斗[^0-9]{0,80}绝\\s*杀\\s*一\\s*尾[^0-9]{0,20}\\[\\s*(\\d)\\s*\\]'), 'yidai_kaimo_139779_topic_tail': re.compile('一代楷模[^0-9]{0,80}绝\\s*杀\\s*一\\s*尾[^0-9]{0,20}\\[\\s*(\\d)\\s*\\]'), 'wuliang_shoufo_139779_topic_tail': re.compile('无量寿佛[^0-9]{0,80}绝\\s*杀\\s*(?:1|一)\\s*尾[^0-9]{0,20}\\[\\s*(\\d)\\s*\\]')}
    pattern = patterns.get(parser_name)
    if pattern is None:
        return []
    article_scopes = {'ziche_precise_tail': (re.compile('\\d+\\s*期\\s*:?\\s*(?:澳门)?子车唇鸾\\s*\\[\\s*绝杀一尾\\s*\\]\\s*已更新.{0,160}?作者\\s*:\\s*子车唇鸾'), ('博彩必备',)), 'saodi_kill_one_tail': (re.compile('绝杀贴\\s*\\d+\\s*期\\s*\\[\\s*绝杀一尾\\s*\\]\\s*已更新.{0,160}?作者\\s*:\\s*扫地焚香'), ('博彩必备',)), 'fengwu_kill_one_tail': (re.compile('\\d+\\s*期\\s*:\\s*凤舞九天\\s*\\[\\s*绝杀1尾\\s*\\]\\s*〓?\\s*成就财富'), ()), 'hengcai_kill_one_tail': (re.compile('\\d+\\s*期\\s*:\\s*横财聚彩\\s*\\[\\s*绝杀一尾\\s*\\]\\s*〓?\\s*高薪聘请'), ()), 'zhiqiuwending_art_zhuanqu_tail': (re.compile('\\d+\\s*期\\s*[:：]\\s*[\\[【]?\\s*绝\\s*杀\\s*一\\s*尾\\s*[\\]】]?\\s*只求稳定不求最好'), ('澳门报码论坛提供',)), 'yanhuo_current_tail': (re.compile('\\d+\\s*期\\s*:\\s*澳\\s*门\\s*百\\s*事\\s*通\\s*\\[\\s*无语稳杀一尾\\s*\\]\\s*已公开\\s*煙火四射\\s*发表于'), ()), 'shanhaijing_current_tail': (re.compile('热门高手\\s*\\d+\\s*期\\s*:\\s*[\\[〖【]?\\s*精品好料\\s*[—-]\\s*绝杀一尾\\s*/\\s*特19\\s*[〗\\]】]?\\s*震撼六合界\\s*[!！]\\s*作者\\s*:\\s*74757[gd]\\.com'), ()), 'baihua_current_tail': (re.compile('\\d+\\s*期\\s*[【\\[]?\\s*绝杀一尾\\s*[】\\]]?\\s*准准准\\s*作者\\s*:\\s*百花齐放'), ('★★ 博彩必备',)), 'liangxiao_current_tail': (re.compile('\\d+\\s*期\\s*[【\\[]?\\s*绝杀一\\s*尾\\s*[】\\]]?\\s*两小无猜\\s*发表于'), ('上一篇',)), 'dongxin_current_tail': (re.compile('高手帖\\s*\\d+\\s*期\\s*\\[\\s*绝杀一尾\\s*\\]\\s*已更新\\s*作者\\s*:\\s*动心骇目'), ()), 'liuhehongtu_manager_tail': (re.compile('六合宏图\\s*\\d+\\s*期\\s*:\\s*\\[\\s*绝杀1尾\\s*\\]\\s*〓?\\s*更新中奖'), ()), 'duzhancaijing_manager_tail': (re.compile('独占财经\\s*\\d+\\s*期\\s*:\\s*\\[\\s*绝杀一尾\\s*\\]\\s*〓?\\s*信心百倍'), ()), 'dishengzhuangba_manager_tail': (re.compile('\\d+\\s*期\\s*[:：]\\s*[【\\[]\\s*绝杀一尾\\s*[】\\]]\\s*〓?\\s*一心为民'), ()), 'wangebanxia_manager_tail': (re.compile('挽歌半夏\\s*\\d+\\s*期\\s*:\\s*\\[\\s*绝杀一尾\\s*\\]\\s*〓?\\s*关注中奖'), ()), 'zhouyi_qvuu_tail': (re.compile('绝\\s*杀\\s*一\\s*尾'), ()), 'zengshi_qvuu_tail': (re.compile('\\d+\\s*期[^\\n]{0,40}曾氏\\s*绝\\s*杀\\s*一\\s*尾'), ()), 'dute_zhaopai_profile_tail': (re.compile('\\d+\\s*期[^\\n]{0,40}精\\s*杀\\s*一\\s*尾\\s*专区'), ()), 'zhuhong_doujiang_profile_tail': (re.compile('\\d+\\s*期[^\\n]{0,30}绝\\s*杀\\s*1\\s*尾'), ()), 'jianchi_139779_topic_tail': (re.compile('\\d+\\s*期\\s*:\\s*坚持战斗.*?作者\\s*:\\s*坚持战斗'), ('下一贴:', '上一贴:')), 'yidai_kaimo_139779_topic_tail': (re.compile('\\d+\\s*期\\s*:\\s*一代楷模.*?作者\\s*:\\s*一代楷模'), ('下一贴:', '上一贴:')), 'wuliang_shoufo_139779_topic_tail': (re.compile('\\d+\\s*期\\s*:\\s*无量寿佛.*?作者\\s*:\\s*无量寿佛'), ('下一贴:', '上一贴:'))}
    scope = article_scopes.get(parser_name)
    require_keyword_in_chunk = require_site_keyword and scope is None
    if scope is not None:
        header_pattern, stop_keywords = scope
        header = header_pattern.search(text)
        if header is None:
            return []
        text = text[header.start():]
        stop_positions = [text.find(keyword) for keyword in stop_keywords if text.find(keyword) >= 0]
        if stop_positions:
            text = text[:min(stop_positions)]
        if parser_name == 'shanhaijing_current_tail':
            next_header = header_pattern.search(text, header.end() - header.start())
            if next_header:
                text = text[:next_header.start()]
    records: list[Record] = []
    scoped_texts = [text]
    if require_keyword_in_chunk:
        normalized_site = normalize_text(site_name)
        starts = [
            match.start()
            for match in re.finditer(re.escape(normalized_site), text)
        ]
        scoped_texts = [
            text[
                max(0, start - 8): min(
                    starts[index + 1] if index + 1 < len(starts) else len(text),
                    start + anchor_span,
                )
            ]
            for index, start in enumerate(starts)
        ]
    for scoped_text in scoped_texts:
        chunks = [
            chunk.strip()
            for chunk in PERIOD_CHUNK_RE.split(scoped_text)
            if chunk.strip()
        ]
        for chunk in chunks:
            period_match = PERIOD_RE.match(chunk)
            if not period_match:
                continue
            if exclude_keywords and (not contains_none(chunk, exclude_keywords)):
                continue
            if require_draw_signal and (not _has_draw_signal(chunk)):
                continue
            match = pattern.search(chunk)
            if not match:
                continue
            if parser_name in {'baihua_current_tail', 'liangxiao_current_tail'}:
                current_period = PERIOD_RE.match(scoped_text)
                if (
                    context.target_period is None
                    and current_period
                    and int(period_match.group(1)) > int(current_period.group(1))
                ):
                    break
            placeholder_error = ""
            if parser_name in {'xiaoge_current_tail', 'baihua_current_tail', 'liangxiao_current_tail'} and re.search('开\\s*0{4}', chunk):
                if context.target_period is None:
                    continue
                placeholder_error = "开0000占位记录"
            records.append(Record(tail=int(match.group(1)[-1]), period=int(period_match.group(1)), site_name=site_name, draw_text=extract_draw_text(chunk), source_snippet=_compact_snippet(f'{site_name} {_period_window(chunk, max_chunk_span)}'), validation_error=placeholder_error))
    return records


GENERIC_DEDICATED_PARSER_NAMES = ('zao_che_kill_tail', 'xukong_precision_tail', 'ziche_precise_tail', 'saodi_kill_one_tail', 'fengwu_kill_one_tail', 'hengcai_kill_one_tail', 'renyoupiaobo_art_zhuanqu_tail', 'zhiqiuwending_art_zhuanqu_tail', 'yanhuo_current_tail', 'shanhaijing_current_tail', 'xiaoge_current_tail', 'baihua_current_tail', 'liangxiao_current_tail', 'dongxin_current_tail', 'liuhehongtu_manager_tail', 'duzhancaijing_manager_tail', 'dishengzhuangba_manager_tail', 'wangebanxia_manager_tail', 'zhouyi_qvuu_tail', 'zengshi_qvuu_tail', 'dute_zhaopai_profile_tail', 'zhuhong_doujiang_profile_tail', 'jianchi_139779_topic_tail', 'yidai_kaimo_139779_topic_tail', 'wuliang_shoufo_139779_topic_tail')

DEDICATED_PARSER_HANDLERS = {}
DEDICATED_PARSER_HANDLERS["liuxuan_zhjs_tail"] = _parse_liuxuan
DEDICATED_PARSER_HANDLERS.update({name: _parse_qvuu_two_tail for name in QVUU_TWO_TAIL_PATTERNS})
DEDICATED_PARSER_HANDLERS.update({name: _parse_qvuu_one_tail for name in _QVUU_ONE_TAIL_PATTERNS})
DEDICATED_PARSER_HANDLERS.update({name: _parse_manager_tail for name in _MANAGER_TAIL_PATTERNS})
DEDICATED_PARSER_HANDLERS["huishouqiankun_topic_tail"] = _parse_huishouqiankun
DEDICATED_PARSER_HANDLERS["jiangyu_bottom_cycle_tail"] = _parse_jiangyu_bottom_cycle
DEDICATED_PARSER_HANDLERS["caifu_gaoshou_kill_table"] = _parse_caifu_table
DEDICATED_PARSER_HANDLERS["ttss_list_article_top_tail"] = _parse_ttss_list_article
DEDICATED_PARSER_HANDLERS["kaijiangfacai_combined_kill_table"] = _parse_kaijiangfacai_table
DEDICATED_PARSER_HANDLERS.update({name: _parse_exact_current_topic for name in _EXACT_CURRENT_TOPIC_PATTERNS})
DEDICATED_PARSER_HANDLERS.update({name: _parse_topic_main for name in TOPIC_MAIN_DEDICATED_PARSERS})
DEDICATED_PARSER_HANDLERS["topic_published_body_tail"] = _parse_published_topic_body
DEDICATED_PARSER_HANDLERS["qingqingdandan_topic_tail"] = _parse_qingqingdandan_topic
DEDICATED_PARSER_HANDLERS.update({name: _parse_generic_dedicated for name in GENERIC_DEDICATED_PARSER_NAMES})


def _parse_lainan_yixin(document: str, site_name: str, parser_name: str, context: DedicatedContext) -> list[Record]:
    return extract_lainan_yixin_bottom_records(
        document,
        site_name,
        context.exclude_keywords,
        context.max_chunk_span,
        context.require_draw_signal,
        context.require_site_keyword,
        context.anchor_span,
        context.target_period,
        context.pick,
    )


DEDICATED_PARSER_HANDLERS["lainan_yixin_parenthesized"] = _parse_lainan_yixin


def extract_dedicated_records(
    document: str,
    site_name: str,
    parser_name: str,
    exclude_keywords: tuple[str, ...] = DEFAULT_EXCLUDE_KEYWORDS,
    chunk_keywords: tuple[str, ...] = (),
    max_chunk_span: int = 240,
    require_draw_signal: bool = True,
    require_site_keyword: bool = True,
    target_period: int | None = None,
    pick: str = "top",
    anchor_span: int = 1500,
    allow_same_period_records: bool = False,
) -> list[Record]:
    handler = DEDICATED_PARSER_HANDLERS.get(parser_name)
    if handler is None:
        return []
    context = DedicatedContext(
        exclude_keywords,
        chunk_keywords,
        max_chunk_span,
        require_draw_signal,
        require_site_keyword,
        target_period,
        pick,
        anchor_span,
        allow_same_period_records,
    )
    return handler(document, site_name, parser_name, context)
