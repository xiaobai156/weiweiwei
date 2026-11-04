# -*- coding: utf-8 -*-
"""抓取 772149.shop 论坛全部帖子标题与链接，比对我们 10 个站（只读）。

同时试探分页，尽量扩散覆盖。
"""
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
PERIOD = 294
BASE = "https://pa4dwcnd64.772149.shop"
PAGES = [f"{BASE}/bbs/"] + [f"{BASE}/bbs/?page={i}" for i in range(2, 8)]

SITES = [
    "坚持战斗", "无量寿佛", "再度归来", "童颜鹤发", "一心为民",
    "怪咖小生", "澳彩碼王", "寻宝探码", "财源滚滚", "海角天涯",
]


async def main() -> None:
    from playwright.async_api import async_playwright

    all_rows: list[dict] = []
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(browser_profile_dir()),
            headless=True,
            viewport={"width": 1366, "height": 3000},
            ignore_https_errors=True,
        )
        page = await ctx.new_page()
        for url in PAGES:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=40000)
                await page.wait_for_timeout(2200)
                body = await page.locator("body").inner_text()
                html = await page.content()
            except Exception:  # noqa: BLE001
                continue
            idx = PAGES.index(url) if url in PAGES else 0
            (OUT / f"forum772149_p{idx}.txt").write_text(body, encoding="utf-8")
            # 抓 a 标签：链接 + 文本
            anchors = re.findall(
                r'<a[^>]+href="([^"]*topic\.php\?id=(\d+)[^"]*)"[^>]*>(.*?)</a>',
                html, re.I | re.S,
            )
            for href, tid, inner in anchors:
                title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inner)).strip()
                all_rows.append({"page": url, "href": href, "tid": tid, "title": title})
            print(url, "标题数", len(anchors))

        # 逐站匹配
        print("\n=== 站名匹配 ===")
        matched = {}
        for site in SITES:
            hits = [r for r in all_rows if site in r["title"]]
            if hits:
                matched[site] = hits
                print(f"  ✅ {site}: {len(hits)} 条")
                for h in hits[:4]:
                    print(f"      id={h['tid']}  {h['title'][:70]}")
            else:
                print(f"  ❌ {site}")

        # 一尾相关
        print("\n=== 含「尾」的帖子标题 ===")
        for r in list(dict.fromkeys((x["tid"], x["title"]) for x in all_rows)):
            if "尾" in r[1]:
                print(f"  id={r[0]}  {r[1][:80]}")

        await ctx.close()

    (OUT / "forum772149_rows.json").write_text(
        json.dumps({"rows": all_rows, "matched": matched}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


asyncio.run(main())
