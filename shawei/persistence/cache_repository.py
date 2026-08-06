from __future__ import annotations

import datetime
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path

from shawei.config.constants import TWO_TAIL_SITE_URLS
from shawei.domain.models import CurrentRunResult
from shawei.domain.text import canonical_pick
from shawei.persistence.atomic_file import atomic_write_text


def is_valid_result_value(value: str, url: str = "") -> bool:
    if re.fullmatch(r"\d", value or ""):
        return True
    return url.strip() in TWO_TAIL_SITE_URLS and re.fullmatch(r"\d、\d", value or "") is not None


def update_recent_cache_from_current_results(
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
        previous_period = int(payload["period"])
        window = int(payload.get("window") or 10)
    except (KeyError, TypeError, ValueError):
        print("最近10期缓存更新失败: 现有缓存缺少有效 period/window", file=sys.stderr)
        return False
    if previous_period > period:
        print(f"最近10期缓存更新失败: 缓存最新期{previous_period}大于本次{period}期", file=sys.stderr)
        return False

    old_items = payload.get("sites")
    if not isinstance(old_items, list):
        print("最近10期缓存更新失败: 现有缓存没有站点数据", file=sys.stderr)
        return False
    old_by_url = {
        str(item.get("url")): item
        for item in old_items
        if isinstance(item, dict) and item.get("url")
    }
    active_urls = {str(getattr(site, "url", "")) for site in sites}
    archived_items = [
        dict(item)
        for item in old_items
        if isinstance(item, dict)
        and item.get("archived")
        and str(item.get("url") or "") not in active_urls
    ]
    result_by_index = {result.index: result for result in results}
    wanted_periods = list(range(period, period - window, -1))
    new_items: list[dict] = []
    fail_lines: list[str] = []
    complete_count = 0

    for index, site in enumerate(sites, start=1):
        name = str(getattr(site, "name", ""))
        url = str(getattr(site, "url", ""))
        try:
            pick = canonical_pick(str(getattr(site, "pick", "top")))
        except ValueError as exc:
            print(f"最近10期缓存更新失败: 站点方向无效({exc})", file=sys.stderr)
            return False
        old_item = old_by_url.get(url, {})
        try:
            old_values = {
                int(old_period): str(value)
                for old_period, value in zip(old_item.get("periods", []), old_item.get("values", []))
            }
        except (AttributeError, TypeError, ValueError):
            old_values = {}
        old_values.pop(period, None)

        old_reasons = old_item.get("failure_reasons", {}) if isinstance(old_item, dict) else {}
        reasons = {
            int(old_period): str(reason)
            for old_period, reason in old_reasons.items()
            if str(old_period).isdigit()
            and int(old_period) in wanted_periods
            and int(old_period) != period
        } if isinstance(old_reasons, dict) else {}

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
        "site_count": len(sites),
        "vector_count": complete_count,
        "fail_count": cache_fail_count,
        "fail_lines": fail_lines,
        "sites": new_items,
    }
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"最近10期缓存已按本次{period}期滚动更新: "
        f"完整 {complete_count} 条, 标记失败 {cache_fail_count} 条"
    )
    return True
