from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import shawei_crawler as crawler


SCRIPT_DIR = Path(__file__).resolve().parent
SITES_PATH = SCRIPT_DIR / "sites.json"
CACHE_PATH = SCRIPT_DIR / "recent_10_cache.json"
REPORT_PATH = SCRIPT_DIR / "dynamic_article_id_audit_report.json"


def _record_id(value: dict) -> str:
    for key in crawler.ARTICLE_ID_KEYS:
        candidate = value.get(key)
        if candidate is not None and str(candidate).strip():
            return str(candidate).strip()
    return ""


def _payload_count(value, path: str = "$") -> tuple[int, list[str]]:
    count = 0
    paths: list[str] = []
    if isinstance(value, dict):
        if _record_id(value) and crawler._is_article_payload(value):
            count += 1
            paths.append(path)
        for key, child in value.items():
            child_count, child_paths = _payload_count(child, f"{path}.{key}")
            count += child_count
            paths.extend(child_paths)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_count, child_paths = _payload_count(child, f"{path}[{index}]")
            count += child_count
            paths.extend(child_paths)
    return count, paths


def _json_target_matches(text: str, target_id: str) -> tuple[int, list[str], str]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return 0, [], f"接口响应不是有效JSON: {type(exc).__name__}"
    matches = crawler._find_article_payloads_by_id(payload, target_id)
    return len(matches), [path for path, _ in matches], ""


def _target_id(url: str) -> tuple[str, str]:
    article_id = crawler.dynamic_article_id(url)
    if article_id:
        return article_id, "article-url"
    forum_id = crawler.spa_forum_target_id(url)
    if forum_id:
        return forum_id, "spa-forum-url"
    return "", "none"


def _controlled_profile_scope(site: dict) -> dict | None:
    """Return the stable URL scope for an explicitly configured profile feed."""
    url = str(site.get("url") or "")
    name = str(site.get("name") or "")
    try:
        rule = crawler.effective_rule_for(url, name)
    except Exception:
        return None
    if not rule.profile_parser:
        return None

    parsed = urlparse(url)
    query_user_id = (parse_qs(parsed.query).get("userId") or [""])[0].strip()
    fragment = parsed.fragment or ""
    fragment_match = re.search(r"(?:^|/)users/(\d+)(?:/|$)", fragment)
    user_id = query_user_id or (fragment_match.group(1) if fragment_match else "")
    if not user_id:
        return None
    return {
        "scope_id": user_id,
        "scope_source": "user-url",
        "profile_parser": rule.profile_parser,
        "scope_rule": "用户ID + 专属栏目 + 指定期数 + top/bottom + 内部文章ID",
    }


def _iter_json_dicts(value, path: str = "$"):
    if isinstance(value, dict):
        yield path, value
        for key, child in value.items():
            yield from _iter_json_dicts(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_json_dicts(child, f"{path}[{index}]")


def _profile_record_matches(text: str, site: dict, scope: dict) -> list[dict]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []

    name = str(site.get("name") or "")
    parser_name = str(scope.get("profile_parser") or "")
    expected_topic = getattr(crawler, "QVUU_TWO_TAIL_PROFILE_TOPICS", {}).get(parser_name)
    keyword = crawler._profile_topic_keyword(parser_name, name)
    matches: list[dict] = []
    seen_paths: set[str] = set()
    for path, item in _iter_json_dicts(payload):
        if path in seen_paths or not isinstance(item, dict):
            continue
        item_id = crawler._payload_id(item)
        if not item_id or crawler._profile_owner_id(item) != str(scope["scope_id"]):
            continue
        document = crawler._profile_item_document(item, name)
        if keyword and crawler.normalize_text(keyword) not in crawler.normalize_text(document):
            continue
        if expected_topic:
            topic = item.get("topic")
            if not isinstance(topic, str) or crawler.normalize_text(topic) != crawler.normalize_text(expected_topic):
                continue
        nickname = item.get("user", {}).get("nickname") if isinstance(item.get("user"), dict) else ""
        if nickname and crawler.normalize_text(str(nickname)) != crawler.normalize_text(name):
            continue
        body = item.get("content") or item.get("body")
        if not isinstance(body, str) or not body.strip():
            continue
        periods = sorted({int(value) for value in crawler.PERIOD_RE.findall(document)})
        matches.append({
            "id": item_id,
            "path": path,
            "period": crawler._profile_item_period(item),
            "periods_in_document": periods,
            "topic": str(item.get("topic") or item.get("sub_topic") or ""),
        })
        seen_paths.add(path)
    return matches


def _is_dynamic_scope(url: str) -> bool:
    parsed = urlparse(url)
    return bool(
        crawler.dynamic_article_id(url)
        or crawler.spa_forum_target_id(url)
        or crawler.user_release_api_urls(url)
        or re.search(r"(?:^|/)users/\d+/?$", parsed.fragment or "")
    )


def _load_cache() -> dict:
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"error": f"缓存读取失败: {type(exc).__name__}: {exc}", "sites": []}
    return payload if isinstance(payload, dict) else {"error": "缓存不是对象", "sites": []}


def _cache_entry(cache: dict, url: str) -> dict | None:
    for item in cache.get("sites", []):
        if isinstance(item, dict) and item.get("url") == url:
            return item
    return None


def _fetch_one(url: str, timeout: int) -> tuple[str, str]:
    try:
        return crawler.fetch_text(url, timeout), "成功"
    except Exception as exc:
        return "", f"{type(exc).__name__}: {exc}"


def _compare_cached_history(result: dict, site: dict, cache: dict, timeout: int) -> None:
    cached = _cache_entry(cache, result["url"])
    if not isinstance(cached, dict):
        return
    periods = cached.get("periods") or []
    values = cached.get("values") or []
    comparisons = []
    if not result["record_id"]:
        for period, cached_value in zip(periods, values):
            comparisons.append({
                "period": period,
                "cached_value": str(cached_value),
                "actual_value": None,
                "original_order": None,
                "original_position": None,
                "article_id": None,
                "comparison": "历史解析错误或源站内容变更待确认",
            })
        result["cache_comparison"] = comparisons
        result["needs_historical_cache_repair"] = True
        return

    result["historical_validation_mode"] = "每个缓存期独立调用正式target_period验证器"
    profile_matches = result.get("profile_record_matches") or []
    profile_ids_by_period: dict[str, set[str]] = {}
    for match in profile_matches:
        item_id = str(match.get("id") or "")
        period = match.get("period")
        if isinstance(period, int):
            profile_ids_by_period.setdefault(str(period), set()).add(item_id)

    def article_id_for_period(period: int) -> str | None:
        if result.get("record_id_source") != "profile-user-url":
            return result.get("record_id") or None
        ids = sorted(profile_ids_by_period.get(str(period), set()))
        if (
            not ids
            and result.get("profile_parser") == "qvuu_two_tail_user_forums"
        ):
            ids = sorted(profile_ids_by_period.get(str(period + 1), set()))
        if len(ids) == 1:
            return ids[0]
        if len(ids) > 1:
            return "多个: " + "、".join(ids)
        return None

    unique_profile_periods: list[int] = []
    for period, cached_value in zip(periods, values):
        try:
            target_period = int(period)
        except (TypeError, ValueError):
            result["needs_historical_cache_repair"] = True
            comparisons.append({
                "period": period,
                "cached_value": str(cached_value),
                "actual_value": None,
                "original_order": None,
                "original_position": None,
                "article_id": None,
                "comparison": "历史解析错误或源站内容变更待确认",
                "validation_error": "缓存期数不是整数",
            })
            continue

        validation_error = ""
        try:
            records = crawler.collect_site_records(
                result["url"],
                str(site.get("name") or ""),
            pick=crawler.canonical_pick(str(site.get("pick") or "top")),
                timeout=timeout,
                target_period=target_period,
            )
        except Exception as exc:
            records = []
            validation_error = f"{type(exc).__name__}: {exc}"

        validation_decision = None
        try:
            decision_key = (
                result["url"],
                crawler.normalize_text(str(site.get("name") or "")),
                crawler.canonical_pick(str(site.get("pick") or "top")),
                int(timeout),
                target_period,
            )
            validation_decision = crawler.VALIDATION_DECISION_CACHE.get(decision_key)
        except (AttributeError, TypeError, ValueError):
            validation_decision = None
        evidence_candidates = []
        if validation_decision is not None:
            evidence_candidates = [
                candidate
                for candidate in validation_decision.candidates
                if candidate.record.period == target_period
            ]
        ordered_evidence = sorted(
            evidence_candidates,
            key=lambda candidate: (
                candidate.document_order,
                candidate.original_position,
                candidate.parser_id,
                candidate.document_id,
            ),
        )
        original_order: list[int] = []
        for candidate in (
            sorted(
                getattr(validation_decision, "all_candidates", ())
                or validation_decision.candidates,
                key=lambda item: (
                    item.document_order,
                    item.original_position,
                    item.parser_id,
                    item.document_id,
                ),
            )
            if validation_decision is not None
            else []
        ):
            if candidate.record.period not in original_order:
                original_order.append(candidate.record.period)

        candidates = [record for record in records if record.period == target_period]
        actual_value = crawler.record_value(candidates[0]) if len(candidates) == 1 else None
        article_id = article_id_for_period(target_period)
        evidence_ids = sorted({candidate.record_id for candidate in ordered_evidence if candidate.record_id})
        if result.get("record_id_source") != "profile-user-url":
            if len(evidence_ids) == 1:
                article_id = evidence_ids[0]
            elif len(evidence_ids) > 1:
                article_id = "多个: " + "、".join(evidence_ids)
        position = (
            ordered_evidence[0].original_position + 1
            if len(ordered_evidence) == 1
            else None
        )
        if not candidates and not validation_error:
            validation_error = f"正式验证器没有返回{target_period}期唯一记录"
        if not candidates:
            comparison = "历史解析错误或源站内容变更待确认"
            result["needs_historical_cache_repair"] = True
            if result["classification"] == "正常":
                result["classification"] = "疑似错误"
        elif len(candidates) > 1:
            comparison = "数据存在冲突，停止写入"
            result["needs_historical_cache_repair"] = True
            result["classification"] = "已确认错误"
        elif result.get("record_id_source") == "profile-user-url" and article_id is None:
            comparison = "历史解析错误或源站内容变更待确认"
            result["needs_historical_cache_repair"] = True
            if result["classification"] == "正常":
                result["classification"] = "疑似错误"
        elif result.get("record_id_source") == "profile-user-url" and article_id.startswith("多个:"):
            comparison = "数据存在多个文章ID，停止写入"
            result["needs_historical_cache_repair"] = True
            result["classification"] = "已确认错误"
        elif str(actual_value) != str(cached_value):
            comparison = "疑似错误，需确认历史页面快照"
            result["needs_historical_cache_repair"] = True
            result["classification"] = "疑似错误"
        else:
            comparison = "当前源站结果一致；历史页面快照缺失，无法确认旧解析"
        if len(candidates) == 1 and article_id and not article_id.startswith("多个:"):
            unique_profile_periods.append(target_period)
        comparisons.append({
            "period": target_period,
            "cached_value": str(cached_value),
            "actual_value": actual_value,
            "original_order": original_order or None,
            "original_position": position,
            "original_positions": [candidate.original_position + 1 for candidate in ordered_evidence],
            "article_id": article_id,
            "candidate_evidence": [
                {
                    "parser_id": candidate.parser_id,
                    "source_url": candidate.source_url,
                    "source_type": candidate.source_type,
                    "record_id": candidate.record_id,
                    "document_id": candidate.document_id,
                    "document_order": candidate.document_order,
                    "original_position": candidate.original_position + 1,
                    "anchor": candidate.anchor,
                    "keyword": candidate.keyword,
                }
                for candidate in ordered_evidence
            ],
            "comparison": comparison,
            **({"validation_error": validation_error} if validation_error else {}),
        })
    result["cache_comparison"] = comparisons
    if result.get("record_id_source") == "profile-user-url":
        result["profile_exact_unique_periods"] = unique_profile_periods
        result["exact_unique_match"] = bool(unique_profile_periods)


def _audit_site(site: dict, cache: dict, timeout: int) -> dict:
    name = str(site.get("name") or "")
    url = str(site.get("url") or "")
    url_target_id, url_id_source = _target_id(url)
    profile_scope = _controlled_profile_scope(site)
    target_id = url_target_id or (str(profile_scope["scope_id"]) if profile_scope else "")
    id_source = url_id_source if url_target_id else ("profile-user-url" if profile_scope else "none")
    result = {
        "name": name,
        "url": url,
        "record_id": target_id,
        "record_id_source": id_source,
        "profile_controlled": bool(profile_scope),
        "profile_parser": profile_scope.get("profile_parser", "") if profile_scope else "",
        "profile_scope_rule": profile_scope.get("scope_rule", "") if profile_scope else "",
        "profile_record_matches": [],
        "profile_exact_unique_periods": [],
        "interface_article_count": 0,
        "interface_record_paths": [],
        "matched_record_paths": [],
        "exact_unique_match": False,
        "page_status": "",
        "api_statuses": [],
        "author_title_section_direction_field_check": "未完成",
        "title_body_same_record": False,
        "classification": "正常",
        "root_cause": "",
        "minimal_fix": "",
        "needs_historical_cache_repair": False,
        "cache_comparison": [],
    }
    if not target_id:
        result.update({
            "classification": "已确认错误",
            "root_cause": "页面是聚合列表，但URL没有唯一文章/记录ID，不能证明目标记录",
            "minimal_fix": "补充唯一详情记录ID或配置专属接口过滤条件；未补齐前禁止抓取",
            "author_title_section_direction_field_check": "未执行，ID边界缺失",
        })
    page, page_status = _fetch_one(url, timeout)
    result["page_status"] = page_status

    api_urls = []
    api_urls.extend(crawler.admin_article_api_urls(url))
    api_urls.extend(crawler.manager_article_api_urls(url))
    api_urls.extend(crawler.spa_user_forum_api_urls(url))
    api_urls.extend(crawler.user_release_api_urls(url))
    landing = crawler.admin_article_landing_data_url(url)
    if landing is not None:
        api_urls.append(landing[1])
    api_urls = list(dict.fromkeys(api_urls))
    for api_url in api_urls:
        api_text, api_status = _fetch_one(api_url, timeout)
        entry = {"url": api_url, "status": api_status, "article_count": 0, "record_paths": [], "target_matches": 0}
        if api_text:
            try:
                payload = json.loads(api_text)
                count, paths = _payload_count(payload)
                entry["article_count"] = count
                entry["record_paths"] = paths[:100]
                result["interface_article_count"] += count
            except json.JSONDecodeError as exc:
                entry["parse_error"] = f"接口响应不是有效JSON: {type(exc).__name__}"
            if profile_scope:
                profile_matches = _profile_record_matches(api_text, site, profile_scope)
                entry["target_matches"] = len(profile_matches)
                entry["target_paths"] = [item["path"] for item in profile_matches]
                result["profile_record_matches"].extend(
                    {**item, "api_url": api_url} for item in profile_matches
                )
            elif url_target_id:
                matches, paths, error = _json_target_matches(api_text, target_id)
                entry["target_matches"] = matches
                entry["target_paths"] = paths
                if error:
                    entry["target_error"] = error
                if matches == 1:
                    result["matched_record_paths"].extend(paths)
        result["api_statuses"].append(entry)

    result["interface_record_paths"] = [
        path
        for entry in result["api_statuses"]
        for path in entry.get("record_paths", [])
    ][:200]
    if profile_scope:
        if not result["profile_record_matches"]:
            result.update({
                "classification": "已确认错误",
                "root_cause": "受控用户聚合接口没有找到可校验的唯一内部文章记录",
                "minimal_fix": "保留用户ID边界，并补齐可访问的专属栏目接口或详情记录；禁止扫描全响应",
                "author_title_section_direction_field_check": "未通过，未找到内部文章记录",
                "exact_unique_match": False,
            })
        else:
            result.update({
                "exact_unique_match": False,
                "title_body_same_record": True,
                "author_title_section_direction_field_check": (
                    "用户ID边界后由专属profile按栏目、作者、标题/正文、方向、期数和内部文章ID校验"
                ),
            })
    elif url_target_id:
        matches = [
            entry.get("target_matches", 0)
            for entry in result["api_statuses"]
            if entry.get("target_matches") is not None
        ]
        result["exact_unique_match"] = any(value == 1 for value in matches) and not any(value > 1 for value in matches)
        result["title_body_same_record"] = result["exact_unique_match"]
        result["author_title_section_direction_field_check"] = (
            "ID唯一后由正式专属解析、作者、标题、正文、方向、期数和字段校验" if result["exact_unique_match"] else "未通过"
        )
        if not result["exact_unique_match"]:
            result.update({
                "classification": "已确认错误",
                "root_cause": "接口未按URL记录ID唯一匹配，或目标记录不可访问",
                "minimal_fix": "仅允许结构化JSON按URL记录ID唯一定位，再校验作者、标题、正文、栏目和业务字段",
                "needs_historical_cache_repair": True,
            })

    has_aggregate_risk = bool(profile_scope) or (
        not url_target_id
        or result["interface_article_count"] > 1
        or not result["exact_unique_match"]
    )
    if has_aggregate_risk:
        _compare_cached_history(result, site, cache, timeout)
    return result


def run(timeout: int = 8) -> dict:
    sites = json.loads(SITES_PATH.read_text(encoding="utf-8-sig"))
    cache = _load_cache()
    dynamic_sites = [site for site in sites if isinstance(site, dict) and _is_dynamic_scope(str(site.get("url") or ""))]
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(_audit_site, site, cache, timeout) for site in dynamic_sites]
        results = [future.result() for future in futures]
    return {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "audit_only": True,
        "formal_files_modified": False,
        "site_count": len(results),
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="动态详情接口ID只读审查，不修改正式文件")
    parser.add_argument("--timeout", type=int, default=8)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("timeout必须为正整数")
    payload = run(args.timeout)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"动态接口ID审查完成: {payload['site_count']} 个动态站点")
    print(f"报告: {args.output}")
    print("保护结论: recent_10_cache.json、成功TXT、失败TXT、sites.json和正式配置未修改")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
