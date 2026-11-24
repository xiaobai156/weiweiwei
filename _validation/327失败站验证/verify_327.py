"""327 期失败站只读验证（6 站，同一站群 4.48kk49.com）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.config.sites import load_sites  # noqa: E402
from shawei.services.crawl_site import crawl_current_site  # noqa: E402

OUT = Path(__file__).resolve().parent
PERIOD = 327
TARGETS = [
    "https://4.48kk49.com:1888/Article/ar_content/id/1556/tid/82.html",
    "https://4.48kk49.com:1888/Article/ar_content/id/1544/tid/82.html",
    "https://4.48kk49.com:1888/Article/ar_content/id/1543/tid/82.html",
    "https://4.48kk49.com:1888/Article/ar_content/id/1469/tid/82.html",
    "https://4.48kk49.com:1888/Article/ar_content/id/1452/tid/82.html",
    "https://4.48kk49.com:1888/Article/ar_content/id/199/tid/4.html",
]


def main() -> None:
    sites = load_sites(ROOT / "sites.json")
    rows = []
    for target in TARGETS:
        index = next((i for i, s in enumerate(sites, 1) if s.url == target), None)
        if index is None:
            print("跳过（不在活动站点）:", target)
            rows.append({"url": target, "skipped": "not active site"})
            continue
        site = sites[index - 1]
        result = crawl_current_site(index, len(sites), site, PERIOD, 30, retries=2)
        rows.append(
            {
                "name": site.name,
                "url": target,
                "success_line": result.success_line,
                "fail_line": result.fail_line,
                "ranking_value": result.ranking_value,
                "stage": result.failure_stage,
                "reason": result.failure_reason,
                "messages": result.messages[-3:],
            }
        )
        print(f"=== {site.name} ===")
        print("  成功:", result.success_line, "| 失败:", (result.fail_line or "")[:160])
    (OUT / "verify_327.json").write_text(
        json.dumps({"period": PERIOD, "runs": rows}, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
