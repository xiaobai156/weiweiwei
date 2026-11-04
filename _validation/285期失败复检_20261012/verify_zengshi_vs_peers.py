"""285 期「曾氏」决定性校验：真实接口记录 vs 页面全年版诱饵列表，并对照同站已发布 285 的作者。

只读。产出 verify_zengshi_vs_peers_out.json。
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

HERE = Path(__file__).parent
ORIGIN = "https://qvuuqqs.8imf7-hteuh-ylwuqv.xyz"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"}
ZENGSHI_USER = "1014"
PEER_USER = "4606"  # 周易算算
SUB_TOPIC = "曾氏每期绝杀一尾【已公开】"


def get_json(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={**UA, "Accept": "application/json,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def main() -> int:
    report: dict = {"checked_at": time.strftime("%Y-%m-%dT%H:%M:%S")}

    history = get_json(f"{ORIGIN}/api/v1/users/{ZENGSHI_USER}/references/history")
    mine = [i for i in history if isinstance(i, dict) and str(i.get("user_id")) == ZENGSHI_USER]
    target = sorted(
        [i for i in mine if str(i.get("sub_topic") or "").startswith("曾氏每期绝杀一尾")],
        key=lambda i: i.get("draw") or 0,
        reverse=True,
    )
    report["zengshi_target_records"] = [
        {"id": i.get("id"), "draw": i.get("draw"), "created_at": i.get("created_at")} for i in target[:4]
    ]
    print("曾氏『曾氏每期绝杀一尾』接口记录(降序):", report["zengshi_target_records"])
    newest = target[0]
    detail = get_json(f"{ORIGIN}/api/v1/forums/{newest['id']}")
    content = str(detail.get("content") or "")
    first_lines = [ln.strip() for ln in re.split(r"<[^>]+>|\n", content) if ln.strip()][:4]
    report["newest_detail"] = {
        "id": detail.get("id"),
        "draw": detail.get("draw"),
        "created_at": detail.get("created_at"),
        "first_lines": first_lines,
    }
    print("最新真实记录:", json.dumps(report["newest_detail"], ensure_ascii=False))

    # 页面诱饵列表里的同号期值
    rendered = (HERE / "probe_zengshi_browser_forum_15340352.txt").read_text(encoding="utf-8")
    template = {
        int(m.group(1)): m.group(2)
        for m in re.finditer(r"(\d{2,3})期 『曾氏绝杀一尾』杀《(\d)》尾\s+开", rendered)
    }
    cache = json.loads((ROOT / "recent_10_cache.json").read_text(encoding="utf-8-sig"))
    entry = next(e for e in cache["sites"] if e.get("name") == "曾氏")
    real = dict(zip(entry["periods"], entry["values"]))
    compare = {
        str(p): {"cache/真实接口": real.get(p), "页面列表": template.get(p)}
        for p in sorted(set(list(real) + list(template)), reverse=True)
        if p <= 284
    }
    report["compare_284_down"] = compare
    print("\n同号期值对照（真实 vs 页面列表）:")
    for period, values in compare.items():
        flag = "  <== 冲突" if values["cache/真实接口"] and values["页面列表"] and values["cache/真实接口"] != values["页面列表"] else ""
        print(f"  {period}: 真实={values['cache/真实接口']} 页面={values['页面列表']}{flag}")
    report["template_future_periods"] = sorted([p for p in template if p > 285], reverse=True)[:6]
    print(f"\n页面列表里 >285 的期号(不可能已开奖): {report['template_future_periods']}")

    # 同站对照：已发布 285 的作者
    peer_history = get_json(f"{ORIGIN}/api/v1/users/{PEER_USER}/references/history")
    peer = [i for i in peer_history if str(i.get("user_id")) == PEER_USER]
    peer_285 = [i for i in peer if i.get("draw") == 285]
    report["peer"] = {
        "user_id": PEER_USER,
        "count": len(peer),
        "newest_periods": sorted({i.get("draw") for i in peer}, reverse=True)[:6],
        "records_285": [{"id": i.get("id"), "sub_topic": i.get("sub_topic"), "created_at": i.get("created_at")} for i in peer_285],
    }
    print("\n同站作者 4606（周易算算）:", json.dumps(report["peer"], ensure_ascii=False))

    (HERE / "verify_zengshi_vs_peers_out.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print("证据已写 verify_zengshi_vs_peers_out.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
