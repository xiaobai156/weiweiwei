# -*- coding: utf-8 -*-
"""查「再度归来」在大掌柜论坛是否有新帖（旧帖已下架）。只读。"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.fetch.browser import browser_profile_dir  # noqa: E402

OUT = Path(__file__).resolve().parent
BASE = "https://0130190827.673454.xyz"


async def main() -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(browser_profile_dir()),
            headless=True,
            viewport={"width": 1366, "height": 3200},
            ignore_https_errors=True,
        )
        pg = await ctx.new_page()
        await pg.goto(BASE + "/bbs/", wait_until="domcontentloaded", timeout=45000)
        await pg.wait_for_timeout(2500)
        html = await pg.content()
        (OUT / "forum_dazhanggui_297.html").write_text(html, encoding="utf-8")

        anchors = re.findall(
            r'<a[^>]+href="([^"]*topic\.php\?id=(\d+)[^"]*)"[^>]*>(.*?)</a>',
            html, re.I | re.S,
        )
        print("帖子总数", len(anchors))
        for href, tid, inner in anchors:
            title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inner)).strip()
            if "再度归来" in title:
                print(f"  命中 id={tid}  {title[:80]}")
        await ctx.close()


asyncio.run(main())
