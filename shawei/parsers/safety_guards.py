from __future__ import annotations

import re

from shawei.config.constants import PERIOD_CHUNK_RE, PERIOD_RE, TAIL_PATTERNS
from shawei.domain.models import Record
from shawei.domain.text import normalize_text


_GENERIC_STRICT_SOURCES = frozenset({"section", "compact", "lead_compact"})

_ACTION = r"(?:绝\s*杀|精准\s*杀|精\s*杀|稳\s*杀|狠\s*杀|主\s*杀|课\s*杀|杀\s*掉|禁|杀)"
_DRAW_BOUNDARY_RE = re.compile(
    r"开\s*[:：?？]?\s*(?=(?:[鼠牛虎兔龙蛇马羊猴鸡狗猪]\s*)?\d|\?)"
)
_STRICT_SINGLE_TAIL_PATTERNS = (
    re.compile(
        rf"{_ACTION}\s*(?:一个|一|①|1)?\s*尾\s*"
        rf"(?:[:：=◆◇〓\-—_~*#、，,.．。+＋]\s*)*"
        rf"[\[(]?\s*(\d)\s*尾?\s*[\])]?"
    ),
    re.compile(
        rf"{_ACTION}\s*(?:一个|一|①|1)?\s*"
        rf"(?:[:：=◆◇〓\-—_~*#、，,.．。+＋]\s*)*"
        rf"[\[(]?\s*(\d)\s*[\])]?\s*尾"
    ),
)
_CUSTOM_MULTI_DIGIT_TAIL_RE = re.compile(
    rf"{_ACTION}[^开\r\n]{{0,28}}?(\d{{2,3}})\s*尾?"
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
    if snippet:
        return snippet
    return _period_evidence(document, record.period)


def _has_ambiguous_multi_digit_tail(text: str) -> bool:
    prediction = _prediction_only(text)
    for pattern in TAIL_PATTERNS:
        for match in pattern.finditer(prediction):
            value = match.group(1)
            if isinstance(value, str) and len(value) > 1:
                return True
    custom = _CUSTOM_MULTI_DIGIT_TAIL_RE.search(prediction)
    return bool(custom and len(custom.group(1)) > 1)


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
    """Fail closed when a single-tail record cannot prove an unambiguous source field."""
    for record in records:
        if record.tail_values or record.value_text:
            continue
        evidence = _record_evidence(record, document)
        if _has_ambiguous_multi_digit_tail(evidence):
            raise LookupError(
                f"{site_name}{record.period}期单尾字段出现多位值，拒绝截断为{record.tail}尾"
            )
        if source in _GENERIC_STRICT_SOURCES and not _has_strict_single_tail_evidence(
            evidence, record.tail
        ):
            raise LookupError(
                f"{site_name}{record.period}期单尾字段和值不直接相邻，拒绝跨字段取值"
            )
    return records
