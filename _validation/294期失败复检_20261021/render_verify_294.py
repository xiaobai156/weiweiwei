# -*- coding: utf-8 -*-
"""只读验证：把 10 站规则在内存里改为浏览器渲染，走项目真实解析链路，看能否取到 294 期。

不写配置、不写缓存、不写正式 TXT。
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace as dc_replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.config.rules import STRICT_SITE_RULES, effective_rule_for  # noqa: E402
from shawei.config.sites import load_sites  # noqa: E402
from shawei.services import crawl_site  # noqa: E402
from shawei.services.crawl_site import crawl_current_site  # noqa: E402

OUT = Path(__file__).resolve().parent
PERIOD = 294

NAMES = [
    "坚持战斗", "无量寿佛", "再度归来", "童颜鹤发", "一心为民",
    "怪咖小生", "澳彩碼王", "寻宝探码", "财源滚滚", "海角天涯",
]

# 1) 内存内把规则改成浏览器渲染
patched = 0
for url, rule in list(STRICT_SITE_RULES.items()):
    if "/bbs/topic.php" in url and rule.prefer_rendered is False:
        STRICT_SITE_RULES[url] = dc_replace(rule, prefer_rendered=True)
        patched += 1
print(f"内存内改为浏览器渲染的规则数: {patched}")

# 清掉进程内抓取缓存，避免复用旧失败
from shawei.fetch.http_client import clear_fetch_cache  # noqa: E402
clear_fetch_cache()

sites = load_sites()
results = []
for name in NAMES:
    idx = next((i for i, s in enumerate(sites, 1) if s.name == name), None)
    if idx is None:
        print(f"  {name} 不在活动配置里")
        continue
    try:
        r = crawl_current_site(idx, len(sites), sites[idx - 1], PERIOD, 30, retries=1)
        ok = bool(r.success_line)
        results.append({
            "name": name,
            "ok": ok,
            "success_line": r.success_line,
            "fail_line": (r.fail_line or "")[:160],
        })
        print(f"  {'✅' if ok else '❌'} {name}: {r.success_line or (r.fail_line or '')[:110]}")
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ {name} 异常 {type(exc).__name__}: {str(exc)[:110]}")
        results.append({"name": name, "ok": False, "error": f"{type(exc).__name__}: {str(exc)[:120]}"})

ok_count = sum(1 for r in results if r.get("ok"))
print(f"\n成功 {ok_count} / {len(NAMES)}")
(OUT / "render_verify_294.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)
