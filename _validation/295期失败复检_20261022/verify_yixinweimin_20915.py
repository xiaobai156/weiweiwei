# -*- coding: utf-8 -*-
"""验证一心为民新帖 id=20915 的 295 期取值（只读）。"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.fetch.browser import browser_profile_dir  # noqa: E402

OUT = Path(__file__).resolve().parent
URL = "https://88888020827.983654.xyz/bbs/topic.php?id=20915"


async def main() -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(browser_profile_dir()),
            headless=True,
            viewport={"width": 1366, "height": 3200},
            ignore_https_errors=True,
        )
        page = await ctx.new_page()
        await page.goto(URL, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(2500)
        body = await page.inner_text("body")
        (OUT / "new_一心为民_20915.txt").write_text(body, encoding="utf-8")
        print("len", len(body), "| 含一心为民", "一心为民" in body, "| 已下架", "此帖子ID已被下架" in body)
        for line in body.splitlines():
            if "295" in line and "尾" in line:
                print("ROW:", re.sub(r"\s+", " ", line)[:150])
        await ctx.close()


asyncio.run(main())
