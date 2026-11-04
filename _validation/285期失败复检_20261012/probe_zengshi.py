"""285 期「曾氏」Qvuu 历史接口复检：直连 JSON 接口，判断是发布时序(无数据)还是接口结构变化(异常)。

只读，不写任何正式文件。产出 probe_zengshi_out.json。
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.fetch.profile import (  # noqa: E402
    _profile_item_period,
    decode_qvuu_history_json,
    spa_forum_target_id,
)
from shawei.parsers.common import normalize_text  # noqa: E402

URL = "https://qvuuqqs.8imf7-hteuh-ylwuqv.xyz/#/forums/15340352"
ORIGIN = "https://qvuuqqs.8imf7-hteuh-ylwuqv.xyz"
TARGET_PERIOD = 285
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = Path(__file__).with_name("probe_zengshi_out.json")


def fetch_json(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        status = resp.status
        ctype = resp.headers.get("Content-Type")
    text = body.decode("utf-8", errors="replace")
    return status, ctype, text


def main() -> int:
    report: dict = {"url": URL, "target_period": TARGET_PERIOD, "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S")}

    # 1) 同站(Qvuu)其他作者今天是否拿到 285 —— 站点侧是否正常
    cache = json.loads((ROOT / "recent_10_cache.json").read_text(encoding="utf-8-sig"))
    qvuu_entries = [e for e in cache["sites"] if "qvuuqqs." in str(e.get("url"))]
    report["qvuu_peers"] = [
        {
            "name": e.get("name"),
            "archived": bool(e.get("archived")),
            "has_285": 285 in (e.get("periods") or []),
            "value_285": (e.get("values") or [None])[(e.get("periods") or []).index(285)] if 285 in (e.get("periods") or []) else None,
            "newest_period": (e.get("periods") or [None])[0],
            "failed_periods": e.get("failed_periods"),
        }
        for e in qvuu_entries
    ]
    print(f"== 同站 Qvuu 条目 {len(report['qvuu_peers'])} 个 ==")
    for peer in report["qvuu_peers"]:
        print(peer)

    route_id = spa_forum_target_id(URL)
    report["route_id"] = route_id

    # 2) 原始记录
    status, ctype, text = fetch_json(f"{ORIGIN}/api/v1/forums/{route_id}")
    report["route"] = {"status": status, "ctype": ctype, "len": len(text)}
    try:
        route = json.loads(text)
        report["route"]["json"] = route
        print("\n== /api/v1/forums/%s ==" % route_id)
        print(json.dumps(route, ensure_ascii=False)[:1200])
    except json.JSONDecodeError:
        report["route"]["raw_head"] = text[:600]
        print("\n路由接口非 JSON:", text[:300])
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        return 2

    author_id = str(route.get("user_id") or "")
    sub_topic = str(route.get("sub_topic") or "")
    report["author_id"] = author_id
    report["sub_topic"] = sub_topic

    # 3) 作者历史接口
    history_url = f"{ORIGIN}/api/v1/users/{author_id}/references/history"
    status, ctype, text = fetch_json(history_url)
    report["history"] = {"url": history_url, "status": status, "ctype": ctype, "len": len(text)}
    payload = json.loads(text)
    report["history"]["count"] = len(payload)
    print(f"\n== history: {len(payload)} 条 ==")

    mine = [it for it in payload if isinstance(it, dict) and str(it.get("user_id") or "") == author_id]
    topics: dict[str, list[tuple[int | None, str]]] = {}
    for it in mine:
        key = normalize_text(str(it.get("sub_topic") or ""))
        topics.setdefault(key, []).append((_profile_item_period(it), str(it.get("id") or "")))
    print("\n该作者在本接口出现的栏目:")
    for key, rows in topics.items():
        periods = [p for p, _ in rows if p is not None]
        print(f"  - {key!r}: {len(rows)} 条 期数 {min(periods) if periods else None}..{max(periods) if periods else None} 最新 {sorted(periods, reverse=True)[:6]}")
    report["author_topics"] = {
        key: {
            "count": len(rows),
            "periods_desc": sorted([p for p, _ in rows if p is not None], reverse=True),
            "ids": [i for _, i in rows],
        }
        for key, rows in topics.items()
    }

    target_key = normalize_text(sub_topic)
    rows = topics.get(target_key, [])
    target_rows = sorted([p for p, _ in rows if p is not None], reverse=True)
    report["target_topic_rows"] = target_rows[:12]
    print(f"\n目标栏目 {sub_topic!r} 期数(降序前12)={target_rows[:12]}")
    print(f"是否含 {TARGET_PERIOD}: {TARGET_PERIOD in target_rows}")

    newest = [it for it in mine if normalize_text(str(it.get("sub_topic") or "")) == target_key]
    newest.sort(key=lambda it: _profile_item_period(it) or 0, reverse=True)
    if newest:
        report["newest_item"] = newest[0]
        print("\n最新目标条目原文:")
        print(json.dumps(newest[0], ensure_ascii=False)[:1000])

    # 4) 复现解析器判定
    try:
        ids = decode_qvuu_history_json(text, author_id, TARGET_PERIOD, sub_topic, "top")
        report["decode_result"] = {"ok": True, "ids": ids}
        print(f"\n解析器判 OK: ids={ids}")
    except Exception as exc:  # noqa: BLE001
        report["decode_result"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        print(f"\n解析器判失败: {type(exc).__name__}: {exc}")

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n证据已写 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
