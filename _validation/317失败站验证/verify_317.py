# -*- coding: utf-8 -*-
"""317 期失败站只读验证：真实抓取一次，区分异常与无数据，不写任何正式输出。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shawei.config.rules import effective_rule_for  # noqa: E402
from shawei.config.sites import load_sites  # noqa: E402
from shawei.services.crawl_site import crawl_current_site  # noqa: E402

PERIOD = 317
TARGETS = ("刘半仙", "飞龙在天", "无量寿佛", "跑马图", "一心为民")


def main() -> None:
    sites = load_sites(Path("sites.json"))
    by_name = {site.name: (i, site) for i, site in enumerate(sites)}
    out: list[dict[str, object]] = []
    for name in TARGETS:
        item = by_name.get(name)
        if item is None:
            print(f"[{name}] 不在活动站点列表（可能已封存）", flush=True)
            out.append({"name": name, "status": "不在活动列表"})
            continue
        idx, site = item
        rule = effective_rule_for(site.url, site.name)
        print(
            f"[{name}] sources={rule.allowed_sources} parser={rule.dedicated_parser!r} pick={site.pick}",
            flush=True,
        )
        result = crawl_current_site(idx, len(sites), site, PERIOD, 25, retries=2)
        if result.success_line:
            print(f"[{name}] RESULT: 有数据-成功 {result.success_line}", flush=True)
        else:
            print(f"[{name}] RESULT: 失败 {result.fail_line}", flush=True)
        for msg in result.messages:
            print("   ", msg, flush=True)
        out.append(
            {
                "name": name,
                "status": "有数据-成功" if result.success_line else "失败",
                "line": result.success_line,
                "fail_line": result.fail_line,
                "messages": list(result.messages),
            }
        )
    path = Path(__file__).with_name("verify_317.json")
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("写入", path, flush=True)


if __name__ == "__main__":
    main()
