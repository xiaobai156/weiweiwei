from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from shawei.domain.defaults import (
    DEFAULT_EXCLUDE_KEYWORDS,
    SECTION_KEYWORDS,
    SECTION_TAIL_KEYWORDS,
    TABLE_TAIL_HEADERS,
)
from shawei.domain.text import canonical_pick


@dataclass(frozen=True)
class StrictRule:
    allowed_sources: tuple[str, ...] = ("section", "table", "compact")
    dedicated_parser: str = ""
    section_keywords: tuple[str, ...] = SECTION_KEYWORDS
    section_stop_keywords: tuple[str, ...] = ()
    chunk_keywords: tuple[str, ...] = SECTION_TAIL_KEYWORDS
    table_headers: tuple[str, ...] = TABLE_TAIL_HEADERS
    table_anchor_keywords: tuple[str, ...] = ()
    table_required_headers: tuple[str, ...] = ()
    table_stop_keywords: tuple[str, ...] = ()
    exclude_keywords: tuple[str, ...] = DEFAULT_EXCLUDE_KEYWORDS
    prefer_rendered: bool = False
    require_site_keyword: bool = False
    max_section_span: int = 1500
    lead_span: int = 700
    max_chunk_span: int = 240
    require_draw_signal: bool = True
    render_timeout: int | None = None
    follow_link_keywords: tuple[str, ...] = ()
    follow_link_rendered: bool = False
    follow_link_only: bool = False
    # Some list pages place the URL-bound target link on a later page.  The
    # fetch layer may follow same-list "下一页" links only when this flag is
    # explicitly enabled by the URL/name rule.
    follow_link_pagination: bool = False
    profile_parser: str = ""
    # Some URL-specific feeds expose several independent history blocks as
    # separate documents.  An explicit direction scope chooses the document
    # boundary before period/conflict validation; it never resolves a
    # conflict inside the selected document.
    direction_document_scope: str = ""
    # A small, explicitly configured set of sources can publish more than one
    # independent record for the same period inside the same dedicated area.
    # The validator numbers those records in document order and selects only
    # the first/last one according to the site direction.
    same_period_record_selection: bool = False
    # Some browser pages parse more reliably from body.inner_text than from the
    # HTML representation, whose CSS/JS can push the target block past bounds.
    prefer_rendered_body_text: bool = False


@dataclass(frozen=True)
class SiteConfig:
    name: str
    url: str
    pick: str = "top"
    archived: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "pick", canonical_pick(self.pick))


@dataclass(frozen=True)
class Document:
    source_url: str
    content: str
    source_type: str
    record_id: str = ""
    order: int = 0
    document_id: str = ""


@dataclass(frozen=True)
class Record:
    tail: int
    period: int
    site_name: str
    draw_text: str = ""
    value_text: str = ""
    source_snippet: str = ""
    tail_values: tuple[int, ...] = ()
    same_period_record_index: int = 0
    same_period_record_count: int = 0
    validation_error: str = ""

    def value(self) -> str:
        if self.tail_values:
            return "、".join(str(value) for value in self.tail_values)
        return self.value_text or str(self.tail)

    def as_line(self) -> str:
        if self.tail_values:
            labels = " ".join(f"{value}尾" for value in self.tail_values)
            return f"{labels} {self.site_name}"
        value = self.value()
        if self.value_text:
            return f"{value} {self.site_name}"
        return f"{value}尾 {self.site_name}"


@dataclass(frozen=True)
class Candidate:
    record: Record
    parser_id: str
    source_url: str
    source_type: str
    record_id: str = ""
    document_id: str = ""
    document_order: int = 0
    original_position: int = 0
    anchor: str = ""
    keyword: str = ""
    raw_block: str = ""
    same_period_record_index: int = 0
    same_period_record_count: int = 0


@dataclass(frozen=True)
class ValidationDecision:
    records: tuple[Record, ...]
    candidates: tuple[Candidate, ...]
    target_period: int | None
    pick: str
    all_candidates: tuple[Candidate, ...] = ()


@dataclass(frozen=True)
class FailureResult:
    stage: str
    reason: str
    site_name: str
    url: str
    candidate_count: int = 0
    conflict_values: tuple[str, ...] = ()
    elapsed_seconds: float = 0.0


@dataclass(frozen=True)
class CurrentRunResult:
    index: int
    success_line: str | None
    fail_line: str | None
    ranking_value: str | None
    messages: list[str]
    failure_stage: str = ""
    failure_reason: str = ""


class SiteLike(Protocol):
    name: str
    url: str
    pick: str
