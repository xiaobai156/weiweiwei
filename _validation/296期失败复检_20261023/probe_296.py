# -*- coding: utf-8 -*-
"""296 期 7 个失败站只读验证：浏览器渲染，判断是异常/无数据/可救（只读）。"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.fetch.browser import browser_profile_dir  # noqa: E402

OUT = Path(__file__).resolve().parent
PERIOD = 296

TARGETS = [
    ("纳喇满职", "https://sfch0f.ky3r5-0b4c9-yudwqy.work/topic/240474.html"),
    ("名列前茅", "https://a.995546.com/gsb.aspx?id=amjyb034"),
    ("坚持战斗", "https://1214.775486.xyz/bbs/topic.php?id=20200"),
    ("无量寿佛", "https://1214.775486.xyz/bbs/topic.php?id=20198"),
    ("再度归来", "https://0130190827.673454.xyz/bbs/topic.php?id=20330"),
    ("一心为民", "https://88888020827.983654.xyz/bbs/topic.php?id=20915"),
    ("怪咖小生", "https://0130190827.657954.xyz/bbs/topic.php?id=20210"),
    ("澳彩碼王", "https://12388990827.794555.xyz/bbs/topic.php?id=19959"),
]


async def main() -> None:
    from playwright.async_api import async_playwright

    results = []
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(browser_profile_dir()),
            headless=True,
            viewport={"width": 1366, "height": 3200},
            ignore_https_errors=True,
        )
        page = await ctx.new_page()
        for name, url in TARGETS:
            item = {"name": name, "url": url}
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(2500)
                body = await page.inner_text("body")
                item["len"] = len(body)
                item["name_hit"] = name in body
                item["removed"] = "此帖子ID已被下架" in body
                periods = sorted({int(x) for x in re.findall(r"(?<!\d)(\d{2,4})\s*期", body)})
                item["periods_tail"] = periods[-6:]
                item["has_296"] = PERIOD in periods
                item["max"] = periods[-1] if periods else None
                if item["removed"]:
                    item["verdict"] = "无数据(帖子下架)"
                elif item["has_296"]:
                    m = re.search(rf"{PERIOD}期[^\n]{{0,140}}", body)
                    item["row296"] = re.sub(r"\s+", " ", m.group(0))[:140] if m else None
                    item["verdict"] = "可救(有296期)"
                elif periods:
                    item["verdict"] = f"无数据(最新{periods[-1]}期)"
                else:
                    item["verdict"] = "异常(无期数)"
                (OUT / f"pw_{name}_296.txt").write_text(body, encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                item["error"] = f"{type(exc).__name__}: {str(exc)[:110]}"
                item["verdict"] = "异常(打不开)"
            results.append(item)
            print(f"{name:6s} {item['verdict']:18s} len={item.get('len')} "
                  f"期数={item.get('periods_tail')} | {item.get('row296') or item.get('error','')[:80]}")
        await ctx.close()

    (OUT / "probe_296.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


asyncio.run(main())
