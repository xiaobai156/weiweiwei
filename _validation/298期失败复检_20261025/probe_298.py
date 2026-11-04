# -*- coding: utf-8 -*-
"""298 期失败站「物产丰富」只读验证（浏览器渲染）。"""
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
PERIOD = 298
NAME = "物产丰富"
URL = "https://8818.www19753a.com/read.php?tid=501"


async def main() -> None:
    from playwright.async_api import async_playwright

    item = {"name": NAME, "url": URL}
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(browser_profile_dir()),
            headless=True,
            viewport={"width": 1366, "height": 3200},
            ignore_https_errors=True,
        )
        page = await ctx.new_page()
        try:
            await page.goto(URL, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(2500)
            body = await page.inner_text("body")
            item["len"] = len(body)
            item["name_hit"] = NAME in body
            periods = sorted({int(x) for x in re.findall(r"(?<!\d)(\d{2,4})\s*期", body)})
            item["periods_tail"] = periods[-8:]
            item["has_298"] = PERIOD in periods
            item["max"] = periods[-1] if periods else None
            (OUT / f"pw_{NAME}_298.txt").write_text(body, encoding="utf-8")
            # 296-298 附近原文
            rows = []
            for line in body.splitlines():
                if re.search(r"(?<!\d)(29[5-9])\s*期", line):
                    rows.append(re.sub(r"\s+", " ", line)[:130])
            item["rows"] = rows[:12]
            item["verdict"] = "可救(有298期)" if item["has_298"] else f"无数据(最新{item['max']}期)"
        except Exception as exc:  # noqa: BLE001
            item["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
            item["verdict"] = "异常(打不开)"
        finally:
            await ctx.close()

    print(json.dumps({k: v for k, v in item.items() if k != "rows"}, ensure_ascii=False))
    for r in item.get("rows", []):
        print("  ROW:", r)
    (OUT / "probe_298.json").write_text(
        json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8"
    )


asyncio.run(main())
