from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import cast

from shawei.config.constants import DEFAULT_EXCLUDE_KEYWORDS, PERIOD_CHUNK_RE, PERIOD_RE
from shawei.domain.models import Record
from shawei.domain.text import contains_none, is_bottom_pick, normalize_text
from shawei.parsers.common import _compact_snippet, _has_draw_signal, extract_draw_text


class _DynamicHtmlNode:
    def __init__(self, tag: str, attrs: dict[str, str], parent=None):
        self.tag = tag.lower()
        self.attrs = attrs
        self.parent = parent
        self.children: list["_DynamicHtmlNode"] = []
        self.text_parts: list[str] = []
        self.ordered_parts: list[object] = []


class _DynamicHtmlParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _DynamicHtmlNode("root", {})
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs) -> None:
        node = _DynamicHtmlNode(
            tag,
            {str(key).lower(): str(value or "") for key, value in attrs},
            self.stack[-1],
        )
        self.stack[-1].children.append(node)
        self.stack[-1].ordered_parts.append(node)
        if tag.lower() not in {"area", "base", "br", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag.lower():
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == lowered:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].text_parts.append(data)
        self.stack[-1].ordered_parts.append(data)


def _dynamic_node_text(node: _DynamicHtmlNode) -> str:
    if node.tag in {"script", "style", "noscript"}:
        return ""
    return normalize_text(" ".join(node.text_parts + [_dynamic_node_text(child) for child in node.children]))


def _dynamic_node_text_in_order(node: _DynamicHtmlNode) -> str:
    if node.tag in {"script", "style", "noscript"}:
        return ""
    parts = node.ordered_parts or [*node.text_parts, *node.children]
    values = [
        part
        if isinstance(part, str)
        else _dynamic_node_text_in_order(cast(_DynamicHtmlNode, part))
        for part in parts
    ]
    return normalize_text(" ".join(value for value in values if value))


TOPIC_MAIN_DEDICATED_PARSERS = frozenset({
    "forum_main_kill_tail",
    "saodi_topic_main_tail",
    "dongxin_topic_main_tail",
    "yanhuo_topic_main_tail",
    "xiaoge_topic_main_tail",
    "fuhuo_topic_main_tail",
    "muzhi_topic_main_tail",
    "shanhaijing_topic_main_tail",
    "fengchi_topic_main_tail",
    "jianren_topic_main_tail",
    "lulu_topic_main_tail",
    "chuimao_topic_tail",
    "chuimao_primary_topic_tail",
    "bujuxiaojie_topic_tail",
    "xingshuchangwan_topic_tail",
    "wanbuwunai_topic_tail",
    "laoqirenxiaowei_topic_tail",
    "zhongliwanzhao_topic_tail",
    "gaofengliangjie_topic_tail",
    "gulichunyi_topic_tail",
    "daidai_kill_tail",
    "chuanjue_xizi_topic_tail",
    "bamian_shifeng_topic_tail",
    "huayan_shijie_topic_tail",
})


TOPIC_MAIN_CONTIGUOUS_PARSERS = frozenset({
    "saodi_topic_main_tail",
    "bujuxiaojie_topic_tail",
    "xingshuchangwan_topic_tail",
    "wanbuwunai_topic_tail",
    "laoqirenxiaowei_topic_tail",
    "zhongliwanzhao_topic_tail",
    "gaofengliangjie_topic_tail",
    "gulichunyi_topic_tail",
    "daidai_kill_tail",
    "chuanjue_xizi_topic_tail",
    "bamian_shifeng_topic_tail",
    "huayan_shijie_topic_tail",
})


TOPIC_MAIN_REQUIRE_MARKER_CONTEXT_PARSERS = frozenset({
    "forum_main_kill_tail",
    "saodi_topic_main_tail",
    "dongxin_topic_main_tail",
    "yanhuo_topic_main_tail",
    "chuanjue_xizi_topic_tail",
    "bamian_shifeng_topic_tail",
    "huayan_shijie_topic_tail",
})


TOPIC_MAIN_TARGET_TITLE_TOLERANT_PARSERS = TOPIC_MAIN_CONTIGUOUS_PARSERS | {
    "forum_main_kill_tail",
    "chuimao_topic_tail",
    "chuimao_primary_topic_tail",
}


TOPIC_MAIN_TARGET_PERIOD_DEFERRED_PARSERS = frozenset({
    "forum_main_kill_tail",
})


_TOPIC_MAIN_PARSER_PATTERNS = {
    "forum_main_kill_tail": re.compile(
        r"(?:[\[【《(（]\s*)?(?:绝|爆)\s*杀\s*(?:1|一)\s*尾"
        r"\s*[\]】》)）]?\s*[\[【《(（)]\s*(?:杀\s*)?(\d{1,3})\s*(?:尾)?\s*[\]】》)）]"
    ),
    "saodi_topic_main_tail": re.compile(
        r"(?:[\[【(（]\s*)?绝\s*杀\s*(?:1|一)\s*尾"
        r"\s*[\]】)）]?\s*[\[【(（)]\s*(\d{1,3})\s*[\]】)）]"
    ),
    "dongxin_topic_main_tail": re.compile(
        r"绝\s*杀\s*一\s*尾\s*\]\s*\[\s*(\d{1,3})\s*\]"
    ),
    "yanhuo_topic_main_tail": re.compile(
        r"杀\s*一\s*尾\s*[\[【]\s*(\d{1,3})\s*尾\s*[\]】]"
    ),
    "xiaoge_topic_main_tail": re.compile(
        r"[『【\[]\s*笑歌戏舞\s*[』】\]]\s*杀\s*[【\[\(（]\s*(\d{1,3})\s*[】\]\)）]\s*尾"
    ),
    "fuhuo_topic_main_tail": re.compile(
        r"绝\s*杀\s*一\s*尾\s*◆\s*[\[\(（]\s*(\d{1,3})\s*[\]\)）]"
    ),
    "muzhi_topic_main_tail": re.compile(
        r"绝\s*杀\s*一\s*尾[^0-9]{0,20}[\[\(（]\s*(\d{1,3})\s*尾?\s*[\]\)）]"
    ),
    "shanhaijing_topic_main_tail": re.compile(
        r"杀\s*一\s*尾\s*[\(（]\s*(\d)\s*尾\s*[\)）]"
    ),
    "fengchi_topic_main_tail": re.compile(
        r"(?=[^\r\n]*绝\s*杀\s*一\s*尾)"
        r"(?=[^\r\n]*一\s*[\[【\(（]\s*(\d{1,3})\s*尾\s*[\]】\)）])"
    ),
    "jianren_topic_main_tail": re.compile(
        r"(?=[^\r\n]*绝\s*杀\s*一\s*尾)"
        r"(?=[^\r\n]*[\[【\(（]\s*(\d{1,3})\s*[\]】\)）])"
    ),
    "lulu_topic_main_tail": re.compile(
        r"绝\s*杀\s*一\s*尾[^0-9]{0,20}[\[\(（]\s*(\d{1,3})\s*[\]\)）]"
    ),
    "chuimao_topic_tail": re.compile(
        r"(?=[^\r\n]*杀\s*肖\s*杀\s*尾)"
        r"(?=[^\r\n]*杀\s*(?:龙|蛇|虎|羊|牛|猴|鼠|鸡|兔|猪|狗|马)\s*肖\s*杀\s*(\d)\s*尾)"
    ),
    "chuimao_primary_topic_tail": re.compile(
        r"(?=[^\r\n]*杀\s*肖\s*杀\s*尾)"
        r"(?=[^\r\n]*杀\s*(?:龙|蛇|虎|羊|牛|猴|鼠|鸡|兔|猪|狗|马)\s*肖\s*杀\s*(\d)\s*尾)"
    ),
    "bujuxiaojie_topic_tail": re.compile(
        r"杀\s*肖\s*杀\s*尾\s*[\[【(（][^\]】)）\r\n]{0,24}?[+＋]\s*(\d)\s*尾"
    ),
    "xingshuchangwan_topic_tail": re.compile(
        r"杀\s*肖\s*杀\s*尾\s*[\[【(（][^\]】)）\r\n]{0,24}?[+＋]\s*(\d)\s*尾"
    ),
    "wanbuwunai_topic_tail": re.compile(
        r"绝\s*杀\s*1\s*[.．]\s*肖\s*1\s*[.．]\s*尾\s*[\[【(（][^\]】)）\r\n]{0,24}?[.．]\s*(\d)\s*尾"
    ),
    "laoqirenxiaowei_topic_tail": re.compile(
        r"绝\s*杀\s*1\s*[.．]\s*肖\s*1\s*[.．]\s*尾\s*[\[【(（][^\]】)）\r\n]{0,24}?[.．]?\s*(\d)\s*尾"
    ),
    "zhongliwanzhao_topic_tail": re.compile(
        r"绝\s*杀\s*1\s*[.．]\s*肖\s*1\s*[.．]\s*尾\s*[\[【(（][^\]】)）\r\n]{0,24}?[.．]\s*(\d)\s*尾"
    ),
    "gaofengliangjie_topic_tail": re.compile(
        r"绝\s*杀\s*1\s*肖\s*1\s*尾\s*[\]】)）]?\s*[\[【(（][^\]】)）\r\n]{0,24}?(\d)\s*尾"
    ),
    "gulichunyi_topic_tail": re.compile(
        r"杀\s*肖\s*杀\s*尾\s*[\[【(（][^\]】)）\r\n]{0,24}?[.．]\s*(\d)\s*尾"
    ),
    "daidai_kill_tail": re.compile(
        r"呆\s*呆\s*杀\s*[\[【(（]\s*"
        r"(?:龙|蛇|虎|羊|牛|猴|鼠|鸡|兔|猪|狗|马)\s*肖\s*[+＋]\s*"
        r"\d\s*头\s*(?:单|双)\s*[+＋]\s*(\d)\s*尾\s*[\]】)）]"
    ),
    "chuanjue_xizi_topic_tail": re.compile(
        r"杀\s*一\s*尾\s*[\[【(（]\s*(\d)\s*尾\s*[\]】)）]"
    ),
    "bamian_shifeng_topic_tail": re.compile(
        r"杀\s*1\s*尾\s*[\[【(（]\s*(\d)\s*[\]】)）]"
    ),
    "huayan_shijie_topic_tail": re.compile(
        r"绝\s*杀\s*1\s*尾\s*☆\s*〖\s*(\d)\1{2}\s*〗"
    ),
}


_FORUM_YUANTING_BARE_KILL_TAIL_PATTERN = re.compile(
    r"(?:[\[【《(（]\s*)?(?:(?:绝|爆)\s*)?杀\s*(?:1|一)\s*尾"
    r"\s*[\]】》)）]?\s*[\[【《(（)]\s*(?:杀\s*)?(\d{1,3})\s*(?:尾)?\s*[\]】》)）]"
)


_TOPIC_MAIN_PARSER_MARKERS = {
    "saodi_topic_main_tail": ("扫地焚香",),
    "dongxin_topic_main_tail": ("动心骇目",),
    "yanhuo_topic_main_tail": ("煙火四射",),
    "xiaoge_topic_main_tail": ("笑歌戏舞",),
    "fuhuo_topic_main_tail": ("赴火蹈刃",),
    "muzhi_topic_main_tail": ("目治手营",),
    "shanhaijing_topic_main_tail": ("精品好料",),
    "fengchi_topic_main_tail": ("风驰电掣",),
    "jianren_topic_main_tail": ("坚韧不拔",),
    "lulu_topic_main_tail": ("碌碌庸才",),
    "chuimao_topic_tail": ("吹毛求疵",),
    "chuimao_primary_topic_tail": ("吹毛求疵",),
    "bujuxiaojie_topic_tail": ("不拘小节",),
    "xingshuchangwan_topic_tail": ("行舒唱晚",),
    "wanbuwunai_topic_tail": ("万般无奈",),
    "laoqirenxiaowei_topic_tail": ("老奇人",),
    "zhongliwanzhao_topic_tail": ("钟离晚照",),
    "gaofengliangjie_topic_tail": ("高风亮节",),
    "gulichunyi_topic_tail": ("故里春意",),
    "daidai_kill_tail": ("呆呆杀码-综合绝杀",),
    "chuanjue_xizi_topic_tail": ("传爵袭紫", "绝杀一尾", "让您暴富"),
    "bamian_shifeng_topic_tail": ("八面驶风", "稳杀一尾"),
    "huayan_shijie_topic_tail": ("华严世界", "绝杀1尾"),
}


def _dynamic_class_tokens(node: _DynamicHtmlNode) -> set[str]:
    return {token for token in node.attrs.get("class", "").split() if token}


def _topic_main_header_period(
    node: _DynamicHtmlNode,
    markers: tuple[str, ...],
) -> int | None:
    """Read the period from the header sibling that owns the content node."""
    current = node
    while current.parent is not None:
        parent = current.parent
        try:
            child_index = parent.children.index(current)
        except ValueError:
            child_index = len(parent.children)

        preceding = parent.children[:child_index]
        header_nodes = [
            sibling
            for sibling in preceding
            if _dynamic_class_tokens(sibling)
            & {"forum-head", "title", "topic-title", "top-left", "head"}
        ]
        for sibling in reversed(header_nodes):
            text = _dynamic_node_text(sibling)
            matches = list(PERIOD_RE.finditer(text))
            if matches:
                return int(matches[-1].group(1))
        current = parent

    return None


_TOPIC_PUBLISHED_BODY_CLASSES = frozenset({"topic-content", "d-content", "content"})
_TOPIC_PUBLISHED_TAIL_PATTERN = re.compile(
    r"(?:绝\s*杀\s*(?:1|一)\s*尾|杀\s*(?:1|一)\s*尾)"
    r"[^0-9\r\n]{0,30}(?:杀\s*)?(\d{1,3})\s*尾?"
)
_TOPIC_PUBLISHED_PRECISION_TAIL_PATTERN = re.compile(
    r"(?:精准\s*杀\s*(?:1|一)?\s*尾|绝\s*杀\s*(?:1|一)\s*尾|杀\s*(?:1|一)\s*尾)"
    r"[^0-9\r\n]{0,30}(?:杀\s*)?(\d{1,3})\s*尾?"
)
_TOPIC_UNPUBLISHED_DRAW_PATTERN = re.compile(
    r"(?:开|中\s*开)\s*[:：]?\s*(?:[?？]\s*0{2,}|0{2,})(?:准|错)?"
)

_LAINAN_YIXIN_TAIL_PATTERN = re.compile(
    r"绝\s*杀\s*(?:1|一)\s*尾"
    r"[^0-9\r\n]{0,30}[【\[\(（]\s*(\d{1,3})\s*[】\]\)）]"
)
_LAINAN_YIXIN_UNPUBLISHED_DRAW_PATTERN = re.compile(
    r"(?:开|中\s*开)\s*[:：]?\s*(?:[?？]\s*0{2,}|0{4,})(?:准|错)?"
)


def _topic_body_header_period(node: _DynamicHtmlNode) -> int | None:
    """Find the period in the title/header that owns one body container."""
    period = _topic_main_header_period(node, ())
    if period is not None:
        return period

    current = node.parent
    while current is not None:
        classes = _dynamic_class_tokens(current)
        if classes & {"big-con", "boxn", "big-tit", "big-title"}:
            match = PERIOD_RE.search(_dynamic_node_text_in_order(current))
            if match:
                return int(match.group(1))
        current = current.parent
    return None


def extract_topic_published_body_records(
    document: str,
    site_name: str,
    chunk_keywords: tuple[str, ...],
    exclude_keywords: tuple[str, ...],
    max_chunk_span: int,
    require_draw_signal: bool,
    target_period: int | None,
    pick: str,
    allow_same_period_records: bool = False,
    required_author_anchor: str = "",
    preserve_body_header: bool = False,
) -> list[Record]:
    """Parse URL-specific topic body rows and reject unpublished duplicates.

    These pages contain a real history beside a copied current row whose draw
    field is 0000 or ?00. Only direct rows inside the proven body container are
    considered; a published row and an unpublished copy never become a silent
    conflict.
    """
    if "<" not in document or ">" not in document:
        return []

    tail_pattern = (
        _TOPIC_PUBLISHED_PRECISION_TAIL_PATTERN
        if normalize_text(site_name) == "束广就狭"
        else _TOPIC_PUBLISHED_TAIL_PATTERN
    )

    parser = _DynamicHtmlParser()
    try:
        parser.feed(document)
        parser.close()
    except Exception:
        return []

    records: list[Record] = []
    stack = [parser.root]
    while stack:
        node = stack.pop()
        if node.tag in {"script", "style", "noscript"}:
            continue
        classes = _dynamic_class_tokens(node)
        if classes & _TOPIC_PUBLISHED_BODY_CLASSES:
            if required_author_anchor and not _topic_body_has_author_anchor(
                node, required_author_anchor
            ):
                stack.extend(reversed(node.children))
                continue
            rows: list[tuple[int, str]] = []
            for child in node.children:
                if child.tag in {"script", "style", "noscript"}:
                    continue
                row_text = normalize_text(_dynamic_node_text_in_order(child))
                period_match = PERIOD_RE.match(row_text)
                if period_match is None or tail_pattern.search(row_text) is None:
                    continue
                rows.append((int(period_match.group(1)), row_text))

            if rows:
                header_period = _topic_body_header_period(node)
                if header_period is None:
                    stack.extend(reversed(node.children))
                    continue
                if (
                    not preserve_body_header
                    and target_period is not None
                    and header_period != target_period
                ):
                    stack.extend(reversed(node.children))
                    continue
                body_text = normalize_text(_dynamic_node_text_in_order(node))
                if chunk_keywords and not any(keyword and keyword in body_text for keyword in chunk_keywords):
                    stack.extend(reversed(node.children))
                    continue

                for period, row_text in rows:
                    if exclude_keywords and not contains_none(row_text, exclude_keywords):
                        continue
                    if require_draw_signal and not _has_draw_signal(row_text):
                        continue
                    placeholder_error = ""
                    if _TOPIC_UNPUBLISHED_DRAW_PATTERN.search(row_text):
                        if target_period is None:
                            continue
                        placeholder_error = "开0000占位记录"
                    match = tail_pattern.search(row_text)
                    if match is None:
                        continue
                    records.append(
                        Record(
                            tail=int(match.group(1)[-1]),
                            period=period,
                            site_name=site_name,
                            draw_text=extract_draw_text(row_text),
                            source_snippet=_compact_snippet(
                                f"{site_name} 主体{header_period}期 {row_text}",
                                max(80, max_chunk_span),
                            ),
                            validation_error=placeholder_error,
                        )
                    )
        stack.extend(reversed(node.children))

    grouped: dict[int, list[Record]] = {}
    for record in records:
        grouped.setdefault(record.period, []).append(record)
    # A targeted run must expose every candidate to the central validator so
    # it can select the absolute top/bottom boundary.  Conflict arbitration is
    # intentionally kept there; this parser only decides which rows belong to
    # the proven body block.  Historical collection keeps its existing
    # fail-closed conflict check before selecting one row per period.
    if target_period is None and not allow_same_period_records:
        for period, period_records in grouped.items():
            values = {record.value() for record in period_records}
            if len(values) > 1:
                raise LookupError(
                    f"{period}期存在多个候选且数据冲突: {'、'.join(sorted(values))}"
                )

    if target_period is not None:
        return records
    ordered_periods = sorted(grouped, reverse=not is_bottom_pick(pick))
    if allow_same_period_records:
        return [record for period in ordered_periods for record in grouped[period]]
    return [grouped[period][0] for period in ordered_periods]


def _topic_body_has_author_anchor(
    node: _DynamicHtmlNode, expected_author: str
) -> bool:
    """Require the author and target body to share the same topic container."""
    normalized_author = normalize_text(expected_author)
    if not normalized_author:
        return False

    current = node.parent
    while current is not None:
        classes = _dynamic_class_tokens(current)
        if "container" in classes:
            context_text = normalize_text(_dynamic_node_text_in_order(current))
            return re.search(
                rf"(?:^|\s){re.escape(normalized_author)}\s*发表于(?:\s|$)",
                context_text,
            ) is not None
        if classes & {"detail_info_forum2_item", "topic-item", "forum-item"}:
            return False
        current = current.parent
    return False


def _select_contiguous_record_segment(
    records: list[Record], pick: str
) -> list[Record]:
    """Keep one ordered annual cycle before applying the absolute direction."""
    if not records:
        return records

    segments: list[list[Record]] = []
    current = [records[0]]
    direction = 0
    for record in records[1:]:
        delta = record.period - current[-1].period
        if delta in {-1, 1} and (direction == 0 or direction == delta):
            current.append(record)
            direction = delta
            continue
        segments.append(current)
        current = [record]
        direction = 0
    segments.append(current)
    return segments[-1] if is_bottom_pick(pick) else segments[0]


def extract_qingqingdandan_topic_records(
    document: str,
    site_name: str,
    chunk_keywords: tuple[str, ...],
    exclude_keywords: tuple[str, ...],
    max_chunk_span: int,
    require_draw_signal: bool,
    target_period: int | None,
    pick: str,
    allow_same_period_records: bool = False,
) -> list[Record]:
    """Parse topic 324703 from its author-owned current annual cycle only."""
    expected_author = "清清淡淡"
    if normalize_text(site_name) != expected_author:
        return []

    records = extract_topic_published_body_records(
        document,
        site_name,
        chunk_keywords,
        exclude_keywords,
        max_chunk_span,
        require_draw_signal,
        target_period if target_period is not None else 0,
        pick,
        allow_same_period_records,
        required_author_anchor=expected_author,
        preserve_body_header=True,
    )
    return _select_contiguous_record_segment(records, pick)


def extract_lainan_yixin_bottom_records(
    document: str,
    site_name: str,
    exclude_keywords: tuple[str, ...],
    max_chunk_span: int,
    require_draw_signal: bool,
    require_site_keyword: bool,
    anchor_span: int,
    target_period: int | None,
    pick: str,
) -> list[Record]:
    """Parse 来年一心's real bottom history block.

    The source emits independent history blocks as decoded documents.  Within
    one document it can also concatenate two contiguous histories.  Keep the
    DOM/direct-row boundary, select the direction segment first, and only then
    validate the requested period.  This site uses ``开00准`` as a valid draw
    field; only ``开0000`` and ``开?00``-style placeholders are rejected.
    """
    full_text = normalize_text(re.sub(r"<[^>]+>", " ", document))
    if require_site_keyword:
        normalized_site = normalize_text(site_name)
        if not normalized_site or not re.search(
            rf"{re.escape(normalized_site)}.{{0,{max(0, anchor_span)}}}"
            r"(?:绝\s*杀\s*(?:1|一)\s*尾)",
            full_text,
        ):
            return []

    rows: list[tuple[int, str]] = []
    if "<" in document and ">" in document:
        parser = _DynamicHtmlParser()
        try:
            parser.feed(document)
            parser.close()
        except Exception:
            return []

        row_groups: list[list[tuple[int, str]]] = []
        stack = [parser.root]
        while stack:
            node = stack.pop()
            if _dynamic_class_tokens(node) & {"content", "d-content", "topic-content"}:
                node_rows: list[tuple[int, str]] = []
                for child in node.children:
                    if child.tag in {"script", "style", "noscript"}:
                        continue
                    row_text = normalize_text(_dynamic_node_text_in_order(child))
                    period_match = PERIOD_RE.match(row_text)
                    if period_match is None or _LAINAN_YIXIN_TAIL_PATTERN.search(row_text) is None:
                        continue
                    node_rows.append((int(period_match.group(1)), row_text))
                if node_rows:
                    row_groups.append(node_rows)
            stack.extend(reversed(node.children))

        if row_groups:
            rows = max(row_groups, key=len)
        else:
            rows = [
                (int(period_match.group(1)), chunk.strip())
                for chunk in PERIOD_CHUNK_RE.split(full_text)
                if (period_match := PERIOD_RE.match(chunk.strip()))
                and _LAINAN_YIXIN_TAIL_PATTERN.search(chunk) is not None
            ]
    else:
        rows = [
            (int(period_match.group(1)), chunk.strip())
            for chunk in PERIOD_CHUNK_RE.split(full_text)
            if (period_match := PERIOD_RE.match(chunk.strip()))
            and _LAINAN_YIXIN_TAIL_PATTERN.search(chunk) is not None
        ]

    if not rows:
        return []

    segments: list[list[tuple[int, str]]] = []
    current = [rows[0]]
    direction = 0
    for row in rows[1:]:
        delta = row[0] - current[-1][0]
        if delta in {-1, 1} and (direction == 0 or direction == delta):
            current.append(row)
            direction = delta
            continue
        segments.append(current)
        current = [row]
        direction = 0
    segments.append(current)
    selected_rows = (
        rows
        if target_period is not None
        else segments[-1] if is_bottom_pick(pick) else segments[0]
    )

    records: list[Record] = []
    for period, row_text in selected_rows:
        if exclude_keywords and not contains_none(row_text, exclude_keywords):
            continue
        if require_draw_signal and not _has_draw_signal(row_text):
            continue
        placeholder_error = ""
        if _LAINAN_YIXIN_UNPUBLISHED_DRAW_PATTERN.search(row_text):
            if target_period is None:
                continue
            placeholder_error = "开0000占位记录"
        match = _LAINAN_YIXIN_TAIL_PATTERN.search(row_text)
        if match is None:
            continue
        records.append(
            Record(
                tail=int(match.group(1)[-1]),
                period=period,
                site_name=site_name,
                draw_text=extract_draw_text(row_text),
                source_snippet=_compact_snippet(
                    f"{site_name} 底部历史区块 {period}期 {row_text}",
                    max(80, max_chunk_span),
                ),
                validation_error=placeholder_error,
            )
        )
    return records


def _topic_main_primary_rows(
    node: _DynamicHtmlNode,
    parser_name: str,
    title_period: int | None,
    pick: str,
    preserve_all: bool = False,
    pattern: re.Pattern[str] | None = None,
) -> list[tuple[int, str]]:
    """Keep the structurally proven primary history in the topic body.

    Several forum templates append a second, repeated history directly after the
    real post body. It has no separate container, so flattening the whole node
    creates a same-period conflict. A repeated period is ignored only when the
    DOM also proves a separated second history; otherwise it remains a conflict.
    """
    pattern = pattern or _TOPIC_MAIN_PARSER_PATTERNS.get(parser_name)
    if pattern is None:
        return []

    rows: list[tuple[int, str]] = []
    for child in node.children:
        if child.tag in {"script", "style", "noscript"}:
            continue
        row_text = normalize_text(
            _dynamic_node_text_in_order(child)
            if parser_name in TOPIC_MAIN_CONTIGUOUS_PARSERS
            else _dynamic_node_text(child)
        )
        period_match = PERIOD_RE.match(row_text)
        if period_match is None or pattern.search(row_text) is None:
            continue
        period = int(period_match.group(1))
        rows.append((period, row_text))
    if preserve_all:
        return rows
    if parser_name in TOPIC_MAIN_CONTIGUOUS_PARSERS | {"chuimao_topic_tail"}:
        return _topic_main_select_contiguous_segment(rows, pick)
    return _topic_main_select_primary_rows(rows, title_period, pick)


def _topic_main_select_contiguous_segment(
    rows: list[tuple[int, str]],
    pick: str,
) -> list[tuple[int, str]]:
    """Select one URL-specific contiguous history from repeated topic rows."""
    if not rows:
        return rows
    segments: list[list[tuple[int, str]]] = []
    current = [rows[0]]
    direction = 0
    for row in rows[1:]:
        delta = row[0] - current[-1][0]
        if delta in {-1, 1} and (direction == 0 or direction == delta):
            current.append(row)
            direction = delta
            continue
        segments.append(current)
        current = [row]
        direction = 0
    segments.append(current)
    return segments[-1] if is_bottom_pick(pick) else segments[0]


def _topic_main_select_primary_rows(
    rows: list[tuple[int, str]],
    title_period: int | None,
    pick: str,
) -> list[tuple[int, str]]:
    if title_period is None:
        return rows

    title_indexes = [
        index for index, (period, _) in enumerate(rows)
        if period == title_period
    ]
    if len(title_indexes) < 2:
        return rows

    first, second = title_indexes[0], title_indexes[1]
    between = rows[first + 1 : second]
    separated_second_history = len(between) >= 3 and (
        (
            is_bottom_pick(pick)
            and any(period > title_period for period, _ in between)
        )
        or (
            not is_bottom_pick(pick)
            and any(period < title_period for period, _ in between)
        )
    )
    if not is_bottom_pick(pick) and len(between) >= 2:
        has_lower_period = any(period < title_period for period, _ in between)
        has_reset_period = any(period > title_period for period, _ in between)
        separated_second_history = separated_second_history or (
            has_lower_period and has_reset_period
        )
    if not separated_second_history:
        return rows
    return rows[: first + 1] if is_bottom_pick(pick) else rows[:second]


def _topic_main_html_blocks(
    document: str,
    parser_name: str,
    pick: str = "top",
    site_name: str = "",
    preserve_all: bool = False,
    pattern: re.Pattern[str] | None = None,
) -> list[tuple[int, str]]:
    if "<" not in document or ">" not in document:
        return []
    parser = _DynamicHtmlParser()
    try:
        parser.feed(document)
        parser.close()
    except Exception:
        return []

    markers = _TOPIC_MAIN_PARSER_MARKERS.get(parser_name, ())
    if parser_name == "forum_main_kill_tail" and site_name:
        markers = (normalize_text(site_name),)
    blocks: list[tuple[int, str]] = []
    stack = [parser.root]
    while stack:
        node = stack.pop()
        classes = _dynamic_class_tokens(node)
        is_topic_content = "topic-content" in classes
        is_buttom_content = (
            "content" in classes
            and node.parent is not None
            and "buttom" in _dynamic_class_tokens(node.parent)
        )
        if is_topic_content or is_buttom_content:
            if parser_name in TOPIC_MAIN_REQUIRE_MARKER_CONTEXT_PARSERS:
                context = node
                marker_context_found = False
                while context is not None:
                    context_text = _dynamic_node_text(context)
                    if markers and all(marker in context_text for marker in markers):
                        marker_context_found = True
                        break
                    context = context.parent
                if not marker_context_found:
                    stack.extend(reversed(node.children))
                    continue
            title_period = _topic_main_header_period(node, markers)
            if title_period is None:
                context = node.parent
                while context is not None and title_period is None:
                    candidate_text = _dynamic_node_text(context)
                    if candidate_text and (not markers or any(marker in candidate_text for marker in markers)):
                        match = PERIOD_RE.search(candidate_text)
                        if match:
                            title_period = int(match.group(1))
                    context = context.parent

            primary_rows = _topic_main_primary_rows(
                node, parser_name, title_period, pick, preserve_all, pattern
            )
            if title_period is not None and primary_rows:
                body_text = " ".join(row_text for _, row_text in primary_rows)
                candidate = (title_period, body_text)
                if candidate not in blocks:
                    blocks.append(candidate)
        stack.extend(reversed(node.children))
    return blocks


def _extract_topic_main_dedicated_records(
    document: str,
    site_name: str,
    parser_name: str,
    exclude_keywords: tuple[str, ...],
    max_chunk_span: int,
    require_draw_signal: bool,
    target_period: int | None,
    pick: str,
    allow_same_period_records: bool = False,
) -> list[Record]:
    pattern = _TOPIC_MAIN_PARSER_PATTERNS.get(parser_name)
    if parser_name == "forum_main_kill_tail" and normalize_text(site_name) in {
        "渊停山立",
        "陟岵瞻望",
    }:
        pattern = _FORUM_YUANTING_BARE_KILL_TAIL_PATTERN
    if pattern is None:
        return []
    records: list[Record] = []
    blocks = _topic_main_html_blocks(
        document,
        parser_name,
        pick,
        site_name,
        preserve_all=target_period is not None,
        pattern=pattern,
    )
    if not blocks and "<" not in document:
        plain_text = normalize_text(document)
        markers = _TOPIC_MAIN_PARSER_MARKERS.get(parser_name, ())
        if parser_name == "forum_main_kill_tail" and site_name:
            markers = (normalize_text(site_name),)
        if not markers or any(marker in plain_text for marker in markers):
            line_rows: list[tuple[int, str]] = []
            for raw_line in document.splitlines():
                line = normalize_text(raw_line)
                period_match = PERIOD_RE.match(line)
                if period_match is None or pattern.search(line) is None:
                    continue
                period = int(period_match.group(1))
                line_rows.append((period, line))
            title_match = PERIOD_RE.search(plain_text)
            if line_rows and title_match:
                title_period = int(title_match.group(1))
                if parser_name in {
                    "forum_main_kill_tail",
                    "saodi_topic_main_tail",
                    "dongxin_topic_main_tail",
                    "yanhuo_topic_main_tail",
                }:
                    # These repair parsers require a DOM boundary before they
                    # separate repeated histories; plain text must fail closed.
                    blocks = [(title_period, " ".join(row_text for _, row_text in line_rows))]
                else:
                    primary_rows = (
                        line_rows
                        if target_period is not None
                        else _topic_main_select_contiguous_segment(line_rows, pick)
                        if parser_name in TOPIC_MAIN_CONTIGUOUS_PARSERS
                        else _topic_main_select_primary_rows(line_rows, title_period, pick)
                    )
                    blocks = [(title_period, " ".join(row_text for _, row_text in primary_rows))]
            elif title_match:
                compact_rows: list[tuple[int, str]] = []
                for chunk in PERIOD_CHUNK_RE.split(plain_text):
                    chunk = chunk.strip()
                    period_match = PERIOD_RE.match(chunk)
                    if period_match is None or pattern.search(chunk) is None:
                        continue
                    compact_rows.append((int(period_match.group(1)), chunk))
                title_period = int(title_match.group(1))
                if compact_rows:
                    if parser_name in {
                        "forum_main_kill_tail",
                        "saodi_topic_main_tail",
                        "dongxin_topic_main_tail",
                        "yanhuo_topic_main_tail",
                    }:
                        blocks = [(title_period, " ".join(row_text for _, row_text in compact_rows))]
                    else:
                        primary_rows = (
                            compact_rows
                            if target_period is not None
                            else _topic_main_select_contiguous_segment(compact_rows, pick)
                            if parser_name in TOPIC_MAIN_CONTIGUOUS_PARSERS
                            else _topic_main_select_primary_rows(compact_rows, title_period, pick)
                        )
                        blocks = [(title_period, " ".join(row_text for _, row_text in primary_rows))]
                elif "\n" not in document and "\r" not in document:
                    # Keep compact fixtures without a recognizable row strict.
                    blocks = [(title_period, plain_text)]

    for title_period, body_text in blocks:
        if (
            target_period is not None
            and title_period != target_period
            and parser_name not in TOPIC_MAIN_TARGET_TITLE_TOLERANT_PARSERS
        ):
            continue
        chunks = [chunk.strip() for chunk in PERIOD_CHUNK_RE.split(normalize_text(body_text)) if chunk.strip()]
        for chunk in chunks:
            period_match = PERIOD_RE.match(chunk)
            if not period_match:
                continue
            period = int(period_match.group(1))
            if period > title_period:
                continue
            if exclude_keywords and not contains_none(chunk, exclude_keywords):
                continue
            placeholder_error = ""
            if parser_name in {
                "xiaoge_topic_main_tail",
                "chuimao_topic_tail",
                "chuimao_primary_topic_tail",
            } and re.search(r"开\s*[:：]?\s*(?:\?0+|0{2,4})(?!\d)", chunk):
                if target_period is None:
                    continue
                placeholder_error = "开0000占位记录"
            if require_draw_signal and not _has_draw_signal(chunk):
                continue
            match = pattern.search(chunk)
            if not match:
                continue
            records.append(
                Record(
                    tail=int(match.group(1)[-1]),
                    period=period,
                    site_name=site_name,
                    draw_text=extract_draw_text(chunk),
                    source_snippet=_compact_snippet(
                        f"{site_name} 主帖标题{title_period}期 {chunk}", max(80, max_chunk_span)
                    ),
                    validation_error=placeholder_error,
                )
            )
    return records


def extract_topic_main_records(
    document: str,
    site_name: str,
    parser_name: str,
    target_period: int | None,
    pick: str,
) -> list[Record]:
    return _extract_topic_main_dedicated_records(
        document,
        site_name,
        parser_name,
        DEFAULT_EXCLUDE_KEYWORDS,
        240,
        True,
        target_period,
        pick,
    )
