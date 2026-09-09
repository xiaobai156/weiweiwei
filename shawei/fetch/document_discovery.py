from __future__ import annotations

import hashlib
import html
import re
from urllib.error import URLError
from urllib.parse import parse_qs, urljoin, urlparse

from shawei.config.constants import LIUXUAN_SITE_URL, SCRIPT_SRC_RE, STRICT_BOUNDARY_WINDOW
from shawei.domain.models import Document
from shawei.domain.text import is_bottom_pick, normalize_text
from shawei.fetch.browser import render_browser_documents
from shawei.fetch.decoding import (
    collect_decoded_documents,
    decode_document_writeln_html,
    decode_embedded_base64_blocks,
    decode_strdecode_blocks,
    strip_html_tags,
)
from shawei.fetch.dynamic_article import (
    DynamicArticleEmptyShellError,
    DynamicArticleNotFoundError,
    admin_article_api_urls,
    admin_article_landing_data_url,
    decode_admin_article_json,
    decode_landing_page_admin_article_json,
    dynamic_article_id,
    is_admin_article_url,
    is_dynamic_article_url,
    manager_article_api_urls,
)
from shawei.fetch.http_client import (
    FETCH_CACHE_LOCK,
    FETCH_CHILDREN,
    _is_http_404_error,
    fetch_text,
)
from shawei.fetch.profile import (
    collect_profile_feed_documents,
    decode_forum_detail_json,
    forum_detail_api_urls,
    is_dynamic_scoped_url,
    spa_forum_target_id,
    spa_user_forum_api_urls,
    user_release_api_urls,
)


def collect_followed_link_documents(
    page_url: str,
    page: str,
    keywords: tuple[str, ...],
    timeout: int,
    render_target: bool = False,
    pick: str = "top",
    paginate: bool = False,
) -> list[str]:
    if not keywords:
        return []
    anchor_pattern = re.compile(r"<a\b[^>]*\bhref\s*=\s*([\"'])(.*?)\1[^>]*>.*?</a>", re.I | re.S)

    def matching_links(current_page: str) -> list[str]:
        return [
            html.unescape(match.group(2))
            for match in anchor_pattern.finditer(current_page)
            if all(
                keyword in normalize_text(strip_html_tags(match.group(0)))
                for keyword in keywords
            )
        ]

    def next_page_url(current_url: str, current_page: str, visited: set[str]) -> str | None:
        current = urlparse(current_url)
        for match in anchor_pattern.finditer(current_page):
            label = normalize_text(strip_html_tags(match.group(0)))
            if "下一页" not in label:
                continue
            candidate = urljoin(current_url, html.unescape(match.group(2)))
            parsed = urlparse(candidate)
            if (parsed.scheme, parsed.netloc, parsed.path) != (
                current.scheme,
                current.netloc,
                current.path,
            ):
                continue
            current_id = (parse_qs(current.query).get("id") or [""])[0]
            candidate_id = (parse_qs(parsed.query).get("id") or [""])[0]
            if current_id and candidate_id != current_id:
                continue
            if candidate in visited:
                continue
            return candidate
        return None

    current_url = page_url
    current_page = page
    visited = {page_url}
    max_pages = 10 if paginate else 1
    for _ in range(max_pages):
        matches = matching_links(current_page)
        if matches:
            href = matches[-1] if is_bottom_pick(pick) else matches[0]
            target_url = urljoin(current_url, href)
            target = fetch_text(target_url, timeout)
            with FETCH_CACHE_LOCK:
                FETCH_CHILDREN.setdefault(page_url, set()).add(target_url)
            documents = [target]
            documents.extend(
                collect_decoded_documents(
                    decode_strdecode_blocks(target)
                    + decode_embedded_base64_blocks(target)
                )
            )
            if render_target:
                documents.extend(render_browser_documents(target_url, timeout))
            return documents
        if not paginate:
            break
        next_url = next_page_url(current_url, current_page, visited)
        if next_url is None:
            break
        current_page = fetch_text(next_url, timeout)
        current_url = next_url
        visited.add(next_url)
    return []


def collect_liuxuan_documents(url: str, timeout: int) -> list[str]:
    def fetch_liuxuan_text(target_url: str) -> str:
        for attempt in range(2):
            try:
                return fetch_text(target_url, timeout)
            except (ConnectionError, TimeoutError, URLError):
                if attempt == 1:
                    raise
        raise AssertionError("六玄网传输重试未返回")

    page = fetch_liuxuan_text(url)
    loader_urls = [
        urljoin(url, match.group(2))
        for match in SCRIPT_SRC_RE.finditer(page)
        if match.group(2).lstrip("/") == "yjjy/wenzhang.js"
    ]
    if len(loader_urls) != 1:
        raise LookupError(f"六玄网入口脚本未唯一匹配: {len(loader_urls)} 条")

    loader_url = loader_urls[0]
    loader = fetch_liuxuan_text(loader_url)
    loader_html = decode_document_writeln_html(loader)
    iframe_matches = re.findall(
        r"<iframe\b[^>]*\bsrc\s*=\s*['\"]([^'\"]+)['\"]",
        loader_html,
        flags=re.I,
    )
    if len(iframe_matches) != 1:
        raise LookupError(f"六玄网正文iframe未唯一匹配: {len(iframe_matches)} 条")
    detail_url = urljoin(url, iframe_matches[0])
    root = urlparse(url)
    detail = urlparse(detail_url)
    if (detail.scheme, detail.netloc) != (root.scheme, root.netloc):
        raise LookupError("六玄网正文iframe越出原始站点边界")

    detail_page = fetch_liuxuan_text(detail_url)
    if "六玄网论坛" not in normalize_text(detail_page):
        raise LookupError("六玄网正文页标题锚点不匹配")
    zhjs_match = re.search(
        r"<div\b[^>]*\bid\s*=\s*['\"]zhjs['\"][^>]*>\s*"
        r"<script\b[^>]*\bsrc\s*=\s*(['\"])(.*?)\1",
        detail_page,
        flags=re.I | re.S,
    )
    if zhjs_match is None:
        raise LookupError("六玄网综合绝杀脚本未找到")
    zhjs_url = urljoin(detail_url, zhjs_match.group(2))
    if (urlparse(zhjs_url).scheme, urlparse(zhjs_url).netloc) != (root.scheme, root.netloc):
        raise LookupError("六玄网综合绝杀脚本越出原始站点边界")

    zhjs_script = fetch_liuxuan_text(zhjs_url)
    zhjs_html = decode_document_writeln_html(zhjs_script)
    normalized = normalize_text(re.sub(r"<[^>]+>", " ", zhjs_html))
    compact = normalized.replace(" ", "")
    required_anchors = ("澳彩六玄网[综合绝杀]", "澳彩最准开奖:87127.com")
    if not all(anchor in compact for anchor in required_anchors):
        raise LookupError("六玄网综合绝杀结构锚点不完整")
    return [page, loader, detail_page, zhjs_script, zhjs_html]


def collect_documents(
    url: str,
    timeout: int = 20,
    follow_link_keywords: tuple[str, ...] = (),
    follow_link_rendered: bool = False,
    follow_link_only: bool = False,
    follow_link_pick: str = "top",
    site_name: str = "",
    target_period: int | None = None,
    profile_parser: str = "",
    profile_boundary_window: int = STRICT_BOUNDARY_WINDOW,
    same_period_record_selection: bool = False,
    follow_link_pagination: bool = False,
) -> list[str]:
    docs: list[str] = []
    if url == LIUXUAN_SITE_URL:
        return collect_liuxuan_documents(url, timeout)
    if profile_parser:
        return collect_profile_feed_documents(
            url,
            site_name,
            follow_link_pick,
            target_period if target_period is not None else 0,
            timeout,
            profile_parser,
            profile_boundary_window,
            same_period_record_selection,
        )
    page = ""
    page_error: Exception | None = None
    is_admin = is_admin_article_url(url)
    is_dynamic_scoped = is_dynamic_scoped_url(url)
    article_id = dynamic_article_id(url)
    spa_target_id = spa_forum_target_id(url)
    empty_shell_error: DynamicArticleEmptyShellError | None = None
    dynamic_api_count = 0
    dynamic_api_404_count = 0

    if is_admin:
        for api_url in admin_article_api_urls(url):
            dynamic_api_count += 1
            try:
                api_text = fetch_text(api_url, timeout)
            except Exception as exc:
                if not _is_http_404_error(exc):
                    raise
                dynamic_api_404_count += 1
                continue
            try:
                docs.extend(decode_admin_article_json(api_text, article_id, site_name))
            except DynamicArticleEmptyShellError as exc:
                empty_shell_error = exc

        admin_landing = admin_article_landing_data_url(url)
        if admin_landing is not None:
            article_id, api_url = admin_landing
            dynamic_api_count += 1
            try:
                api_text = fetch_text(api_url, timeout)
            except Exception as exc:
                if not _is_http_404_error(exc):
                    raise
                dynamic_api_404_count += 1
                api_text = ""
            if api_text:
                docs.extend(decode_landing_page_admin_article_json(api_text, article_id, site_name))

    for api_url in manager_article_api_urls(url):
        dynamic_api_count += 1
        try:
            api_text = fetch_text(api_url, timeout)
        except Exception as exc:
            if not _is_http_404_error(exc):
                raise
            dynamic_api_404_count += 1
            continue
        try:
            docs.extend(decode_admin_article_json(api_text, article_id, site_name))
        except DynamicArticleEmptyShellError as exc:
            empty_shell_error = empty_shell_error or exc

    if is_dynamic_article_url(url):
        if not docs and empty_shell_error is not None:
            raise empty_shell_error
        if not docs and dynamic_api_count and dynamic_api_404_count == dynamic_api_count:
            raise DynamicArticleNotFoundError(f"目标ID {article_id} 的全部专属接口均返回404")
        return docs

    try:
        page = fetch_text(url, timeout)
        if not is_dynamic_scoped:
            docs.append(page)
    except Exception as exc:
        page_error = exc

    for api_url in user_release_api_urls(url):
        raise LookupError(
            "用户发布聚合接口没有唯一文章ID，禁止按第一篇、期数或作者决定目标记录"
        )

    for api_url in spa_user_forum_api_urls(url):
        try:
            api_text = fetch_text(api_url, timeout)
        except Exception:
            continue
        if spa_target_id and "/discuss/detail" in api_url:
            docs.extend(decode_forum_detail_json(api_text, spa_target_id, site_name))
        elif not spa_target_id:
            raise LookupError("用户论坛聚合接口没有唯一记录ID，禁止全响应解析")

    if not is_admin:
        for api_url in admin_article_api_urls(url):
            try:
                api_text = fetch_text(api_url, timeout)
            except Exception:
                continue
            docs.extend(decode_admin_article_json(api_text, dynamic_article_id(url), site_name))

    if page_error is not None and not docs:
        raise page_error
    if not page:
        return docs
    if is_dynamic_scoped:
        return docs

    followed_documents = collect_followed_link_documents(
        url,
        page,
        follow_link_keywords,
        timeout,
        render_target=follow_link_rendered,
        pick=follow_link_pick,
        paginate=follow_link_pagination,
    )
    if follow_link_only:
        return followed_documents
    docs.extend(followed_documents)

    docs.extend(collect_decoded_documents(decode_strdecode_blocks(page) + decode_embedded_base64_blocks(page)))

    if not is_dynamic_scoped:
        for match in SCRIPT_SRC_RE.finditer(page):
            script_url = urljoin(url, match.group(2))
            if "/upload/script/" not in script_url and "view_content.php" not in script_url:
                continue
            try:
                script = fetch_text(script_url, timeout)
            except Exception:
                continue
            with FETCH_CACHE_LOCK:
                FETCH_CHILDREN.setdefault(url, set()).add(script_url)
            docs.append(script)
            docs.extend(collect_decoded_documents(decode_strdecode_blocks(script) + decode_embedded_base64_blocks(script)))

    for api_url in forum_detail_api_urls(url):
        try:
            api_text = fetch_text(api_url, timeout)
        except Exception:
            continue
        detail_id = (parse_qs(urlparse(url).query).get("id") or [""])[0]
        docs.extend(decode_forum_detail_json(api_text, detail_id, site_name))

    return docs


def build_documents(
    url: str,
    contents: list[str],
    source_type: str = "page",
    record_id: str = "",
) -> list[Document]:
    stable_record_id = record_id or dynamic_article_id(url) or spa_forum_target_id(url)
    return [
        Document(
            source_url=url,
            content=content,
            source_type=source_type,
            record_id=stable_record_id,
            order=index,
            document_id=hashlib.sha256(
                content.encode("utf-8", errors="replace")
            ).hexdigest(),
        )
        for index, content in enumerate(contents)
    ]
