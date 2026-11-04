# -*- coding: utf-8 -*-
"""292 期换址只读端到端验证：内存内挂载新 URL 规则，走项目真实抓取链路。

不写 sites.json、不写 rules.py、不写缓存、不写正式 TXT。
新 URL 规则来自同站旧 URL 的专属规则（路径与站名不变，仅换 origin）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.config.rules import STRICT_SITE_RULES, effective_rule_for  # noqa: E402
from shawei.config.sites import load_sites  # noqa: E402
from shawei.services.crawl_site import crawl_current_site  # noqa: E402

OUT = Path(__file__).resolve().parent
PERIOD = 292
NEW_ORIGIN = "https://dzdsqxrw.1mppg-x8rsf-cxwlxc.cyou:17455"

# 站名, 旧URL（=配置里现在的 URL）, 方向
TARGETS = [
    ("龙凤呈祥", "https://tulprhfc.wghcb-bnmgm-hyymaz.work:16655/topic/324698.html", "top"),
    ("可怜春天", "https://jogavu.6bl6s-ilo1w-yfnvvl.work:16677/topic/678625.html", "bottom"),
    ("正气凛然", "https://whsbrmz.qclrc-4mk42-vnxbyg.work:16677/topic/248009.html", "top"),
    ("违背烟蒂", "https://tulprhfc.wghcb-bnmgm-hyymaz.work:16655/topic/305414.html", "top"),
    ("清清淡淡", "https://iboatq.pjgpm-epbf7-lxpezb.work:16677/topic/324703.html", "top"),
    ("八面驶风", "https://pvxiftuf.yumkw-u4s81-hpytyz.work:16677/topic/559099.html", "top"),
]

sites = load_sites()
by_name = {site.name: (i, site) for i, site in enumerate(sites, 1)}

results = []
for name, old_url, pick in TARGETS:
    topic_path = "/" + old_url.split("/", 3)[3]
    new_url = NEW_ORIGIN + topic_path
    item = {"name": name, "old_url": old_url, "new_url": new_url, "pick": pick}

    old_rule = STRICT_SITE_RULES.get(old_url)
    if old_rule is None:
        item["error"] = "旧URL没有专属规则"
        results.append(item)
        print(name, "-> 旧URL没有专属规则")
        continue

    # 只在内存里挂新 URL 规则，磁盘文件不动
    if new_url not in STRICT_SITE_RULES:
        STRICT_SITE_RULES[new_url] = old_rule

    index, _ = by_name[name]
    try:
        from dataclasses import replace as dc_replace

        probe_site = dc_replace(by_name[name][1], url=new_url)
        result = crawl_current_site(index, len(sites), probe_site, PERIOD, 25, retries=1)
        item["success_line"] = result.success_line
        item["fail_line"] = result.fail_line
        item["ranking_value"] = result.ranking_value
        item["verdict"] = "成功" if result.success_line else "失败"
    except Exception as exc:  # noqa: BLE001
        item["error"] = f"{type(exc).__name__}: {exc}"
        item["verdict"] = "异常"
    results.append(item)
    print(f"{name:6s} {pick:6s} -> {item.get('success_line') or item.get('fail_line') or item.get('error')}")

(OUT / "换址验证_292.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("成功", sum(1 for r in results if r.get("verdict") == "成功"), "/", len(results))
