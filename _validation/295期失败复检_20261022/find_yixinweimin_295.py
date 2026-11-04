# -*- coding: utf-8 -*-
"""找「一心为民」的杀尾帖（绝杀一尾/绝杀①尾），排除推荐人同名帖（只读）。"""
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
FORUMS = [
    ("大掌柜", "https://0130190827.673454.xyz"),
    ("玲珑", "https://67806780827.325346.xyz"),
    ("公式王", "https://88888020827.983654.xyz"),
    ("金算盘", "https://12388990827.794555.xyz"),
    ("聚贤庄", "https://12388990827.688756.xyz"),
    ("澳门财神", "https://88888020827.997595.xyz"),
    ("曾道人", "https://0130190827.657954.xyz"),
    ("小仙女", "https://0130190827.767566.xyz"),
    ("白小姐", "https://88888020827.833567.xyz"),
    ("澳门头条", "https://88888020827.885536.xyz"),
    ("王中王", "https://88888020827.897657.xyz"),
]


async def main() -> None:
    from playwright.async_api import async_playwright

    hits = []
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(browser_profile_dir()),
            headless=True,
            viewport={"width": 1366, "height": 3200},
            ignore_https_errors=True,
        )
        page = await ctx.new_page()
        for forum, base in FORUMS:
            try:
                await page.goto(base + "/bbs/", wait_until="domcontentloaded", timeout=40000)
                await page.wait_for_timeout(2000)
                html = await page.content()
            except Exception:  # noqa: BLE001
                print(f"{forum} 打不开")
                continue
            anchors = re.findall(
                r'<a[^>]+href="([^"]*topic\.php\?id=(\d+)[^"]*)"[^>]*>(.*?)</a>',
                html, re.I | re.S,
            )
            for href, tid, inner in anchors:
                title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inner)).strip()
                # 标题形如「295期：一心为民【绝杀①尾】...」= 本站；推荐人形如「295期：XX【栏目】一心为民」
                if "一心为民" in title and re.search(r"绝杀[①1一]?尾|杀[①1一]?尾", title):
                    # 站名在括号前才算本站
                    if re.search(r"期[：:]\s*一心为民", title):
                        hits.append({"forum": forum, "base": base, "tid": tid, "title": title})
                        print(f"★ {forum} id={tid} {title[:80]}")
            print(f"  {forum} 扫描 {len(anchors)} 帖")
        await ctx.close()

    print(f"\n命中 {len(hits)} 条")
    (OUT / "yixinweimin_hits_295.json").write_text(
        json.dumps(hits, ensure_ascii=False, indent=2), encoding="utf-8"
    )


asyncio.run(main())
