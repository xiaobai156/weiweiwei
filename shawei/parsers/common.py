from __future__ import annotations

import re
import sys
import threading
from html.parser import HTMLParser

from shawei.config.constants import (
    CHINESE_DIGITS, CURRENT_PERIOD_MARKERS, DEFAULT_EXCLUDE_KEYWORDS, DRAW_RE,
    PERIOD_CHUNK_RE, PERIOD_RE, PRIOR_PERIOD_LOOKBEHIND, PRIOR_PERIOD_MARKERS,
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


def exact_tail_value(raw_value: str) -> int | None:
    """Return one exact single-tail digit.

    Several verified pages display the predicted tail as the same digit
    repeated two or more times (for example ``(777)`` or ``〖222尾〗``).
    Mixed multi-digit tokens such as ``23`` stay rejected.
    """

    if re.fullmatch(r"\d", raw_value):
        return int(raw_value)
    if len(raw_value) > 1 and len(set(raw_value)) == 1:
        return int(raw_value[0])
    return None


# 匹配点所在小句的边界：句读符号和真正的开奖字段。裸「开」不能当边界，
# 否则「上期公开 杀一尾5」里的「公开」会把上期词截掉，又变回借值。
_SENTENCE_BOUNDARIES = ("。", "，", ",", "；", ";", "\n", "|")
_DRAW_FIELD_BOUNDARY_RE = re.compile(
    r"开(?:奖结果|奖号码|奖)?\s*[:：?？]?\s*(?=(?:[鼠牛虎兔龙蛇马羊猴鸡狗猪])?\d|\?)"
)
# 「上期红单/上期命中」描述的是上期开奖的战绩，不是上期的预测字段，
# 后面的尾值仍属本行。这是一组封闭结果词；不能把「连中/全中/连红/战绩/
# 推荐」这类预测记录词也放进来，否则「上期战绩 杀一尾5」就会借上期值。
_PRIOR_RESULT_WORDS = (
    "红单",
    "黑单",
    "命中",
    "中出",
    "中奖",
    "中特",
)

# 期面守卫拒绝取值的计数：真实验证时要能分清「页面真没数据」和
# 「被上期/本期判定挡回去」，否则误伤面无法量化。
_REJECTION_LOCK = threading.Lock()
_REJECTION_COUNTS: dict[str, int] = {}


def reset_tail_rejections() -> None:
    with _REJECTION_LOCK:
        _REJECTION_COUNTS.clear()


def tail_rejection_counts() -> dict[str, int]:
    with _REJECTION_LOCK:
        return dict(_REJECTION_COUNTS)


def _count_rejection(reason: str) -> None:
    with _REJECTION_LOCK:
        _REJECTION_COUNTS[reason] = _REJECTION_COUNTS.get(reason, 0) + 1


def _prior_directive_start(prediction: str, start: int) -> int:
    """返回最近一个**直接管辖**该匹配点的上期词位置，没有则返回 -1。

    只认紧贴取值字段的时间标签（「上期杀一尾5」「往期绝杀一尾3」）。
    时间词和尾值之间如果先出现战绩/状态词（红单、命中、最高…），说明它
    描述的是别的内容，不能用来剔除这个值——否则会把本期的首值删掉、
    换成后面另一个栏目的值，比原来的借值更危险。
    """

    prefix_start = max(0, start - PRIOR_PERIOD_LOOKBEHIND)
    prefix = prediction[prefix_start:start]
    boundary_at = max(
        (prefix.rfind(boundary) for boundary in _SENTENCE_BOUNDARIES),
        default=-1,
    )
    draw = None
    for match in _DRAW_FIELD_BOUNDARY_RE.finditer(prefix):
        draw = match
    if draw is not None and draw.end() > boundary_at:
        boundary_at = draw.end() - 1
    if boundary_at >= 0:
        prefix = prefix[boundary_at + 1 :]
    prefix_base = start - len(prefix)

    prior_at = max(
        (prefix.rfind(marker) for marker in PRIOR_PERIOD_MARKERS if marker in prefix),
        default=-1,
    )
    if prior_at < 0:
        return -1
    current_at = max(
        (prefix.rfind(marker) for marker in CURRENT_PERIOD_MARKERS if marker in prefix),
        default=-1,
    )
    if current_at > prior_at:
        return -1
    matched_marker = max(
        (marker for marker in PRIOR_PERIOD_MARKERS if prefix.rfind(marker) == prior_at),
        key=len,
    )
    between = prefix[prior_at + len(matched_marker) :]
    # 三种情形：①「上期杀一尾5」——上期词直接管辖取值字段，剔除；
    # ②「上期红单 杀一尾7」——中间只有开奖战绩词，是在说上期结果，不剔除；
    # ③「上期推荐命中 杀一尾5」——还夹着别的说明，仍是上期预测字段，剔除。
    residue = between
    for word in _PRIOR_RESULT_WORDS:
        residue = residue.replace(word, "")
    if re.sub(r"[\s\W_]+", "", residue) == "" and any(
        word in between for word in _PRIOR_RESULT_WORDS
    ):
        return -1
    return prefix_base + prior_at


def _is_prior_period_position(prediction: str, start: int) -> bool:
    """判断匹配点是否被紧邻的上期词直接管辖。"""

    return _prior_directive_start(prediction, start) >= 0


def _extract_tail_value(chunk: str) -> int | None:
    """按「出现位置」取本期尾值，而不是按模式优先级。

    原实现遍历 TAIL_PATTERNS，遇到第一个能匹配的模式就返回——于是
    「本期杀:7尾: 0000 准 上期绝杀一尾5」会先命中「绝杀一尾」这个强模式，
    把上期的 5 当本期值（块内跨期借值，且不产生同期冲突，校验层看不见）。

    现在收集所有模式的全部匹配，按出现位置从前往后取第一个合法值，
    并且只剔除「被上期词直接管着」的值：既挡住借值，也不会把本行首值
    误删后改用后面栏目里的另一个值。
    """

    prediction = normalize_text(_prediction_text(chunk))
    if "尾" not in prediction:
        return None

    candidates: list[tuple[int, int, str, re.Match[str]]] = []
    prior_positions: list[int] = []
    for order, pattern in enumerate(TAIL_PATTERNS):
        for match in pattern.finditer(prediction):
            if _is_prior_period_position(prediction, match.start()):
                prior_positions.append(match.start())
                continue
            candidates.append((match.start(), order, pattern.pattern, match))
    candidates.sort(key=lambda item: (item[0], item[1]))

    first_prior = min(prior_positions) if prior_positions else None
    for start, _order, _pattern, match in candidates:
        raw_value = match.group(1)
        value = exact_tail_value(raw_value)
        if value is None:
            continue
        matched_text = normalize_text(match.group(0)).replace(" ", "")
        if raw_value == "1" and re.fullmatch(
            r"(?:绝杀|精准杀|稳杀|狠杀|主杀|课杀|杀掉|禁|杀)1尾", matched_text
        ):
            continue
        # A single-tail parser must not silently select one value from a
        # multi-tail field such as 2、3尾 or 1尾 8尾.
        suffix = prediction[match.end() : match.end() + 16]
        if re.match(r"\s*(?:尾\s*)?(?:[、,，.．+＋/]\s*)?\d\s*尾", suffix):
            continue
        if first_prior is not None and first_prior < start:
            # 前面已经有被判成上期的值，而当前候选没有被本期词直接管辖：
            # 这多半是后面另一个栏目的值。宁可不给值，也不能把上期值删掉
            # 之后换用它的邻居——那和借值一样是错值，而且更隐蔽。
            prefix = prediction[max(0, start - PRIOR_PERIOD_LOOKBEHIND) : start]
            if not any(marker in prefix for marker in CURRENT_PERIOD_MARKERS):
                _count_rejection("上期值在前且无本期词")
                return None
        return value
    if prior_positions:
        _count_rejection("窗口内只有上期值")
    return None


def _period_window(chunk: str, max_span: int = 240) -> str:
    """按跨度截取本期窗口，且绝不把数字/括号切断成另一个合法值。

    硬切会把非法值「修」成合法值：例如 `[12]` 若切点落在 `[1` 与 `2` 之间，
    窗口里就只剩 `[1]`，而 1 是合法尾数，会静默通过校验。
    """
    full = normalize_text(chunk)
    text = full[: max(80, max_span)]
    if len(text) >= len(full):
        return text
    # 截断点落在数字中间，或任一种括号未闭合时，回退到最近分隔处。
    # 必须同时检查 [] 与 ()：normalize 会把全角括号转成半角 ()。
    unbalanced = any(
        text.count(open_ch) > text.count(close_ch)
        for open_ch, close_ch in (("[", "]"), ("(", ")"), ("【", "】"))
    )
    if re.search(r"\d$", text) or unbalanced:
        cut = max(text.rfind(" "), text.rfind("\t"), text.rfind("\n"))
        if cut > 0:
            text = text[:cut]
        else:
            # 没有分隔处可退时，宁可丢弃末尾不完整的数字/括号片段，
            # 也不能让它变成另一个合法值。
            text = re.sub(r"[\d\[\]()【】]+\s*$", "", text)
    return text


# 开奖字段：允许只写「准/错」不带号码（真实站点存在 `开准` 写法），
# 也允许带号码/占位。`开奖结果 12 准` 同样属于开奖字段。
# 另有站点把开奖写成「尾: 0000 准」「尾: 马13 准」，即尾值字段后直接跟
# 开奖号与准/错，不带「开」字（如尉迟日轻 `298期杀:7尾: 0000 准`）。
_DRAW_FIELD_RE = re.compile(
    r"开(?:奖结果|奖号码|奖)?[ \t:：]*"
    r"(?:"
    r"(?:[鼠牛虎兔龙蛇马羊猴鸡狗猪])?\d{1,4}"
    r"|[?？]{1,2}\d{0,2}"
    r"|准|错"
    r")"
    r"|(?:[鼠牛虎兔龙蛇马羊猴鸡狗猪]\s*\d{2}\s*(?:准|错))"
    r"|(?:[【\[]?\s*\d+\s*[】\]]?\s*[尾头肖]\s*[：:]\s*"
    r"(?:[鼠牛虎兔龙蛇马羊猴鸡狗猪]\s*\d{2}|[?？]{1,2}\d{0,2}|\d{1,4})\s*(?:准|错))"
)

# 噪声词：整词命中时先把词本身从待判文本里抹掉，避免 `公开12期` 里的
# 「开」被当成开奖字段（它后面恰好跟着 12，单靠正则无法区分）。
_DRAW_NOISE_WORDS = (
    "公开", "开户", "开始", "开展", "开通", "开盘", "开奖栏目",
    "开奖时间", "开奖直播", "开奖记录", "开奖走势", "开奖网", "开奖站",
)

# 站点把网址写成「开奖:87127.com」时，「开奖:数字」看起来像开奖号，
# 但后面紧跟域名后缀，属噪声。
_DRAW_URL_RE = re.compile(r"开奖\s*[:：]?\s*\d+\s*\.\s*[A-Za-z]{2,}")


def _has_draw_signal(chunk: str) -> bool:
    """判断本块是否含真正的开奖字段，避免「公开/准备/开奖栏目」误判。

    仅出现「开」「准」「错」任一单字不足以证明这是开奖数据行，广告位与
    导航文字同样会命中，从而把相邻期或栏目里的数字当本期值。

    但真实站点确实存在 `开准`（只写准/错、不带号码）的写法，因此不能要求
    必须有号码。做法：先抹掉噪声词与网址，再判断剩余文本里是否有开奖字段。
    """
    normalized = normalize_text(chunk)
    cleaned = _DRAW_URL_RE.sub("　", normalized)
    for word in _DRAW_NOISE_WORDS:
        cleaned = cleaned.replace(word, "　")
    return bool(_DRAW_FIELD_RE.search(cleaned))


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
    if (
        _extract_tail_value(window) is None
        and _extract_wave_value(window) == ""
    ):
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

    section_full = text.split(section_start, 1)[1][: max(200, max_section_span)]
    # 站名和杀尾关键词必须在**切之前**的整段上判定：切过的 section 只是它的
    # 子集，先切后判会把「停止词接错」误报成「站名/关键词缺失」，也会让下面
    # 的回退告警失去意义。
    # The section marker itself can be the site identity (for example
    # ``飞龙在天 『绝杀一尾』``).  It is consumed when slicing the section, so
    # accept that proven marker instead of requiring the site name to repeat in
    # the rows.
    if require_site_keyword and not (
        _site_keyword_present(section_full, site_name)
        or _site_keyword_present(section_start, site_name)
    ):
        return []
    signal_keywords = _tail_signal_keywords(chunk_keywords, site_name)
    if signal_keywords and not matches_tail_signal(section_full, signal_keywords):
        return []
    stop_positions = [
        section_full.find(keyword)
        for keyword in section_stop_keywords
        if keyword and section_full.find(keyword) >= 0
    ]

    def _section_records(section: str) -> list[Record]:
        records: list[Record] = []
        chunks = [
            chunk.strip() for chunk in PERIOD_CHUNK_RE.split(section) if chunk.strip()
        ]
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

    records = _section_records(
        section_full[: min(stop_positions)] if stop_positions else section_full
    )
    if not records and stop_positions:
        # 停止词切完没有记录，说明真实排版里停止词排在数据行之前。退回不切
        # 窗口的行为，避免把「停止词接错」变成每天静默失败；同时报到 stderr，
        # 让这条规则能被发现并修正，而不是永远静默失效。
        records = _section_records(section_full)
        if records:
            print(
                f"{site_name}停止词切分后无记录，已回退不切窗口: "
                f"{section_stop_keywords}",
                file=sys.stderr,
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
