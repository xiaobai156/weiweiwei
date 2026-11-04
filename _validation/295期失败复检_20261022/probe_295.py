# -*- coding: utf-8 -*-
"""295 期 7 个失败站只读验证：浏览器渲染 + 代理，确认帖子是否恢复、是否有 295 期。"""
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
PERIOD = 295

TARGETS = [
    ("再度归来", "https://0130190827.673454.xyz/bbs/topic.php?id=20144"),
    ("童颜鹤发", "https://67806780827.325346.xyz/bbs/topic.php?id=19812"),
    ("一心为民", "https://88888020827.983654.xyz/bbs/topic.php?id=20758"),
    ("澳彩碼王", "https://12388990827.794555.xyz/bbs/topic.php?id=21353"),
    ("寻宝探码", "https://12388990827.688756.xyz/bbs/topic.php?id=18520"),
    ("财源滚滚", "https://12388990827.688756.xyz/bbs/topic.php?id=19930"),
    ("海角天涯", "https://88888020827.997595.xyz/bbs/topic.php?id=18490"),
]


async def main() -> None:
    from playwright.async_api import async_playwright

    results = []
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(browser_profile_dir()),
            headless=True,
            viewport={"width": 1366, "height": 3000},
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
                item["has_295"] = PERIOD in periods
                item["max_period"] = periods[-1] if periods else None
                (OUT / f"pw_{name}_295.txt").write_text(body, encoding="utf-8")
                if item["removed"]:
                    item["verdict"] = "无数据(帖子下架)"
                elif item["has_295"]:
                    item["verdict"] = "可救(有295期)"
                elif periods:
                    item["verdict"] = f"无数据(最新{periods[-1]}期)"
                else:
                    item["verdict"] = "异常(页面无期数)"
            except Exception as exc:  # noqa: BLE001
                item["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
                item["verdict"] = "异常(打不开)"
            results.append(item)
            print(f"{name:6s} {item['verdict']:16s} len={item.get('len')} "
                  f"name={item.get('name_hit')} 期数={item.get('periods_tail')}")
        await ctx.close()

    (OUT / "probe_295.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


asyncio.run(main())
