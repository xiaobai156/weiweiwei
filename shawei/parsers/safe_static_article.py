from __future__ import annotations

import re

from shawei.config.constants import DEFAULT_EXCLUDE_KEYWORDS, PERIOD_RE
from shawei.domain.models import Record
from shawei.domain.text import contains_none, normalize_text
from shawei.parsers.common import _compact_snippet, _has_draw_signal, extract_draw_text
from shawei.parsers.topic import (
    _ArticleBodyEventParser,
    _article_plain_scope,
    _article_title_matches,
)


_SINGLE_VALUE_RE = re.compile(r"\s*(\d)\s*尾?\s*")
_TWO_VALUE_RE = re.compile(
    r"\s*(\d)\s*尾?\s*(?:[,，、.]|．)\s*(\d)\s*尾?\s*"
)
_BRACKET_RE = re.compile(r"[\[(]([^\]\)]{1,40})[\])]")
_ALLOWED_VALUE_PREFIX_RE = re.compile(
    r"^[\s:：=◆◇〓\-—_~*#、，,.．。+＋]*$"
)


def _split_period_rows(row: str) -> list[str]:
    text = normalize_text(row)
    matches = list(PERIOD_RE.finditer(text))
    if not matches:
        return []
    return [
        text[
            match.start() :
            matches[index + 1].start() if index + 1 < len(matches) else len(text)
        ].strip()
        for index, match in enumerate(matches)
    ]


def _value_after_keyword(
    row_text: str,
    keywords: tuple[str, ...],
    two_tail: bool,
) -> tuple[int, ...] | None:
    row = normalize_text(row_text)
    positions = [
        (row.find(keyword), keyword)
        for keyword in keywords
        if keyword and row.find(keyword) >= 0
    ]
    if not positions:
        return None
    _, keyword = min(positions, key=lambda item: item[0])
    suffix = row[row.find(keyword) + len(keyword) :]
    next_period = PERIOD_RE.search(suffix)
    if next_period is not None:
        suffix = suffix[: next_period.start()]
    suffix = suffix[:140]

    bracket = _BRACKET_RE.search(suffix)
    if bracket is None:
        return None
    prefix = normalize_text(suffix[: bracket.start()])
    # The target value must immediately follow the tail field.  Arbitrary
    # words such as 推荐/杀码/杀头 cannot sit between the tail label and value.
    if _ALLOWED_VALUE_PREFIX_RE.fullmatch(prefix) is None:
        return None

    value_text = normalize_text(bracket.group(1))
    pattern = _TWO_VALUE_RE if two_tail else _SINGLE_VALUE_RE
    match = pattern.fullmatch(value_text)
    if match is None:
        return None
    return tuple(int(group) for group in match.groups())


def _records_from_rows(
    rows: list[str],
    site_name: str,
    keywords: tuple[str, ...],
    two_tail: bool,
    exclude_keywords: tuple[str, ...],
    max_chunk_span: int,
    require_draw_signal: bool,
) -> list[Record]:
    records: list[Record] = []
    for source_row in rows:
        for row in _split_period_rows(source_row):
            period_match = PERIOD_RE.match(row)
            if period_match is None or not any(keyword in row for keyword in keywords):
                continue
            if exclude_keywords and not contains_none(row, exclude_keywords):
                continue
            if require_draw_signal and not _has_draw_signal(row):
                continue
            values = _value_after_keyword(row, keywords, two_tail)
            if values is None:
                continue
            records.append(
                Record(
                    tail=values[0],
                    tail_values=values if two_tail else (),
                    period=int(period_match.group(1)),
                    site_name=site_name,
                    draw_text=extract_draw_text(row),
                    source_snippet=_compact_snippet(
                        f"{site_name} {row}", max(80, max_chunk_span)
                    ),
                )
            )
    return records


def extract_safe_static_article_body_records(
    document: str,
    site_name: str,
    chunk_keywords: tuple[str, ...],
    two_tail: bool = False,
    exclude_keywords: tuple[str, ...] = DEFAULT_EXCLUDE_KEYWORDS,
    max_chunk_span: int = 240,
    require_draw_signal: bool = True,
    require_site_keyword: bool = True,
) -> list[Record]:
    """Parse one URL-bound static article without borrowing another field/period."""
    keywords = tuple(normalize_text(keyword) for keyword in chunk_keywords if keyword)
    if not keywords:
        return []

    if re.search(r"<[A-Za-z][^>]*>", document):
        parser = _ArticleBodyEventParser()
        try:
            parser.feed(document)
            parser.close()
        except Exception:
            return []
        title_index = next(
            (
                index
                for index, (kind, text) in enumerate(parser.events)
                if kind == "h2" and _article_title_matches(text, site_name, keywords)
            ),
            None,
        )
        if title_index is None:
            return []
        rows: list[str] = []
        for kind, text in parser.events[title_index + 1 :]:
            if "上一篇" in text or "下一篇" in text:
                break
            if kind == "p":
                rows.append(text)
        return _records_from_rows(
            rows,
            site_name,
            keywords,
            two_tail,
            exclude_keywords,
            max_chunk_span,
            require_draw_signal,
        )

    scope = _article_plain_scope(document, site_name, keywords)
    if require_site_keyword and not scope:
        return []
    if not scope:
        return []
    return _records_from_rows(
        [scope],
        site_name,
        keywords,
        two_tail,
        exclude_keywords,
        max_chunk_span,
        require_draw_signal,
    )
