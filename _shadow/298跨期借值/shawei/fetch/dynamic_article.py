from __future__ import annotations

import json
import re
from urllib.parse import parse_qs, urlencode, urlparse

from shawei.domain.text import normalize_text
from shawei.fetch.decoding import _decode_b64, strip_html_tags


class DynamicArticleEmptyShellError(LookupError):
    """The target article identity is known, but its API body is empty."""


class DynamicArticleNotFoundError(LookupError):
    """Every configured API endpoint returned HTTP 404 for the target article."""


def dynamic_article_id(url: str) -> str:
    parsed = urlparse(url)
    match = re.search(r"/article/(?:admin|manager|lottery)/([^/?#]+)", parsed.path)
    return match.group(1) if match else ""


def is_dynamic_article_url(url: str) -> bool:
    return bool(dynamic_article_id(url))


def _is_article_payload(value) -> bool:
    return isinstance(value, dict) and any(
        key in value for key in ("authorNickname", "title", "html", "content", "formSections")
    )


ARTICLE_ID_KEYS = (
    "id",
    "articleId",
    "article_id",
    "recordId",
    "record_id",
    "topicId",
    "topic_id",
)


def _payload_id(value: dict) -> str:
    for key in ARTICLE_ID_KEYS:
        candidate = value.get(key)
        if candidate is not None and str(candidate).strip():
            return str(candidate).strip()
    return ""


def _find_article_payloads_by_id(value, target_id: str, path: str = "$") -> list[tuple[str, dict]]:
    matches: list[tuple[str, dict]] = []
    if isinstance(value, dict):
        if _payload_id(value) == target_id and _is_article_payload(value):
            matches.append((path, value))
        for key, child in value.items():
            matches.extend(_find_article_payloads_by_id(child, target_id, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            matches.extend(_find_article_payloads_by_id(child, target_id, f"{path}[{index}]"))
    return matches


def _validate_article_payload(article: dict, target_id: str, expected_author: str = "") -> None:
    if _payload_id(article) != target_id:
        raise LookupError(f"目标ID {target_id} 未匹配到唯一文章记录")
    author = article.get("authorNickname")
    title = article.get("title")
    body = article.get("html") or article.get("content")
    if not isinstance(author, str) or not author.strip():
        raise LookupError(f"目标ID {target_id} 作者字段缺失")
    if not isinstance(title, str) or not title.strip():
        raise LookupError(f"目标ID {target_id} 标题字段缺失")
    if not isinstance(body, str) or not body.strip():
        raise DynamicArticleEmptyShellError(f"目标ID {target_id} 正文字段缺失")
    if expected_author and normalize_text(author) != normalize_text(expected_author):
        raise LookupError(f"目标ID {target_id} 作者不匹配: {author}")


def _decode_article_payload_documents(article: dict) -> list[str]:
    docs: list[str] = []
    for key in ("authorNickname", "title", "html", "content"):
        _append_decoded_article_field(docs, article.get(key))
    for form in article.get("formSections") or []:
        if not isinstance(form, dict):
            continue
        for key in ("disclaimerHtml", "htmlCode"):
            _append_decoded_article_field(docs, form.get(key))
    if docs:
        docs.append("\n".join(docs))
    return docs


def admin_article_api_urls(url: str) -> list[str]:
    parsed = urlparse(url)
    match = re.search(r"/article/admin/([^/?#]+)", parsed.path)
    if not match:
        return []
    return [f"{parsed.scheme}://{parsed.netloc}/api/proxy/admin-articles/{match.group(1)}"]


def manager_article_api_urls(url: str) -> list[str]:
    parsed = urlparse(url)
    match = re.search(r"/article/(?:admin|manager|lottery)/([^/?#]+)", parsed.path)
    if not match:
        return []
    return [f"{parsed.scheme}://{parsed.netloc}/api/proxy/manager-articles/{match.group(1)}"]


def dynamic_article_api_urls(url: str) -> list[str]:
    return list(dict.fromkeys(admin_article_api_urls(url) + manager_article_api_urls(url)))


def is_admin_article_url(url: str) -> bool:
    return bool(re.search(r"/article/admin/[^/?#]+", urlparse(url).path))


def admin_article_landing_data_url(url: str) -> tuple[str, str] | None:
    parsed = urlparse(url)
    match = re.search(r"/article/admin/([^/?#]+)", parsed.path)
    if not match:
        return None
    site_url = (parse_qs(parsed.query).get("url") or [""])[0].strip()
    if not site_url:
        return None
    query = urlencode({"url": site_url})
    return match.group(1), f"{parsed.scheme}://{parsed.netloc}/api/proxy/landing-page-data?{query}"


def decode_admin_article_json(
    text: str,
    target_id: str | None = None,
    expected_author: str = "",
) -> list[str]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        if target_id:
            raise LookupError(f"目标ID {target_id} 接口响应不是有效JSON")
        return []
    if not target_id:
        raise LookupError("动态文章接口缺少目标ID，禁止扫描整个聚合响应")
    matches = _find_article_payloads_by_id(payload, str(target_id))
    if len(matches) != 1:
        raise LookupError(f"目标ID {target_id} 未匹配到唯一文章记录: {len(matches)} 条")
    _, article = matches[0]
    _validate_article_payload(article, str(target_id), expected_author)
    return _decode_article_payload_documents(article)


def _append_decoded_article_field(docs: list[str], value) -> None:
    if not isinstance(value, str) or not value:
        return
    decoded = _decode_b64(value) or value
    docs.append(decoded)
    stripped = strip_html_tags(decoded)
    if stripped and stripped != decoded:
        docs.append(stripped)


def decode_landing_page_admin_article_json(
    text: str,
    target_id: str,
    expected_author: str = "",
) -> list[str]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LookupError(f"目标ID {target_id} 接口响应不是有效JSON") from exc
    if not isinstance(payload, dict):
        raise LookupError(f"目标ID {target_id} 接口响应不是JSON对象")
    section_data = payload.get("sectionData")
    if not isinstance(section_data, dict):
        raise LookupError(f"目标ID {target_id} 栏目数据缺失")

    matches: list[tuple[str, dict]] = []
    for section_key, section in section_data.items():
        if not isinstance(section, dict):
            continue
        articles = section.get("adminArticles")
        if not isinstance(articles, list):
            continue
        for article in articles:
            if not isinstance(article, dict) or _payload_id(article) != target_id:
                continue
            matches.append((str(section_key), article))
    if len(matches) != 1:
        raise LookupError(f"目标ID {target_id} 匹配到 {len(matches)} 条")
    section_key, article = matches[0]
    article_section_id = article.get("sectionId")
    if article_section_id and str(article_section_id) != section_key:
        raise LookupError(f"目标ID {target_id} 栏目归属不一致")
    _validate_article_payload(article, target_id, expected_author)
    return _decode_article_payload_documents(article)
