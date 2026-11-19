"""322 期失败站只读验证：4 站（3 站 SSL 协议错误、1 站渲染超时）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.config.sites import load_sites  # noqa: E402
from shawei.services.crawl_site import crawl_current_site  # noqa: E402

OUT = Path(__file__).resolve().parent
PERIOD = 322
TARGETS = [
    "https://gboqrz.sm0a0-x9x2c-xyvjdr.work/topic/172572.html",
    "https://gboqrz.sm0a0-x9x2c-xyvjdr.work/topic/241106.html",
    "https://yqjfwqsc.1dayz-aetgp-kbjidr.xyz:16677/topic/682033.html",
    "https://ghegvfr.5n8r1-kurkd-esielp.cyou:17455/",
]


def main() -> None:
    sites = load_sites(ROOT / "sites.json")
    report = []
    for url in TARGETS:
        match = [s for s in sites if s.url == url]
        if not match:
            print("!! 站点不在活动列表:", url)
            report.append({"url": url, "status": "不在活动站点列表"})
            continue
        site = match[0]
        index = sites.index(site) + 1
        result = crawl_current_site(index, len(sites), site, PERIOD, 30, retries=2)
        row = {
            "name": site.name,
            "url": url,
            "pick": site.pick,
            "success_line": result.success_line,
            "fail_line": result.fail_line,
            "ranking_value": result.ranking_value,
            "stage": result.failure_stage,
            "reason": result.failure_reason,
            "messages": result.messages[-3:],
        }
        report.append(row)
        print(f"=== {site.name} ({site.pick}) ===")
        if result.success_line:
            print("  有数据-成功:", result.success_line, "| 排行值:", result.ranking_value)
        else:
            print("  失败:", (result.fail_line or "")[:200])
        for msg in result.messages[-2:]:
            print("  消息:", msg[:200])
    (OUT / "verify_322.json").write_text(
        json.dumps({"period": PERIOD, "runs": report}, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
