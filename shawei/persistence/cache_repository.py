from __future__ import annotations

import datetime
import hashlib
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import asdict, is_dataclass
from pathlib import Path

from shawei.config.constants import TWO_TAIL_SITE_URLS
from shawei.config.rules import effective_rule_for
from shawei.domain.models import CurrentRunResult
from shawei.domain.text import canonical_pick
from shawei.persistence.atomic_file import _atomic_write_text_unlocked, file_lock


def is_valid_result_value(value: str, url: str = "") -> bool:
    pattern = r"\d、\d" if url.strip() in TWO_TAIL_SITE_URLS else r"\d"
    return re.fullmatch(pattern, value or "") is not None


def configuration_fingerprint(sites: Sequence[object]) -> str:
    entries: list[dict[str, object]] = []
    for site in sites:
        name = str(getattr(site, "name", "")).strip()
        url = str(getattr(site, "url", "")).strip()
        pick = canonical_pick(str(getattr(site, "pick", "top")))
        if not name or not url:
            raise ValueError("配置站点缺少 name/url，无法生成缓存配置指纹")
        rule = effective_rule_for(url, name)
        if not is_dataclass(rule):
            raise TypeError("effective parsing rule 必须是 dataclass")
        entries.append(
            {
                "name": name,
                "url": url,
                "pick": pick,
                "effective_rule": asdict(rule),
            }
        )
    canonical = json.dumps(
        entries,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _cache_identity(name: object, url: object, pick: object = "top") -> tuple[str, str, str] | None:
    name_text = str(name or "").strip()
    url_text = str(url or "").strip()
    if not name_text or not url_text:
        return None
    try:
        pick_text = canonical_pick(str(pick or "top"))
    except ValueError:
        return None
    return name_text, url_text, pick_text


def _valid_old_values(
    item: object, url: str, wanted_periods: list[int]
) -> dict[int, str] | None:
    if not isinstance(item, dict):
        return None
    raw_periods = item.get("periods")
    raw_values = item.get("values")
    if not isinstance(raw_periods, list) or not isinstance(raw_values, list):
        return None
    if len(raw_periods) != len(raw_values):
        return None
    try:
        periods = [int(value) for value in raw_periods]
    except (TypeError, ValueError):
        return None
    if (
        any(period <= 0 for period in periods)
        or len(set(periods)) != len(periods)
        or periods != sorted(periods, reverse=True)
        or any(not is_valid_result_value(str(value), url) for value in raw_values)
    ):
        return None
    return {
        period: str(value)
        for period, value in zip(periods, raw_values)
        if period in wanted_periods
    }


def _valid_old_failure_state(
    item: object, wanted_periods: list[int]
) -> tuple[list[int], dict[int, str]] | None:
    if not isinstance(item, dict):
        return [], {}
    raw_failed_periods = item.get("failed_periods", [])
    raw_reasons = item.get("failure_reasons", {})
    if not isinstance(raw_failed_periods, list) or not isinstance(raw_reasons, dict):
        return None
    try:
        failed_periods = [int(value) for value in raw_failed_periods]
    except (TypeError, ValueError):
        return None
    if (
        any(period <= 0 for period in failed_periods)
        or len(set(failed_periods)) != len(failed_periods)
    ):
        return None
    reasons: dict[int, str] = {}
    for raw_period, reason in raw_reasons.items():
        period_text = str(raw_period)
        if not period_text.isdigit():
            return None
        failure_period = int(period_text)
        if failure_period <= 0:
            return None
        if failure_period in wanted_periods:
            reasons[failure_period] = str(reason)
    kept_failed_periods = [
        period for period in failed_periods if period in wanted_periods
    ]
    if set(kept_failed_periods) != set(reasons) or any(
        not reason.strip() for reason in reasons.values()
    ):
        return None
    return kept_failed_periods, reasons


def update_recent_cache_from_current_results(
    path: Path,
    period: int,
    sites: Sequence[object],
    results: Sequence[CurrentRunResult],
) -> bool:
    with file_lock(path):
        return _update_recent_cache_from_current_results(path, period, sites, results)


def _update_recent_cache_from_current_results(
    path: Path,
    period: int,
    sites: Sequence[object],
    results: Sequence[CurrentRunResult],
) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"最近10期缓存更新失败: 无法读取现有缓存({type(exc).__name__}: {exc})", file=sys.stderr)
        return False
    if not isinstance(payload, dict):
        print("最近10期缓存更新失败: 现有缓存格式错误", file=sys.stderr)
        return False
    try:
        current_fingerprint = configuration_fingerprint(sites)
    except Exception as exc:
        print(f"最近10期缓存更新失败: 无法生成当前配置指纹({type(exc).__name__}: {exc})", file=sys.stderr)
        return False
    if payload.get("config_fingerprint") != current_fingerprint:
        print("最近10期缓存更新失败: 缓存配置指纹缺失或不匹配", file=sys.stderr)
        return False

    try:
        previous_period = int(payload["period"])
        window = int(payload.get("window") or 10)
    except (KeyError, TypeError, ValueError):
        print("最近10期缓存更新失败: 现有缓存缺少有效 period/window", file=sys.stderr)
        return False
    if payload.get("schema") != 2 or window != 10:
        print("最近10期缓存更新失败: 缓存schema或10期窗口不匹配", file=sys.stderr)
        return False
    if previous_period > period:
        print(f"最近10期缓存更新失败: 缓存最新期{previous_period}大于本次{period}期", file=sys.stderr)
        return False

    old_items = payload.get("sites")
    if not isinstance(old_items, list):
        print("最近10期缓存更新失败: 现有缓存没有站点数据", file=sys.stderr)
        return False
    old_by_identity: dict[tuple[str, str, str], dict] = {}
    old_active_identities: list[tuple[str, str, str]] = []
    for old_item in old_items:
        if not isinstance(old_item, dict):
            continue
        identity = _cache_identity(
            old_item.get("name"), old_item.get("url"), old_item.get("pick")
        )
        if identity is None:
            continue
        if identity in old_by_identity:
            print("最近10期缓存更新失败: 现有缓存存在重复站点身份", file=sys.stderr)
            return False
        old_by_identity[identity] = old_item
        if not old_item.get("archived"):
            old_active_identities.append(identity)

    previous_periods = list(
        range(previous_period, previous_period - window, -1)
    )
    previous_period_set = set(previous_periods)
    validated_values: dict[tuple[str, str, str], dict[int, str]] = {}
    validated_failures: dict[
        tuple[str, str, str], tuple[list[int], dict[int, str]]
    ] = {}
    complete_old_count = 0
    for identity in old_active_identities:
        old_item = old_by_identity[identity]
        values = _valid_old_values(old_item, identity[1], previous_periods)
        failure_state = _valid_old_failure_state(old_item, previous_periods)
        if values is None or failure_state is None:
            print(
                f"最近10期缓存更新失败: 站点{identity[0]}的历史状态损坏",
                file=sys.stderr,
            )
            return False
        failed_periods, reasons = failure_state
        raw_value_periods = {int(value) for value in old_item.get("periods", [])}
        raw_failed_periods = {
            int(value) for value in old_item.get("failed_periods", [])
        }
        raw_reason_periods = {
            int(value) for value in old_item.get("failure_reasons", {})
        }
        if (
            raw_value_periods != set(values)
            or raw_failed_periods != set(failed_periods)
            or raw_reason_periods != set(reasons)
            or set(values) & set(failed_periods)
            or set(values) | set(failed_periods) != previous_period_set
        ):
            print(
                f"最近10期缓存更新失败: 站点{identity[0]}的历史窗口不完整",
                file=sys.stderr,
            )
            return False
        validated_values[identity] = values
        validated_failures[identity] = (failed_periods, reasons)
        if not failed_periods:
            complete_old_count += 1

    old_fail_count = len(old_active_identities) - complete_old_count
    if (
        payload.get("site_count") != len(old_active_identities)
        or payload.get("vector_count") != complete_old_count
        or payload.get("fail_count") != old_fail_count
        or not isinstance(payload.get("fail_lines"), list)
    ):
        print("最近10期缓存更新失败: 缓存汇总元数据不一致", file=sys.stderr)
        return False

    configured_identities: list[tuple[str, str, str]] = []
    for site in sites:
        identity = _cache_identity(
            getattr(site, "name", ""),
            getattr(site, "url", ""),
            getattr(site, "pick", "top"),
        )
        assert identity is not None  # configuration_fingerprint validated this site
        configured_identities.append(identity)
    if old_active_identities != configured_identities:
        print("最近10期缓存更新失败: 现有缓存活动站点身份或顺序不匹配", file=sys.stderr)
        return False
    active_identities = set(configured_identities)
    archived_items = [
        dict(item)
        for item in old_items
        if isinstance(item, dict)
        and item.get("archived")
        and _cache_identity(item.get("name"), item.get("url"), item.get("pick"))
        not in active_identities
    ]
    result_indexes = [getattr(result, "index", None) for result in results]
    if (
        any(
            type(index) is not int
            or index < 1
            or index > len(sites)
            for index in result_indexes
        )
        or len(set(result_indexes)) != len(result_indexes)
    ):
        print("最近10期缓存更新失败: 本轮结果索引重复或越界", file=sys.stderr)
        return False
    for result in results:
        site = sites[result.index - 1]
        ranking_value = result.ranking_value
        success_line = result.success_line
        if success_line is not None:
            url = str(getattr(site, "url", ""))
            if (
                result.fail_line is not None
                or ranking_value is None
                or not is_valid_result_value(ranking_value, url)
            ):
                print("最近10期缓存更新失败: 本轮成功结果字段不一致", file=sys.stderr)
                return False
            labels = (
                " ".join(f"{value}尾" for value in ranking_value.split("、"))
                if url in TWO_TAIL_SITE_URLS
                else f"{ranking_value}尾"
            )
            expected_line = f"{labels} {getattr(site, 'name', '')}"
            if success_line != expected_line:
                print("最近10期缓存更新失败: 本轮成功结果字段不一致", file=sys.stderr)
                return False
        elif ranking_value is not None or not result.fail_line:
            print("最近10期缓存更新失败: 本轮失败结果字段不完整", file=sys.stderr)
            return False
    result_by_index = {result.index: result for result in results}
    wanted_periods = list(range(period, period - window, -1))
    new_items: list[dict] = []
    fail_lines: list[str] = []
    complete_count = 0

    for index, site in enumerate(sites, start=1):
        name = str(getattr(site, "name", ""))
        url = str(getattr(site, "url", ""))
        old_identity = configured_identities[index - 1]
        pick = old_identity[2]
        old_values = {
            old_period: value
            for old_period, value in validated_values[old_identity].items()
            if old_period in wanted_periods
        }
        old_values.pop(period, None)

        _, previous_reasons = validated_failures[old_identity]
        reasons = {
            failed: reason
            for failed, reason in previous_reasons.items()
            if failed in wanted_periods
        }

        result = result_by_index.get(index)
        if (
            result is not None
            and result.success_line
            and result.ranking_value
            and is_valid_result_value(result.ranking_value, url)
        ):
            old_values[period] = result.ranking_value
            reasons.pop(period, None)
        else:
            failure = result.fail_line if result is not None and result.fail_line else "本次未生成有效抓取结果"
            reasons[period] = failure
            fail_lines.append(
                failure if failure.startswith("失败 ") else f"失败 {name} {url} 原因: {failure}"
            )

        for missing_period in (item for item in wanted_periods if item not in old_values):
            reasons.setdefault(missing_period, f"缓存缺少{missing_period}期有效数据")
        failed_periods = sorted(reasons, reverse=True)
        kept_periods = [item for item in wanted_periods if item in old_values]
        item = {
            "name": name,
            "url": url,
            "pick": pick,
            "periods": kept_periods,
            "values": [old_values[item] for item in kept_periods],
            "extended": max(0, window - len(kept_periods)),
        }
        if failed_periods:
            item["failed_periods"] = failed_periods
            item["failure_reasons"] = {str(item): reasons[item] for item in failed_periods}
        else:
            complete_count += 1
        new_items.append(item)

    new_items.extend(archived_items)
    cache_fail_count = sum(
        1 for item in new_items if not item.get("archived") and item.get("failed_periods")
    )
    payload = {
        "schema": 2,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "period": period,
        "window": window,
        "config_fingerprint": current_fingerprint,
        "site_count": len(sites),
        "vector_count": complete_count,
        "fail_count": cache_fail_count,
        "fail_lines": fail_lines,
        "sites": new_items,
    }
    _atomic_write_text_unlocked(
        path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"最近10期缓存已按本次{period}期滚动更新: "
        f"完整 {complete_count} 条, 标记失败 {cache_fail_count} 条"
    )
    return True
