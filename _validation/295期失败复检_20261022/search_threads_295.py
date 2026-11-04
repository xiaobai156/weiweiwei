# -*- coding: utf-8 -*-
"""在 7 个站所在论坛里搜同名帖子（可能换新 ID 重发），只读。

做法：打开论坛 /bbs/ 首页，抓全部帖子标题，找这 7 个站名。
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
SITES = ["再度归来", "童颜鹤发", "一心为民", "澳彩碼王", "寻宝探码", "财源滚滚", "海角天涯"]
# 各站所在论坛的根地址
FORUMS = [
    ("大掌柜", "https://0130190827.673454.xyz"),
    ("玲珑", "https://67806780827.325346.xyz"),
    ("公式王", "https://88888020827.983654.xyz"),
    ("金算盘", "https://12388990827.794555.xyz"),
    ("聚贤庄", "https://12388990827.688756.xyz"),
    ("澳门财神", "https://88888020827.997595.xyz"),
]


async def main() -> None:
    from playwright.async_api import async_playwright

    all_rows: list[dict] = []
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(browser_profile_dir()),
            headless=True,
            viewport={"width": 1366, "height": 3200},
            ignore_https_errors=True,
        )
        page = await ctx.new_page()
        for forum, base in FORUMS:
            url = base + "/bbs/"
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(2500)
                html = await page.content()
                body = await page.inner_text("body")
            except Exception as exc:  # noqa: BLE001
                print(f"{forum} 打开失败 {type(exc).__name__}")
                continue
            (OUT / f"forum_{forum}_295.txt").write_text(body, encoding="utf-8")
            anchors = re.findall(
                r'<a[^>]+href="([^"]*topic\.php\?id=(\d+)[^"]*)"[^>]*>(.*?)</a>',
                html, re.I | re.S,
            )
            print(f"\n{forum} ({base})  帖子数 {len(anchors)}")
            for href, tid, inner in anchors:
                title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inner)).strip()
                if not title:
                    continue
                all_rows.append({"forum": forum, "base": base, "tid": tid, "title": title})
            for site in SITES:
                hits = [
                    (tid, re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inner)).strip())
                    for href, tid, inner in anchors
                    if site in re.sub(r"<[^>]+>", "", inner)
                ]
                if hits:
                    print(f"   ★ {site}: {hits[:3]}")
        await ctx.close()

    print("\n=== 汇总 ===")
    for site in SITES:
        hits = [r for r in all_rows if site in r["title"]]
        print(f"{site}: {len(hits)} 条")
        for h in hits[:3]:
            print(f"    {h['forum']} id={h['tid']} {h['title'][:70]}")

    (OUT / "forum_titles_295.json").write_text(
        json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )


asyncio.run(main())
