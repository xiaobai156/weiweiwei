from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import replace

from shawei.config.constants import TWO_TAIL_SITE_URLS
from shawei.config.rules import DEFAULT_STRICT_RULE
from shawei.domain.models import Candidate, Document, Record, StrictRule, ValidationDecision
from shawei.domain.text import is_bottom_pick, normalize_text
from shawei.parsers import registry


def _build_source_kwargs(
    source: str,
    rule: StrictRule,
    target_period: int | None,
    pick: str,
) -> dict:
    shared = {
        "exclude_keywords": rule.exclude_keywords,
        "require_site_keyword": rule.require_site_keyword,
    }
    if source == "section":
        return {
            **shared,
            "section_keywords": rule.section_keywords,
            "section_stop_keywords": rule.section_stop_keywords,
            "chunk_keywords": rule.chunk_keywords,
            "max_section_span": rule.max_section_span,
            "max_chunk_span": rule.max_chunk_span,
            "require_draw_signal": rule.require_draw_signal,
        }
    if source == "table":
        return {
            **shared,
            "table_headers": rule.table_headers,
            "table_anchor_keywords": rule.table_anchor_keywords,
            "table_required_headers": rule.table_required_headers,
            "table_stop_keywords": rule.table_stop_keywords,
        }
    if source == "compact":
        return {
            **shared,
            "chunk_keywords": rule.chunk_keywords,
            "max_chunk_span": rule.max_chunk_span,
            "require_draw_signal": rule.require_draw_signal,
        }
    if source == "dedicated":
        return {
            **shared,
            "parser_name": rule.dedicated_parser,
            "chunk_keywords": rule.chunk_keywords,
            "max_chunk_span": rule.max_chunk_span,
            "require_draw_signal": rule.require_draw_signal,
            "target_period": target_period,
            "pick": pick,
            "anchor_span": rule.max_section_span,
            "allow_same_period_records": rule.same_period_record_selection,
        }
    if source == "user_feed":
        return {
            **shared,
            "chunk_keywords": rule.chunk_keywords,
            "max_chunk_span": rule.max_chunk_span,
            "require_draw_signal": rule.require_draw_signal,
        }
    if source == "lead_compact":
        return {
            **shared,
            "chunk_keywords": rule.chunk_keywords,
            "lead_span": rule.lead_span,
            "max_chunk_span": rule.max_chunk_span,
            "require_draw_signal": rule.require_draw_signal,
        }
    raise LookupError(f"未知解析来源，拒绝兜底: {source}")


_SOURCE_KWARGS_CACHE: dict[
    tuple[str, int, int | None, str], tuple[StrictRule, dict]
] = {}

def _source_kwargs(
    source: str,
    rule: StrictRule,
    target_period: int | None,
    pick: str,
) -> dict:
    key = (source, id(rule), target_period, pick)
    cached = _SOURCE_KWARGS_CACHE.get(key)
    if cached is not None and cached[0] is rule:
        return cached[1]
    if len(_SOURCE_KWARGS_CACHE) >= 4096:
        _SOURCE_KWARGS_CACHE.clear()
    kwargs = _build_source_kwargs(source, rule, target_period, pick)
    _SOURCE_KWARGS_CACHE[key] = (rule, kwargs)
    return kwargs


# The draw result is independent from the published kill-tail prediction.
# ``开0000`` means the draw is pending; it remains a boundary record but does
# not invalidate an otherwise legal period + kill-tail value.
_NON_FATAL_RECORD_DIAGNOSTICS = frozenset({"开0000占位记录"})


def _validate_value_contract(
    record: Record,
    site_name: str,
    source_url: str = "",
) -> None:
    if (
        record.validation_error
        and record.validation_error not in _NON_FATAL_RECORD_DIAGNOSTICS
    ):
        raise LookupError(record.validation_error)
    if record.site_name != site_name and normalize_text(record.site_name) != normalize_text(site_name):
        raise LookupError(
            f"候选站名不匹配: 请求{site_name}，候选{record.site_name or '为空'}"
        )
    authorized_two_tail = source_url.strip() in TWO_TAIL_SITE_URLS
    if authorized_two_tail:
        if len(record.tail_values) != 2 or any(value < 0 or value > 9 for value in record.tail_values):
            raise LookupError(f"{site_name}必须是两个0-9尾数")
        return
    if record.tail_values:
        raise LookupError(
            f"{site_name}双尾授权URL不匹配: {source_url.strip() or '为空'}"
        )
    if record.value_text or record.tail < 0 or record.tail > 9:
        raise LookupError(f"{site_name}必须是一个0-9尾数")


def _document_for_input(document: str | Document, order: int) -> Document:
    if isinstance(document, Document):
        return document
    content = str(document)
    document_id = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
    return Document(
        source_url="",
        content=content,
        source_type="page",
        order=order,
        document_id=document_id,
    )


def _candidate_keyword(record: Record, rule: StrictRule) -> str:
    snippet = normalize_text(record.source_snippet)
    keywords = (
        *rule.section_keywords,
        *rule.table_anchor_keywords,
        *rule.chunk_keywords,
        *rule.table_headers,
    )
    return next((keyword for keyword in keywords if keyword and keyword in snippet), "")


def _parse_candidates(
    documents: Iterable[str | Document],
    site_name: str,
    pick: str,
    rule: StrictRule,
    target_period: int | None,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    expected_url = rule.site_url
    normalized_documents = [_document_for_input(document, index) for index, document in enumerate(documents)]
    for input_order, document in enumerate(normalized_documents):
        if expected_url and document.source_url and document.source_url != expected_url:
            raise LookupError(
                f"候选来源URL不匹配: 规则{expected_url}，文档{document.source_url}"
            )
        document_order = document.order if document.order else input_order
        parser_ids = (
            ("dedicated",)
            if rule.dedicated_parser and "dedicated" in rule.allowed_sources
            else rule.allowed_sources
        )
        for parser_id in parser_ids:
            source_records = registry.parse_source(
                parser_id,
                document.content,
                site_name,
                **_source_kwargs(parser_id, rule, target_period, pick),
            )
            for position, record in enumerate(source_records):
                keyword = _candidate_keyword(record, rule)
                candidates.append(
                    Candidate(
                        record=record,
                        parser_id=parser_id,
                        source_url=document.source_url,
                        source_type=document.source_type,
                        record_id=document.record_id,
                        document_id=document.document_id,
                        document_order=document_order,
                        original_position=position,
                        anchor=keyword or record.site_name,
                        keyword=keyword,
                        raw_block=record.source_snippet,
                    )
                )
    return candidates


def _apply_direction_document_scope(
    candidates: list[Candidate], pick: str, scope: str
) -> list[Candidate]:
    normalized_scope = normalize_text(scope).lower()
    if not normalized_scope:
        return candidates
    if normalized_scope not in {"top", "bottom"}:
        raise LookupError(f"未知方向文档边界: {scope}")
    if not candidates:
        return candidates
    document_orders = [candidate.document_order for candidate in candidates]
    selected_order = (
        max(document_orders)
        if normalized_scope == "bottom"
        else min(document_orders)
    )
    return [
        candidate
        for candidate in candidates
        if candidate.document_order == selected_order
    ]


def _candidate_order_key(candidate: Candidate) -> tuple[int, int, str, str]:
    return (
        candidate.document_order,
        candidate.original_position,
        candidate.parser_id,
        candidate.document_id,
    )


def _require_absolute_target_boundary(
    candidates: list[Candidate], target_period: int, use_bottom: bool
) -> Candidate | None:
    if not candidates:
        return None
    ordered = sorted(candidates, key=_candidate_order_key)
    boundary = ordered[-1] if use_bottom else ordered[0]
    if boundary.record.period != target_period:
        direction = "bottom" if use_bottom else "top"
        raise LookupError(
            f"绝对{direction}边界是{boundary.record.period}期，不是指定{target_period}期"
        )
    return boundary


def _candidate_authority_key(candidate: Candidate) -> tuple[object, ...]:
    """Identify the parser/document scope that may make an independent claim.

    A document can expose several rows for the same period; those rows are
    intentionally left to the direction boundary selector.  A different
    document or parser source is an independent authority, however, and must
    not be silently hidden by choosing one direction.  Keep the identity tied
    to the evidence carried by ``Candidate`` rather than to a parsed value.
    """

    return (
        candidate.source_url,
        candidate.source_type,
        candidate.record_id,
        candidate.document_id,
        candidate.document_order,
        candidate.parser_id,
    )


def _candidate_evidence_signature(candidate: Candidate) -> tuple[object, ...] | None:
    raw_block = normalize_text(candidate.raw_block)
    if not raw_block:
        return None
    return (
        candidate.record.period,
        candidate.record.value(),
        raw_block,
        candidate.record.validation_error,
    )


def _contains_contiguous_sequence(
    larger: tuple[tuple[object, ...], ...],
    smaller: tuple[tuple[object, ...], ...],
) -> bool:
    if not smaller or len(smaller) >= len(larger):
        return False
    width = len(smaller)
    return any(
        larger[start : start + width] == smaller
        for start in range(len(larger) - width + 1)
    )


def _remove_subsumed_page_fragments(candidates: list[Candidate]) -> list[Candidate]:
    """Drop exact decoded fragments already carried by a larger page block.

    Script decoding can return both a complete topic body and several exact
    row fragments from that same URL.  Those fragments are presentations of
    the complete page evidence, not independent authorities with their own
    top/bottom boundary.  Only exact, contiguous evidence from the same page
    provenance is collapsed; browser/API sources and non-identical blocks
    remain independent and still participate in conflict checks.
    """

    grouped: dict[tuple[object, ...], list[Candidate]] = {}
    for candidate in candidates:
        grouped.setdefault(_candidate_authority_key(candidate), []).append(candidate)

    authority_sequences: dict[
        tuple[object, ...], tuple[tuple[object, ...], ...]
    ] = {}
    authority_provenance: dict[tuple[object, ...], tuple[object, ...]] = {}
    for authority_key, authority_candidates in grouped.items():
        ordered = sorted(authority_candidates, key=_candidate_order_key)
        signatures = tuple(
            signature
            for candidate in ordered
            if (signature := _candidate_evidence_signature(candidate)) is not None
        )
        if len(signatures) != len(ordered):
            continue
        authority_sequences[authority_key] = signatures
        first = ordered[0]
        authority_provenance[authority_key] = (
            first.source_url,
            first.source_type,
            first.record_id,
            first.parser_id,
        )

    subsumed: set[tuple[object, ...]] = set()
    for authority_key, sequence in authority_sequences.items():
        provenance = authority_provenance[authority_key]
        if provenance[1] != "page":
            continue
        for larger_key, larger_sequence in authority_sequences.items():
            if authority_key == larger_key:
                continue
            if authority_provenance[larger_key] != provenance:
                continue
            if _contains_contiguous_sequence(larger_sequence, sequence):
                subsumed.add(authority_key)
                break

    if not subsumed:
        return candidates
    return [
        candidate
        for candidate in candidates
        if _candidate_authority_key(candidate) not in subsumed
    ]


def _require_target_authority_consistency(
    candidates: Iterable[Candidate],
    target_period: int,
    use_bottom: bool,
    site_name: str,
    expected_url: str = "",
) -> tuple[Candidate, ...]:
    """Validate and compare each independent authority's direction edge.

    Rows inside one authority block are diagnostics: only that block's
    absolute edge participates in the targeted decision.  Every independent
    block that contains the requested period must expose it at its own edge
    and its edge record must satisfy the value contract.  Different edge
    values are a real source conflict; non-edge rows never create one.
    """

    candidates = _remove_subsumed_page_fragments(list(candidates))
    grouped: dict[tuple[object, ...], list[Candidate]] = {}
    for candidate in candidates:
        grouped.setdefault(_candidate_authority_key(candidate), []).append(candidate)
    if not grouped:
        return ()

    boundaries: list[Candidate] = []
    direction = "bottom" if use_bottom else "top"
    for authority_candidates in grouped.values():
        ordered = sorted(authority_candidates, key=_candidate_order_key)
        # A secondary document may contain only an older/newer history row
        # (for example a rendered/page duplicate).  It has no claim on the
        # requested period and must not manufacture a boundary failure.  The
        # global boundary check still prevents an out-of-scope row from
        # replacing the target at the selected direction edge.
        if not any(
            candidate.record.period == target_period for candidate in ordered
        ):
            continue
        boundary = ordered[-1] if use_bottom else ordered[0]
        if boundary.record.period != target_period:
            raise LookupError(
                f"绝对{direction}边界是{boundary.record.period}期，不是指定{target_period}期"
            )
        try:
            _validate_value_contract(
                boundary.record,
                site_name,
                boundary.source_url.strip() or expected_url,
            )
        except LookupError as exc:
            raise LookupError(f"绝对{direction}边界记录无效: {exc}") from exc
        boundaries.append(boundary)

    values = {boundary.record.value() for boundary in boundaries}
    if len(values) > 1:
        raise LookupError(
            f"{target_period}期存在多个候选且数据冲突: {'、'.join(sorted(values))}"
        )
    return tuple(boundaries)


def _deduplicate_same_period_presentations(
    candidates: Iterable[Candidate],
) -> list[Candidate]:
    """Collapse API/browser copies without collapsing independent blocks.

    A same-period special site is numbered from real blocks, not from every
    parser pass.  An identical raw block at the same parsed position is one
    presentation; a different block or position remains an independent
    record.
    """
    unique: list[Candidate] = []
    seen: set[tuple[object, ...]] = set()
    for candidate in sorted(candidates, key=_candidate_order_key):
        raw_block = normalize_text(candidate.raw_block)
        if raw_block:
            record_scope = candidate.record_id
            key = (
                "block",
                candidate.record.period,
                candidate.record.value(),
                raw_block,
                candidate.original_position,
                record_scope,
            )
        else:
            key = (
                "candidate",
                candidate.record.period,
                candidate.record.value(),
                candidate.document_id,
                candidate.record_id,
                candidate.parser_id,
                candidate.original_position,
            )
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _records_by_period(
    candidates: Iterable[Candidate],
    target_period: int | None,
    use_bottom: bool,
    allow_same_period_records: bool = False,
) -> tuple[dict[int, Record], list[Candidate], dict[int, Candidate]]:
    records = list(candidates)
    grouped: dict[int, list[Candidate]] = {}
    for candidate in records:
        grouped.setdefault(candidate.record.period, []).append(candidate)

    selected: dict[int, Record] = {}
    selected_candidates: dict[int, Candidate] = {}
    numbered_candidates: list[Candidate] = []
    for period, period_records in grouped.items():
        if allow_same_period_records:
            count = len(period_records)
            numbered = []
            for index, candidate in enumerate(period_records, start=1):
                marker = f"专属区{period}期记录编号 {index}/{count}"
                snippet = candidate.record.source_snippet
                if marker not in snippet:
                    snippet = f"{marker} {snippet}".strip()
                record = replace(
                    candidate.record,
                    source_snippet=snippet,
                    same_period_record_index=index,
                    same_period_record_count=count,
                )
                numbered.append(
                    replace(
                        candidate,
                        record=record,
                        same_period_record_index=index,
                        same_period_record_count=count,
                    )
                )
            numbered_candidates.extend(numbered)
            selected_candidate = numbered[-1] if use_bottom else numbered[0]
            selected[period] = selected_candidate.record
            selected_candidates[period] = selected_candidate
            continue

        values = {candidate.record.value() for candidate in period_records}
        if len(values) > 1:
            raise LookupError(f"{period}期存在多个候选且数据冲突: {'、'.join(sorted(values))}")
        selected_candidate = period_records[-1] if use_bottom else period_records[0]
        selected[period] = selected_candidate.record
        selected_candidates[period] = selected_candidate
        numbered_candidates.extend(period_records)
    return selected, numbered_candidates, selected_candidates


def validate_documents(
    documents: Iterable[str | Document],
    site_name: str,
    limit: int | None = None,
    pick: str = "top",
    rule: StrictRule | None = None,
    target_period: int | None = None,
) -> ValidationDecision:
    active_rule = rule or DEFAULT_STRICT_RULE
    identity_url = active_rule.site_url
    use_bottom = is_bottom_pick(pick)
    candidates = _parse_candidates(documents, site_name, pick, active_rule, target_period)
    all_candidates = list(candidates)
    candidates = _apply_direction_document_scope(
        candidates,
        pick,
        active_rule.direction_document_scope,
    )
    if active_rule.same_period_record_selection:
        candidates = _deduplicate_same_period_presentations(candidates)
    selected_candidates: dict[int, Candidate] = {}
    if target_period is not None:
        target_candidates = [
            candidate for candidate in candidates if candidate.record.period == target_period
        ]
        if not target_candidates:
            authority_groups: dict[tuple[object, ...], list[Candidate]] = {}
            for candidate in candidates:
                authority_groups.setdefault(
                    _candidate_authority_key(candidate), []
                ).append(candidate)
            authority_boundary_periods = {
                (ordered[-1] if use_bottom else ordered[0]).record.period
                for authority_candidates in authority_groups.values()
                if (ordered := sorted(authority_candidates, key=_candidate_order_key))
            }
            if len(authority_boundary_periods) == 1:
                boundary_period = next(iter(authority_boundary_periods))
                direction = "bottom" if use_bottom else "top"
                raise LookupError(
                    f"绝对{direction}边界是{boundary_period}期，不是指定{target_period}期"
                )
            records: list[Record] = []
            numbered_candidates: list[Candidate] = []
        elif active_rule.same_period_record_selection:
            boundary_candidate = _require_absolute_target_boundary(
                candidates, target_period, use_bottom
            )
            assert boundary_candidate is not None
            # Validate the selected edge before considering any other target
            # row.  An invalid edge is a hard failure; another same-period row
            # can never be used as a fallback.
            boundary_record = boundary_candidate.record
            try:
                _validate_value_contract(
                    boundary_record,
                    site_name,
                    boundary_candidate.source_url.strip() or identity_url,
                )
            except LookupError as exc:
                direction = "bottom" if use_bottom else "top"
                raise LookupError(f"绝对{direction}边界记录无效: {exc}") from exc
            selected, numbered_candidates, selected_candidates = _records_by_period(
                target_candidates,
                target_period,
                use_bottom,
                allow_same_period_records=True,
            )
            records = [selected[target_period]]
        else:
            boundaries = _require_target_authority_consistency(
                candidates,
                target_period,
                use_bottom,
                site_name,
                identity_url,
            )
            boundary_candidate = boundaries[0]
            numbered_candidates = target_candidates
            records = [boundary_candidate.record]
            selected_candidates = {target_period: boundary_candidate}
    else:
        selected, numbered_candidates, selected_candidates = _records_by_period(
            candidates,
            target_period,
            use_bottom,
            active_rule.same_period_record_selection,
        )
        records = list(selected.values())
    if target_period is None:
        for period, record in selected.items():
            candidate = selected_candidates[period]
            _validate_value_contract(
                record,
                site_name,
                candidate.source_url.strip() or identity_url,
            )
    elif selected_candidates:
        selected_candidate = selected_candidates[target_period]
        _validate_value_contract(
            records[0],
            site_name,
            selected_candidate.source_url.strip() or identity_url,
        )
    if limit is None or limit <= 0:
        limited = records
    else:
        limited = records[:limit]
    return ValidationDecision(
        tuple(limited),
        tuple(numbered_candidates),
        target_period,
        pick,
        tuple(all_candidates),
    )


def collect_candidates(
    documents: Iterable[str | Document],
    site_name: str,
    pick: str = "top",
    rule: StrictRule | None = None,
    target_period: int | None = None,
) -> list[Candidate]:
    return _parse_candidates(
        documents,
        site_name,
        pick,
        rule or DEFAULT_STRICT_RULE,
        target_period,
    )


def select_current_record(
    records: list[Record], period: int, pick: str = "top"
) -> tuple[Record, int | None]:
    if not records:
        raise LookupError(f"没有找到{period}期数据")
    latest = records[-1] if is_bottom_pick(pick) else records[0]
    if latest.period == period:
        return latest, None
    raise LookupError(f"top/bottom最近候选是{latest.period}期，不是指定{period}期")
