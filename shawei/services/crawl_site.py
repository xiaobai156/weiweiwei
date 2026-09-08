from __future__ import annotations

import re
import threading
import time
from collections.abc import Iterable
from urllib.parse import urlparse

from shawei.config.constants import DIRECTION_BOUNDARY_WINDOW, PERIOD_CHUNK_RE, PERIOD_RE
from shawei.config.rules import STRICT_SITE_RULES, effective_rule_for
from shawei.domain.models import (
    CurrentRunResult,
    Document,
    Record,
    SiteLike,
    StrictRule,
)
from shawei.domain.text import normalize_text
from shawei.fetch import browser, document_discovery
from shawei.fetch.dynamic_article import (
    DynamicArticleEmptyShellError,
    DynamicArticleNotFoundError,
    dynamic_article_api_urls,
    is_dynamic_article_url,
)
from shawei.fetch.http_client import (
    FETCH_CACHE_LOCK,
    FETCH_STATUS,
    RECORD_CACHE,
    RENDER_STATUS,
    RUNTIME_CACHE_LOCK,
    clear_fetch_cache,
)
from shawei.fetch.profile import (
    _is_unscoped_dynamic_aggregate_url,
    dynamic_scope_target_id,
    is_dynamic_scoped_url,
)
from shawei.parsers.common import extract_tail_value, is_valid_tail_record
from shawei.parsers.topic import _DynamicHtmlNode, _DynamicHtmlParser, _dynamic_node_text
from shawei.validation.validator import select_current_record, validate_documents


DOMAIN_LOCKS: dict[str, threading.RLock] = {}
DOMAIN_LOCKS_GUARD = threading.Lock()


def _domain_lock_for(url: str) -> threading.RLock:
    key = urlparse(url).netloc.lower() or url.lower()
    with DOMAIN_LOCKS_GUARD:
        return DOMAIN_LOCKS.setdefault(key, threading.RLock())


def site_lock_for(url: str) -> threading.RLock:
    return _domain_lock_for(url)


def _extract_site_records_from_documents(
    documents: Iterable[str | Document],
    site_name: str,
    pick: str,
    rule: StrictRule,
    target_period: int | None,
) -> list[Record]:
    decision = validate_documents(
        documents,
        site_name,
        limit=0,
        pick=pick,
        rule=rule,
        target_period=target_period,
    )
    return list(decision.records)


def _document_content(document: str | Document) -> str:
    return document.content if isinstance(document, Document) else document


def _documentize(url: str, contents: list[str], source_type: str) -> list[Document]:
    return document_discovery.build_documents(url, contents, source_type)


def _prefer_structured_rendered_documents(rendered: list[str]) -> list[str]:
    """Avoid parsing body text and its identical DOM as separate sources."""
    structured = [
        document
        for document in rendered
        if re.search(r"<[A-Za-z][^>]*>", document)
    ]
    return structured or rendered


def _prefer_rendered_documents(
    rendered: list[str], prefer_body_text: bool = False
) -> list[str]:
    if prefer_body_text:
        body_text = next(
            (
                document
                for document in rendered
                if not re.search(r"<[A-Za-z][^>]*>", document)
            ),
            None,
        )
        if body_text is not None:
            return [body_text]
    return _prefer_structured_rendered_documents(rendered)


def _documents_lack_target_or_keywords(
    documents: Iterable[str | Document],
    target_period: int | None,
    keywords: tuple[str, ...],
) -> bool:
    combined = normalize_text("\n".join(_document_content(document) for document in documents))
    if not combined:
        return True
    if target_period is not None and not re.search(rf"(?<!\d){target_period}\s*期", combined):
        return True
    signals = tuple(keyword for keyword in keywords if keyword)
    return bool(signals) and not any(keyword in combined for keyword in signals)


def _article_admin_failure_reason(
    url: str,
    documents: Iterable[str | Document],
    rule: StrictRule,
    target_period: int | None,
    timeout: int,
) -> str:
    reasons: list[str] = []
    for api_url in dynamic_article_api_urls(url):
        with FETCH_CACHE_LOCK:
            status = FETCH_STATUS.get(api_url, "未请求")
        reasons.append(f"接口:{status}")
    combined = normalize_text("\n".join(_document_content(document) for document in documents))
    if target_period is not None and not re.search(rf"(?<!\d){target_period}\s*期", combined):
        reasons.append(f"原始内容没有{target_period}期")
    elif target_period is not None:
        chunks = []
        for chunk in PERIOD_CHUNK_RE.split(combined):
            chunk = chunk.strip()
            match = PERIOD_RE.match(chunk)
            if chunk and match is not None and int(match.group(1)) == target_period:
                chunks.append(chunk)
        if not any(extract_tail_value(chunk) is not None for chunk in chunks):
            reasons.append(f"正文没有{target_period}期可验证尾数字段（标题期数不计入）")
    signals = rule.chunk_keywords + rule.table_headers
    if signals and not any(keyword in combined for keyword in signals):
        reasons.append("原始内容没有专属关键词")
    with RUNTIME_CACHE_LOCK:
        render_status = RENDER_STATUS.get((url, int(timeout)), "未触发浏览器渲染")
    reasons.append(f"浏览器:{render_status}")
    return "article/admin专属抓取失败(" + "；".join(reasons) + ")"


def _dynamic_node_has_target(node: _DynamicHtmlNode, target_id: str) -> bool:
    identity_attributes = {
        "id",
        "data-id",
        "data-article-id",
        "data-articleid",
        "data-topic-id",
        "data-record-id",
        "data-post-id",
        "href",
    }
    return any(
        key in identity_attributes
        and (
            value == target_id
            or re.search(rf"(?<![A-Za-z0-9]){re.escape(target_id)}(?![A-Za-z0-9])", value)
        )
        for key, value in node.attrs.items()
    )


def _dynamic_target_blocks(document: str, target_id: str) -> list[str]:
    parser = _DynamicHtmlParser()
    try:
        parser.feed(document)
        parser.close()
    except Exception:
        return []
    blocks: list[str] = []
    block_tags = {"article", "section", "li", "div", "main"}
    pending = [parser.root]
    while pending:
        node = pending.pop()
        if node.tag in {"script", "style", "noscript"}:
            continue
        if _dynamic_node_has_target(node, target_id):
            candidate = node
            while candidate.parent is not None and candidate.tag not in block_tags:
                candidate = candidate.parent
            text = _dynamic_node_text(candidate)
            if text and text not in blocks:
                blocks.append(text)
        pending.extend(reversed(node.children))
    return blocks


def _validate_dynamic_render_documents(
    url: str,
    documents: Iterable[str | Document],
    expected_author: str = "",
) -> list[str]:
    target_id = dynamic_scope_target_id(url)
    if not target_id:
        return [_document_content(document) for document in documents]
    matched: list[str] = []
    for document in documents:
        content = _document_content(document)
        if not content:
            continue
        if "<" in content and ">" in content:
            candidates = _dynamic_target_blocks(content, target_id)
        else:
            candidates = (
                [content]
                if re.search(rf"(?<![A-Za-z0-9]){re.escape(target_id)}(?![A-Za-z0-9])", content)
                else []
            )
        for candidate in candidates:
            if expected_author and normalize_text(expected_author) not in normalize_text(candidate):
                continue
            if candidate not in matched:
                matched.append(candidate)
    if not matched:
        raise LookupError(f"浏览器渲染未找到目标记录ID {target_id}")
    return matched


def _is_dynamic_identity_error(exc: Exception) -> bool:
    return any(
        marker in str(exc)
        for marker in (
            "未匹配到唯一文章记录",
            "匹配到 0 条",
            "匹配到 2 条",
            "栏目归属不一致",
            "作者不匹配",
            "作者字段缺失",
            "标题字段缺失",
            "正文字段缺失",
            "浏览器渲染未找到目标记录ID",
            "论坛目标ID ",
        )
    )


def _cache_records(cache_key: tuple, records: list[Record]) -> list[Record]:
    if records:
        with RUNTIME_CACHE_LOCK:
            RECORD_CACHE[cache_key] = list(records)
    return records


def _collect_admin_article_records(
    url: str,
    site_name: str,
    pick: str,
    timeout: int,
    target_period: int | None,
    rule: StrictRule,
    cache_key: tuple,
) -> list[Record]:
    render_timeout = max(timeout, rule.render_timeout or timeout)
    documents: list[Document] = []
    fetch_error: Exception | None = None
    try:
        documents = _documentize(
            url,
            document_discovery.collect_documents(
                url,
                timeout,
                rule.follow_link_keywords,
                rule.follow_link_rendered,
                rule.follow_link_only,
                pick,
                site_name=site_name,
            ),
            "dynamic",
        )
    except Exception as exc:
        fetch_error = exc
    if fetch_error is not None and _is_dynamic_identity_error(fetch_error) and not isinstance(
        fetch_error, DynamicArticleEmptyShellError
    ):
        raise fetch_error

    if fetch_error is None and documents:
        records = _extract_site_records_from_documents(
            documents, site_name, pick, rule, target_period
        )
        if records:
            return _cache_records(cache_key, records)
        raise LookupError(
            _article_admin_failure_reason(url, documents, rule, target_period, render_timeout)
        )

    fallback_allowed = isinstance(
        fetch_error, (DynamicArticleEmptyShellError, DynamicArticleNotFoundError)
    )
    rendered: list[str] = []
    render_validation_error: Exception | None = None
    if fallback_allowed:
        rendered = browser.render_browser_documents(url, render_timeout)
        if rendered:
            try:
                rendered = _validate_dynamic_render_documents(url, rendered, site_name)
            except Exception as exc:
                render_validation_error = exc
                rendered = []

    if rendered:
        rendered_documents = _documentize(url, rendered, "browser")
        records = _extract_site_records_from_documents(
            rendered_documents + documents, site_name, pick, rule, target_period
        )
        if records:
            return _cache_records(cache_key, records)

    if fallback_allowed and documents:
        records = _extract_site_records_from_documents(
            documents, site_name, pick, rule, target_period
        )
        if records:
            return _cache_records(cache_key, records)

    if fallback_allowed:
        if fetch_error is not None and not documents and render_validation_error is not None:
            raise fetch_error
        if render_validation_error is not None and not documents:
            raise render_validation_error
        raise LookupError(
            _article_admin_failure_reason(url, documents, rule, target_period, render_timeout)
        )

    if fetch_error is not None and not documents:
        raise fetch_error
    raise LookupError(_article_admin_failure_reason(url, documents, rule, target_period, render_timeout))


def collect_site_records(
    url: str,
    site_name: str,
    pick: str = "top",
    timeout: int = 20,
    target_period: int | None = None,
) -> list[Record]:
    if _is_unscoped_dynamic_aggregate_url(url) and url not in STRICT_SITE_RULES:
        raise LookupError("动态聚合页面缺少唯一文章ID，禁止扫描整个接口响应或按第一篇记录取值")
    cache_key = (url, normalize_text(site_name), normalize_text(pick).lower(), int(timeout), target_period)
    with RUNTIME_CACHE_LOCK:
        cached = RECORD_CACHE.get(cache_key)
        if cached is not None:
            return list(cached)

    rule = effective_rule_for(url, site_name)
    if rule.profile_parser:
        documents = _documentize(
            url,
            document_discovery.collect_documents(
                url,
                timeout,
                rule.follow_link_keywords,
                rule.follow_link_rendered,
                rule.follow_link_only,
                pick,
                site_name=site_name,
                target_period=target_period,
                profile_parser=rule.profile_parser,
                profile_boundary_window=DIRECTION_BOUNDARY_WINDOW,
                same_period_record_selection=rule.same_period_record_selection,
                follow_link_pagination=rule.follow_link_pagination,
            ),
            "profile",
        )
        records = _extract_site_records_from_documents(
            documents, site_name, pick, rule, target_period
        )
        if records:
            return _cache_records(cache_key, records)
        raise LookupError(f"{site_name}专属用户记录已锁定，但没有解析出{target_period}期数据")

    if is_dynamic_article_url(url):
        return _collect_admin_article_records(
            url, site_name, pick, timeout, target_period, rule, cache_key
        )

    needs_render = rule.prefer_rendered and not is_dynamic_scoped_url(url)
    documents: list[Document] = []
    rendered: list[str] = []
    fetch_error: Exception | None = None
    if needs_render:
        rendered = browser.render_browser_documents(
            url, max(timeout, rule.render_timeout or timeout)
        )
    else:
        try:
            documents = _documentize(
                url,
                document_discovery.collect_documents(
                    url,
                    timeout,
                    rule.follow_link_keywords,
                    rule.follow_link_rendered,
                    rule.follow_link_only,
                    pick,
                    site_name=site_name,
                    follow_link_pagination=rule.follow_link_pagination,
                ),
                "page",
            )
        except Exception as exc:
            fetch_error = exc
        if is_dynamic_scoped_url(url) and (
            not documents
            or _documents_lack_target_or_keywords(
                documents, target_period, rule.chunk_keywords + rule.table_headers
            )
        ) and fetch_error is None:
            rendered = browser.render_browser_documents(url, timeout)

    if fetch_error is not None and _is_dynamic_identity_error(fetch_error):
        raise fetch_error
    rendered = _prefer_rendered_documents(
        rendered,
        prefer_body_text=rule.prefer_rendered_body_text,
    )
    if rendered and is_dynamic_scoped_url(url):
        rendered = _validate_dynamic_render_documents(url, rendered, site_name)
    if not documents and not rendered and fetch_error is not None:
        raise fetch_error

    rendered_documents = _documentize(url, rendered, "browser")
    if rendered_documents and (
        rule.prefer_rendered_body_text
        or (rule.prefer_rendered and set(rule.allowed_sources).issubset({"lead_compact"}))
    ):
        ordered = rendered_documents[:1]
    else:
        ordered = rendered_documents + documents if rule.prefer_rendered else documents + rendered_documents
    records = _extract_site_records_from_documents(
        ordered, site_name, pick, rule, target_period
    )
    return _cache_records(cache_key, records)
def _site_failure(
    index: int,
    site: SiteLike,
    stage: str,
    reason: str,
    messages: list[str],
    line_reason: str | None = None,
    period: int | None = None,
) -> CurrentRunResult:
    return CurrentRunResult(
        index=index,
        success_line=None,
        fail_line=(
            f"失败 {site.name} {site.url} 方向: {site.pick} "
            f"期数: {period if period is not None else '未知'} 阶段: {stage} "
            f"原因: {line_reason or reason}"
        ),
        ranking_value=None,
        messages=messages,
        failure_stage=stage,
        failure_reason=reason,
    )


def crawl_current_site(
    index: int,
    total: int,
    site: SiteLike,
    period: int,
    timeout: int,
    retries: int = 1,
) -> CurrentRunResult:
    messages = [f"[{index}/{total}] {site.name} {site.pick} {site.url}"]
    records: list[Record] = []
    record: Record | None = None
    try:
        with _domain_lock_for(site.url):
            for attempt in range(max(0, retries) + 1):
                try:
                    records = collect_site_records(
                        site.url,
                        site.name,
                        pick=site.pick,
                        timeout=timeout,
                        target_period=period,
                    )
                    record, _ = select_current_record(records, period, site.pick)
                    break
                except Exception as exc:
                    message = str(exc)
                    boundary_or_missing = (
                        "绝对top边界" in message
                        or "绝对bottom边界" in message
                        or f"没有找到{period}期" in message
                        or f"不是指定{period}期" in message
                    )
                    if not boundary_or_missing or attempt >= max(0, retries):
                        raise
                    messages.append(f"  未找到{period}期，清缓存后刷新第{attempt + 1}次")
                    clear_fetch_cache(site.url)
                    time.sleep(min(8.0, 1.5 * (attempt + 1)))
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        return _site_failure(
            index,
            site,
            "抓取/解析",
            reason,
            [*messages, f"  失败: 抓取/解析失败({reason})"],
            f"抓取/解析失败({reason})",
            period=period,
        )

    if record is None:
        reason = f"没有找到{period}期数据"
        return _site_failure(
            index,
            site,
            "指定期数校验",
            reason,
            [*messages, f"  失败: {reason}"],
            period=period,
        )
    value = record.value()
    if record.period != period:
        reason = f"抓到非指定期号({record.period}期，不是{period}期)"
        return _site_failure(
            index,
            site,
            "指定期数校验",
            reason,
            [*messages, f"  失败: {reason}"],
            period=period,
        )
    if not is_valid_tail_record(record):
        reason = f"非0-9尾数据({value})"
        return _site_failure(
            index,
            site,
            "字段校验",
            reason,
            [*messages, f"  失败: {reason}"],
            period=period,
        )
    if record.same_period_record_count:
        messages.append(
            f"  专属区{period}期记录: 编号{record.same_period_record_index}/"
            f"{record.same_period_record_count}"
        )
    messages.append(f"  成功: {record.as_line()}")
    if record.source_snippet:
        messages.append(f"  命中片段: {record.source_snippet}")
    return CurrentRunResult(
        index=index,
        success_line=record.as_line(),
        fail_line=None,
        ranking_value=value,
        messages=messages,
    )


_run_current_site = crawl_current_site
