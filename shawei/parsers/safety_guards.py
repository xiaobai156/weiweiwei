from __future__ import annotations

import re

from shawei.config.constants import PERIOD_CHUNK_RE, PERIOD_RE, TAIL_PATTERNS
from shawei.domain.models import Record
from shawei.domain.text import normalize_text


_GENERIC_STRICT_SOURCES = frozenset({"section", "compact", "lead_compact"})
_SINGLE_TAIL_SOURCES = frozenset(
    {"section", "compact", "lead_compact", "dedicated", "user_feed"}
)

_ACTION = (
    r"(?:绝\s*杀|精准\s*杀|精\s*杀|稳\s*杀|狠\s*杀|主\s*杀|课\s*杀|"
    r"杀\s*掉|禁|杀)"
)
_DRAW_BOUNDARY_RE = re.compile(
    r"开\s*[:：?？]?\s*(?=(?:[鼠牛虎兔龙蛇马羊猴鸡狗猪]\s*)?\d|\?)"
)
_VALUE_TOKEN_RE = re.compile(r"(?<!\d)(\d{1,3})(?!\d)")
_MULTI_TAIL_AFTER_VALUE_RE = re.compile(
    r"^\s*(?:尾\s*)?(?:[、,，.．+＋/]\s*|\s+)(\d)(?:\s*尾)?"
)
_LONG_TAIL_MARKER_RE = re.compile(
    rf"(?:{_ACTION}\s*(?:一个|一|①|1)?\s*尾(?:\s*数)?|杀\s*尾\s*数)"
)
_SHORT_KILL_VALUE_RE = re.compile(
    r"杀\s*[【\[(（〖《]\s*(\d{1,3})\s*[】\])）〗》]\s*尾"
)
_LIUXUAN_VALUE_RE = re.compile(
    r"绝\s*杀\s*[【\[]\s*\d\s*头\s*[.．]\s*(\d)\s*尾"
)

# Literal formatting words that some verified formats place between the field
# label and value. Removing these still leaves labels such as 杀码/杀头 with
# meaningful text, so they remain rejected as a different field.
_ALWAYS_ALLOWED_INFIX_WORDS = ("杀", "专区")
_ALLOWED_INFIX_WORDS_BY_PARSER: dict[str, tuple[str, ...]] = {}
_ALLOWED_FORMATTING_RE = re.compile(
    r"^[\s:：=＝◆◇〓\-—_~*#、，,.．。+＋!?！？"
    r"【\[\(（〖《】\]\)）〗》/\\]*$"
)

_DEDICATED_EXACT_EVIDENCE_PARSERS = frozenset(
    {
        "liuxuan_zhjs_tail",
        "caifu_gaoshou_kill_table",
        "ttss_list_article_top_tail",
        "kaijiangfacai_table_tail",
    }
)

_STRICT_SINGLE_TAIL_PATTERNS = (
    re.compile(
        rf"{_ACTION}\s*(?:一个|一|①|1)?\s*尾\s*"
        rf"(?:[:：=＝◆◇〓\-—_~*#、，,.．。+＋!?！？]\s*)*"
        rf"[【\[\(（〖《]?\s*(\d)(?!\d)"
        rf"(?!\s*(?:尾\s*)?(?:[、,，.．+＋/]\s*|\s+)\d)"
    ),
    re.compile(
        rf"{_ACTION}\s*(?:一个|一|①|1)?\s*"
        rf"(?:[:：=＝◆◇〓\-—_~*#、，,.．。+＋!?！？]\s*)*"
        rf"[【\[\(（〖《]?\s*(\d)(?!\d)\s*[】\]\)）〗》]?\s*尾"
    ),
    re.compile(
        r"杀\s*[【\[\(（〖《]\s*(\d)(?!\d)\s*[】\]\)）〗》]\s*尾"
    ),
)


def _prediction_only(text: str) -> str:
    normalized = normalize_text(text)
    match = _DRAW_BOUNDARY_RE.search(normalized)
    if match is not None:
        normalized = normalized[: match.start()]
    return normalized


def _period_evidence(document: str, period: int) -> str:
    text = normalize_text(document)
    chunks = [chunk.strip() for chunk in PERIOD_CHUNK_RE.split(text) if chunk.strip()]
    matched = []
    for chunk in chunks:
        period_match = PERIOD_RE.match(chunk)
        if period_match is not None and int(period_match.group(1)) == period:
            matched.append(chunk)
    return " ".join(matched)


def _record_evidence(record: Record, document: str) -> str:
    snippet = normalize_text(record.source_snippet)
    period_evidence = _period_evidence(document, record.period)
    if snippet and period_evidence and period_evidence not in snippet:
        return f"{snippet} {period_evidence}"
    return snippet or period_evidence


def _has_ambiguous_multi_digit_tail(text: str) -> bool:
    prediction = _prediction_only(text)
    for pattern in TAIL_PATTERNS:
        for match in pattern.finditer(prediction):
            value = match.group(1)
            if isinstance(value, str) and len(value) > 1:
                return True
    for match in _SHORT_KILL_VALUE_RE.finditer(prediction):
        if len(match.group(1)) > 1:
            return True
    return False


def _prefix_is_safe(prefix: str, parser_name: str) -> bool:
    cleaned = normalize_text(prefix)
    for word in (
        *_ALWAYS_ALLOWED_INFIX_WORDS,
        *_ALLOWED_INFIX_WORDS_BY_PARSER.get(parser_name, ()),
    ):
        cleaned = cleaned.replace(word, "")
    return _ALLOWED_FORMATTING_RE.fullmatch(cleaned) is not None


def _field_candidate_status(
    prediction: str,
    parser_name: str,
    expected_tail: int,
) -> tuple[bool, str]:
    """Return (has_safe_match, error_reason)."""

    safe_match = False
    errors: list[str] = []

    for match in _SHORT_KILL_VALUE_RE.finditer(prediction):
        raw = match.group(1)
        if len(raw) != 1:
            errors.append("单尾字段出现多位值")
            continue
        if int(raw) == expected_tail:
            safe_match = True

    for match in _LIUXUAN_VALUE_RE.finditer(prediction):
        if int(match.group(1)) == expected_tail:
            safe_match = True

    markers = list(_LONG_TAIL_MARKER_RE.finditer(prediction))
    for marker in markers:
        segment = prediction[marker.end() : marker.end() + 120]
        next_marker = _LONG_TAIL_MARKER_RE.search(segment)
        if next_marker is not None:
            segment = segment[: next_marker.start()]

        value_match = _VALUE_TOKEN_RE.search(segment)
        if value_match is None:
            continue

        prefix = segment[: value_match.start()]
        raw = value_match.group(1)
        if not _prefix_is_safe(prefix, parser_name):
            errors.append("单尾字段和值之间出现其他字段或说明文字")
            continue
        if len(raw) != 1:
            errors.append("单尾字段出现多位值")
            continue

        suffix = segment[value_match.end() :]
        if _MULTI_TAIL_AFTER_VALUE_RE.match(suffix):
            errors.append("单尾字段出现多个值")
            continue

        if int(raw) == expected_tail:
            safe_match = True

    return safe_match, errors[0] if errors else ""


def _has_strict_single_tail_evidence(text: str, expected_tail: int) -> bool:
    prediction = _prediction_only(text)
    for pattern in _STRICT_SINGLE_TAIL_PATTERNS:
        for match in pattern.finditer(prediction):
            if int(match.group(1)) == expected_tail:
                return True
    return False


def enforce_parsed_records(
    records: list[Record],
    *,
    source: str,
    parser_name: str,
    document: str,
    site_name: str,
) -> list[Record]:
    """Fail closed when a single-tail record cannot prove one exact source value."""

    for record in records:
        if record.tail_values or record.value_text:
            continue
        if source not in _SINGLE_TAIL_SOURCES:
            continue

        evidence = _record_evidence(record, document)
        if _has_ambiguous_multi_digit_tail(evidence):
            raise LookupError(
                f"{site_name}{record.period}期单尾字段出现多位值，拒绝截断为{record.tail}尾"
            )

        safe_match, field_error = _field_candidate_status(
            _prediction_only(evidence), parser_name, record.tail
        )

        if source == "dedicated":
            if parser_name in _DEDICATED_EXACT_EVIDENCE_PARSERS:
                continue
            if field_error:
                raise LookupError(f"{site_name}{record.period}期{field_error}")
            if not safe_match:
                recognized = bool(
                    _LONG_TAIL_MARKER_RE.search(_prediction_only(evidence))
                    or _SHORT_KILL_VALUE_RE.search(_prediction_only(evidence))
                )
                if recognized:
                    raise LookupError(
                        f"{site_name}{record.period}期单尾字段缺少可证明的直接值"
                    )
            continue

        if source in _GENERIC_STRICT_SOURCES:
            if field_error:
                raise LookupError(f"{site_name}{record.period}期{field_error}")
            if not (
                safe_match
                or _has_strict_single_tail_evidence(evidence, record.tail)
            ):
                raise LookupError(
                    f"{site_name}{record.period}期单尾字段和值不直接相邻，拒绝跨字段取值"
                )

    return records
