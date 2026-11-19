"""323 期失败站只读验证：夜月花朝（绝对top边界是322期）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.config.sites import load_sites  # noqa: E402
from shawei.services.crawl_site import crawl_current_site  # noqa: E402

OUT = Path(__file__).resolve().parent
PERIOD = 323
TARGET = "https://u6agr.dgj1u-jtp00-hcqvut.xyz/topic/226654.html"


def main() -> None:
    sites = load_sites(ROOT / "sites.json")
    index = next(i for i, s in enumerate(sites, 1) if s.url == TARGET)
    site = sites[index - 1]
    rows = []
    for attempt in (1, 2):
        result = crawl_current_site(index, len(sites), site, PERIOD, 30, retries=2)
        rows.append(
            {
                "attempt": attempt,
                "success_line": result.success_line,
                "fail_line": result.fail_line,
                "ranking_value": result.ranking_value,
                "stage": result.failure_stage,
                "reason": result.failure_reason,
                "messages": result.messages[-4:],
            }
        )
        print(f"--- 第{attempt}次 ---")
        print("成功:", result.success_line, "| 失败:", (result.fail_line or "")[:200])
        print("消息:", *result.messages[-3:], sep="\n  ")
    (OUT / "verify_323.json").write_text(
        json.dumps({"period": PERIOD, "site": site.name, "url": TARGET, "runs": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
