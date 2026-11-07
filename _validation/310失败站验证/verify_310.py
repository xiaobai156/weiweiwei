# -*- coding: utf-8 -*-
"""310 期失败站只读验证：真实抓取一次，区分异常与无数据，不写任何正式输出。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shawei.config.rules import effective_rule_for  # noqa: E402
from shawei.services.crawl_site import crawl_current_site  # noqa: E402
from shawei.config.sites import load_sites  # noqa: E402


def main() -> None:
    sites = load_sites(Path("sites.json"))
    name = "奉陪到底"
    idx = next(i for i, item in enumerate(sites) if item.name == name)
    site = sites[idx]
    print("rule:", effective_rule_for(site.url, site.name))
    try:
        result = crawl_current_site(idx, len(sites), site, 310, 20, retries=2)
        print("RESULT: 有数据-成功", result)
    except Exception as exc:  # noqa: BLE001
        print(f"RESULT: 失败 {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()

