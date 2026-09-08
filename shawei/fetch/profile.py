from __future__ import annotations

import json
import re
from urllib.parse import parse_qs, urlencode, urlparse

from shawei.config.constants import (
    FORUM_API_BASES,
    PERIOD_CHUNK_RE,
    PERIOD_RE,
    QVUU_TWO_TAIL_PATTERNS,
    QVUU_TWO_TAIL_PROFILE_TOPICS,
    TWO_TAIL_SITE_PARSERS,
)
from shawei.domain.text import is_bottom_pick, normalize_text
from shawei.domain.defaults import DIRECTION_BOUNDARY_WINDOW
from shawei.fetch.dynamic_article import _payload_id, dynamic_article_id
from shawei.fetch.http_client import fetch_text


def forum_detail_api_urls(url: str) -> list[str]:
    parsed = urlparse(url)
    if "/forum/details" not in parsed.path:
        return []
    detail_id = (parse_qs(parsed.query).get("id") or [""])[0]
    if not detail_id:
        return []
    query = urlencode({"id": detail_id})
    return [f"{base}/api/v1/discuss/detail?{query}" for base in FORUM_API_BASES]


def user_release_api_urls(url: str) -> list[str]:
    parsed = urlparse(url)
    if parsed.path.strip("/") != "user":
        return []
    user_id = (parse_qs(parsed.query).get("userId") or [""])[0]
    if not user_id:
        return []
    urls: list[str] = []
    bases = ("https://api.118tapi1.com:8443", "https://tk.118tapi3.com:8443", "https://api.118tapi2.com:8443")
    for base in bases:
        for keyword in ("", "绝杀一尾"):
            query = urlencode(
                {
                    "lotteryType": 2,
                    "id": user_id,
                    "type": 1,
                    "page": 1,
                    "keyword": keyword,
                }
            )
            urls.append(f"{base}/api/v1/user/release?{query}")
    return urls


def _profile_owner_id(item: dict) -> str:
    owner = item.get("user_id")
    if owner is None:
        user = item.get("user")
        if isinstance(user, dict):
            owner = user.get("id")
    return str(owner).strip() if owner is not None else ""


def _profile_item_period(item: dict) -> int | None:
    draw = item.get("draw")
    if isinstance(draw, int):
        return draw
    if isinstance(draw, str) and draw.strip().isdigit():
        return int(draw.strip())
    title = item.get("title")
    match = PERIOD_RE.search(title if isinstance(title, str) else "")
    return int(match.group(1)) if match else None


def _profile_item_document(item: dict, site_name: str) -> str:
    user = item.get("user")
    nickname = user.get("nickname") if isinstance(user, dict) else ""
    fields = [
        nickname,
        item.get("topic"),
        item.get("sub_topic"),
        item.get("title"),
        item.get("content") or item.get("body"),
    ]
    values = [str(value) for value in fields if isinstance(value, str) and value.strip()]
    if site_name not in values:
        values.insert(0, site_name)
    return "\n".join(values)


def _profile_topic_keyword(parser_name: str, site_name: str) -> str:
    if parser_name == "zcphjs_user_forums":
        return {"独特招牌": "精杀一尾", "朱红豆浆": "绝杀1尾"}.get(site_name, "绝杀一尾")
    if parser_name in QVUU_TWO_TAIL_PROFILE_TOPICS:
        return "二尾"
    return "绝杀一尾"


def _qvuu_two_tail_target_values(
    document: str, parser_name: str, target_period: int
) -> tuple[int, int]:
    pattern = QVUU_TWO_TAIL_PATTERNS.get(parser_name)
    if pattern is None:
        raise LookupError(f"未知Qvuu二尾格式解析器: {parser_name}")
    text = normalize_text(re.sub(r"<[^>]+>", " ", document))
    for chunk in (part.strip() for part in PERIOD_CHUNK_RE.split(text) if part.strip()):
        period_match = PERIOD_RE.match(chunk)
        if period_match is None or int(period_match.group(1)) != target_period:
            continue
        match = pattern.search(chunk)
        if match is None:
            raise LookupError(f"目标文章没有找到{target_period}期有效二尾数据")
        return int(match.group(1)), int(match.group(2))
    raise LookupError(f"目标文章没有找到{target_period}期有效二尾数据")


def _decode_qvuu_two_tail_profile_feed_json(
    items: list[object],
    site_name: str,
    user_id: str,
    target_period: int,
    pick: str,
    boundary_window: int,
    parser_name: str,
) -> list[tuple[str, str]]:
    expected_topic = QVUU_TWO_TAIL_PROFILE_TOPICS.get(parser_name)
    if expected_topic is None:
        raise LookupError(f"未知Qvuu二尾用户栏目解析器: {parser_name}")
    if is_bottom_pick(pick):
        raise LookupError("Qvuu二尾用户专属解析只允许top/顶部方向")

    owned_items: list[dict] = []
    seen_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or _profile_owner_id(item) != str(user_id):
            continue
        item_id = _payload_id(item)
        if not item_id:
            continue
        if item_id in seen_ids:
            raise LookupError(f"Qvuu二尾接口存在重复文章ID: {item_id}")
        seen_ids.add(item_id)
        user = item.get("user")
        nickname = user.get("nickname") if isinstance(user, dict) else ""
        if not isinstance(nickname, str) or normalize_text(nickname) != normalize_text(site_name):
            continue
        topic = item.get("topic")
        if not isinstance(topic, str) or normalize_text(topic) != normalize_text(expected_topic):
            continue
        content = item.get("content") or item.get("body")
        if not isinstance(content, str) or not content.strip():
            continue
        owned_items.append(item)

    if not owned_items:
        raise LookupError(f"Qvuu二尾接口没有找到作者{site_name}的目标栏目")

    window = DIRECTION_BOUNDARY_WINDOW
    boundary_items = owned_items[:window]
    if target_period <= 0:
        return [
            (_payload_id(item), _profile_item_document(item, site_name))
            for item in boundary_items
        ]

    def select_article(candidates: list[dict]) -> tuple[str, str]:
        if len(candidates) != 1:
            ids = "、".join(_payload_id(item) for item in candidates)
            raise LookupError(f"{target_period}期匹配到多个目标文章ID: {ids}")
        item = candidates[0]
        document = _profile_item_document(item, site_name)
        _qvuu_two_tail_target_values(document, parser_name, target_period)
        return _payload_id(item), document

    boundary_item = owned_items[0]
    boundary_period = _profile_item_period(boundary_item)
    if boundary_period != target_period:
        raise LookupError(
            f"绝对top边界是{boundary_period if boundary_period is not None else '未知'}期，"
            f"不是指定{target_period}期"
        )
    return [select_article([boundary_item])]


def decode_profile_feed_json(
    text: str,
    parser_name: str,
    site_name: str,
    user_id: str,
    target_period: int,
    pick: str,
    boundary_window: int = DIRECTION_BOUNDARY_WINDOW,
    same_period_record_selection: bool = False,
) -> list[tuple[str, str]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LookupError(f"用户聚合接口不是有效JSON: {exc}") from exc
    if parser_name == "118_user_release":
        data = payload.get("data") if isinstance(payload, dict) else None
        items = data.get("list") if isinstance(data, dict) else None
    else:
        items = payload if isinstance(payload, list) else None
    if not isinstance(items, list):
        raise LookupError("用户聚合接口缺少结构化记录列表")

    if parser_name == "qvuu_two_tail_user_forums":
        return _decode_qvuu_two_tail_profile_feed_json(
            items,
            site_name,
            user_id,
            target_period,
            pick,
            boundary_window,
            TWO_TAIL_SITE_PARSERS.get(site_name, ""),
        )

    keyword = _profile_topic_keyword(parser_name, site_name)
    owned_items: list[dict] = []
    seen_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or _profile_owner_id(item) != str(user_id):
            continue
        item_id = _payload_id(item)
        if not item_id:
            continue
        if item_id in seen_ids:
            raise LookupError(f"用户聚合接口存在重复记录ID: {item_id}")
        seen_ids.add(item_id)
        document = _profile_item_document(item, site_name)
        if keyword not in document:
            continue
        nickname = item.get("user", {}).get("nickname") if isinstance(item.get("user"), dict) else ""
        if nickname and normalize_text(nickname) != normalize_text(site_name):
            continue
        if not isinstance(item.get("content") or item.get("body"), str):
            continue
        owned_items.append(item)

    target_items = [item for item in owned_items if _profile_item_period(item) == target_period]
    if not target_items:
        raise LookupError(f"用户聚合接口没有找到{target_period}期目标记录")
    boundary_item = owned_items[-1] if is_bottom_pick(pick) else owned_items[0]
    selected_item = target_items[-1] if is_bottom_pick(pick) else target_items[0]
    if _payload_id(selected_item) != _payload_id(boundary_item):
        boundary_period = _profile_item_period(boundary_item)
        direction = "bottom" if is_bottom_pick(pick) else "top"
        raise LookupError(
            f"绝对{direction}边界是"
            f"{boundary_period if boundary_period is not None else '未知'}期，"
            f"不是指定{target_period}期"
        )
    if same_period_record_selection:
        return [
            (_payload_id(item), _profile_item_document(item, site_name))
            for item in target_items
        ]
    if len(target_items) != 1:
        ids = "、".join(_payload_id(item) for item in target_items)
        raise LookupError(f"{target_period}期存在多个目标记录ID: {ids}")
    item = target_items[0]
    return [(_payload_id(item), _profile_item_document(item, site_name))]


def decode_qvuu_history_json(
    text: str,
    user_id: str,
    target_period: int,
    sub_topic: str,
    pick: str,
    boundary_window: int = DIRECTION_BOUNDARY_WINDOW,
    same_period_record_selection: bool = False,
) -> list[str]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LookupError(f"Qvuu历史接口不是有效JSON: {exc}") from exc
    if not isinstance(payload, list):
        raise LookupError("Qvuu历史接口缺少记录列表")
    expected = normalize_text(sub_topic)
    items = [
        item
        for item in payload
        if isinstance(item, dict)
        and str(item.get("user_id") or "") == str(user_id)
        and normalize_text(str(item.get("sub_topic") or "")) == expected
        and _profile_item_period(item) is not None
    ]
    target_items = [item for item in items if _profile_item_period(item) == target_period]
    if not target_items:
        raise LookupError(f"Qvuu历史接口没有找到{target_period}期栏目记录")
    boundary_item = items[-1] if is_bottom_pick(pick) else items[0]
    selected_item = target_items[-1] if is_bottom_pick(pick) else target_items[0]
    if _payload_id(selected_item) != _payload_id(boundary_item):
        boundary_period = _profile_item_period(boundary_item)
        direction = "bottom" if is_bottom_pick(pick) else "top"
        raise LookupError(
            f"绝对{direction}边界是"
            f"{boundary_period if boundary_period is not None else '未知'}期，"
            f"不是指定{target_period}期"
        )
    if same_period_record_selection:
        return [_payload_id(item) for item in target_items if _payload_id(item)]
    if len(target_items) != 1:
        ids = "、".join(str(item.get("id")) for item in target_items)
        raise LookupError(f"{target_period}期存在多个目标记录ID: {ids}")
    item_id = _payload_id(target_items[0])
    if not item_id:
        raise LookupError(f"{target_period}期目标记录缺少ID")
    return [item_id]


def _qvuu_detail_document(
    text: str,
    target_id: str,
    user_id: str,
    sub_topic: str,
    site_name: str,
) -> str:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LookupError(f"Qvuu目标记录接口不是有效JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise LookupError(f"Qvuu目标记录 {target_id} 不是对象")
    if str(payload.get("id") or "") != str(target_id):
        raise LookupError(f"Qvuu目标记录ID不匹配: {target_id}")
    if str(payload.get("user_id") or "") != str(user_id):
        raise LookupError(f"Qvuu目标记录 {target_id} 作者ID不匹配")
    actual_topic = normalize_text(str(payload.get("sub_topic") or ""))
    if actual_topic != normalize_text(sub_topic):
        raise LookupError(f"Qvuu目标记录 {target_id} 栏目不匹配: {actual_topic}")
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise LookupError(f"Qvuu目标记录 {target_id} 正文缺失")
    return "\n".join((site_name, str(payload.get("topic") or ""), str(payload.get("sub_topic") or ""), content))


def collect_profile_feed_documents(
    url: str,
    site_name: str,
    pick: str,
    target_period: int,
    timeout: int,
    parser_name: str,
    boundary_window: int,
    same_period_record_selection: bool = False,
) -> list[str]:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    documents: list[str] = []
    if parser_name in {
        "118_user_release",
        "spa_user_forums",
        "zcphjs_user_forums",
        "qvuu_two_tail_user_forums",
    }:
        if parser_name == "118_user_release":
            user_id = (parse_qs(parsed.query).get("userId") or [""])[0]
            api_urls = user_release_api_urls(url)
        else:
            match = re.search(r"(?:^|/)users/(\d+)(?:\b|/)", parsed.fragment or "")
            user_id = match.group(1) if match else ""
            api_urls = [f"{origin}/api/v1/users/{user_id}/forums?per_page=20"] if user_id else []
        if not user_id or not api_urls:
            raise LookupError("用户聚合页缺少用户ID或接口地址")
        selected: dict[str, str] = {}
        errors: list[str] = []
        for api_url in dict.fromkeys(api_urls):
            try:
                decoded_items = decode_profile_feed_json(
                    fetch_text(api_url, timeout),
                    parser_name,
                    site_name,
                    user_id,
                    target_period,
                    pick,
                    boundary_window,
                    same_period_record_selection,
                )
            except Exception as exc:
                errors.append(f"{api_url}: {type(exc).__name__}: {exc}")
                continue
            for item_id, document in decoded_items:
                previous = selected.get(item_id)
                if previous is not None and previous != document:
                    raise LookupError(
                        f"{target_period}期同一目标文章ID {item_id} 在多个接口返回不同正文"
                    )
                selected[item_id] = document
        if not selected:
            raise LookupError(errors[0] if errors else "用户聚合接口没有返回目标记录")
        if parser_name == "qvuu_two_tail_user_forums" and target_period <= 0:
            return list(selected.values())
        if same_period_record_selection:
            return list(selected.values())
        if len(selected) != 1:
            raise LookupError(f"{target_period}期多个接口返回不同目标记录ID: {'、'.join(selected)}")
        return list(selected.values())

    if parser_name == "qvuu_reference_history":
        match = re.search(r"(?:^|/)users/(\d+)/references/(\d+)(?:\b|/)", parsed.fragment or "")
        if not match:
            raise LookupError("Qvuu引用页缺少用户ID或引用ID")
        user_id, _reference_id = match.groups()
        history_url = f"{origin}/api/v1/users/{user_id}/references/history"
        ids = decode_qvuu_history_json(
            fetch_text(history_url, timeout),
            user_id,
            target_period,
            "绝杀一尾",
            pick,
            boundary_window,
            same_period_record_selection,
        )
        for item_id in ids:
            detail_url = f"{origin}/api/v1/forums/{item_id}"
            documents.append(
                _qvuu_detail_document(
                    fetch_text(detail_url, timeout), item_id, user_id, "绝杀一尾", site_name
                )
            )
        return documents

    if parser_name == "qvuu_author_reference_history":
        route_id = spa_forum_target_id(url)
        if not route_id:
            raise LookupError("Qvuu论坛页缺少原始记录ID")
        route = json.loads(fetch_text(f"{origin}/api/v1/forums/{route_id}", timeout))
        if not isinstance(route, dict) or str(route.get("id") or "") != route_id:
            raise LookupError(f"Qvuu原始记录ID {route_id} 不匹配")
        author_id = str(route.get("user_id") or "")
        sub_topic = str(route.get("sub_topic") or "")
        if not author_id or "曾氏每期绝杀一尾" not in sub_topic:
            raise LookupError("Qvuu原始记录作者或栏目不匹配")
        history_url = f"{origin}/api/v1/users/{author_id}/references/history"
        ids = decode_qvuu_history_json(
            fetch_text(history_url, timeout),
            author_id,
            target_period,
            sub_topic,
            pick,
            boundary_window,
            same_period_record_selection,
        )
        for item_id in ids:
            documents.append(
                _qvuu_detail_document(
                    fetch_text(f"{origin}/api/v1/forums/{item_id}", timeout),
                    item_id,
                    author_id,
                    sub_topic,
                    site_name,
                )
            )
        return documents

    raise LookupError(f"未知用户聚合专属解析器: {parser_name}")


def spa_user_forum_api_urls(url: str) -> list[str]:
    parsed = urlparse(url)
    fragment = parsed.fragment or ""
    forum_match = re.search(r"(?:^|/)forums/(\d+)(?:\b|/)", fragment)
    if forum_match:
        base = f"{parsed.scheme}://{parsed.netloc}"
        return [f"{base}/api/v1/discuss/detail?{urlencode({'id': forum_match.group(1)})}"]
    reference_match = re.search(r"(?:^|/)users/(\d+)/references/(\d+)(?:\b|/)", fragment)
    if reference_match:
        base = f"{parsed.scheme}://{parsed.netloc}"
        user_id, forum_id = reference_match.groups()
        return [
            f"{base}/api/v1/users/{user_id}/forums?{urlencode({'per_page': 20})}",
            f"{base}/api/v1/discuss/detail?{urlencode({'id': forum_id})}",
        ]
    match = re.search(r"(?:^|/)users/(\d+)(?:\b|/)", fragment)
    if not match:
        return []
    base = f"{parsed.scheme}://{parsed.netloc}"
    query = urlencode({"per_page": 20})
    return [f"{base}/api/v1/users/{match.group(1)}/forums?{query}"]


def spa_forum_target_id(url: str) -> str:
    fragment = urlparse(url).fragment or ""
    match = re.search(r"(?:^|/)forums/(\d+)(?:\b|/)", fragment)
    if match:
        return match.group(1)
    match = re.search(r"(?:^|/)users/\d+/references/(\d+)(?:\b|/)", fragment)
    return match.group(1) if match else ""


def dynamic_scope_target_id(url: str) -> str:
    return dynamic_article_id(url) or spa_forum_target_id(url)


def is_dynamic_scoped_url(url: str) -> bool:
    return bool(dynamic_scope_target_id(url))


def _is_unscoped_dynamic_aggregate_url(url: str) -> bool:
    parsed = urlparse(url)
    if user_release_api_urls(url):
        return True
    fragment = parsed.fragment or ""
    return bool(re.search(r"(?:^|/)users/\d+/?$", fragment))


def decode_forum_detail_json(
    text: str,
    target_id: str | None = None,
    expected_author: str = "",
) -> list[str]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    if not target_id:
        raise LookupError("论坛接口缺少目标ID，禁止扫描整个聚合响应")
    if str(data.get("id") or "") != str(target_id):
        raise LookupError(f"论坛目标ID {target_id} 未匹配")
    title = data.get("title")
    content = data.get("content")
    if not isinstance(title, str) or not title.strip():
        raise LookupError(f"论坛目标ID {target_id} 标题字段缺失")
    if not isinstance(content, str) or not content.strip():
        raise LookupError(f"论坛目标ID {target_id} 正文字段缺失")
    author = data.get("authorNickname") or data.get("author")
    user = data.get("user")
    if not author and isinstance(user, dict):
        author = user.get("nickname") or user.get("name")
    if expected_author and (not isinstance(author, str) or normalize_text(author) != normalize_text(expected_author)):
        raise LookupError(f"论坛目标ID {target_id} 作者不匹配: {author or '缺失'}")
    docs = [title, content]
    if docs:
        docs.append("\n".join(docs))
    return docs
