# -*- coding: utf-8 -*-
"""六玄网新域名（ulgvaugz…:17455）浏览器渲染勘察（只读）。

目标：确认渲染后能否出现「澳彩六玄网【综合绝杀】」区块、最新期号、292 期是否有数据。
不写配置、缓存、正式 TXT。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.fetch.browser import browser_profile_dir  # noqa: E402

OUT = Path(__file__).resolve().parent
PERIOD = 292
URLS = [
    ("新域名首页", "https://ulgvaugz.1vh1x-5fer6-nlzydr.work:17455/"),
    ("新域名#87127", "https://ulgvaugz.1vh1x-5fer6-nlzydr.work:17455/#87127"),
]


async def main() -> None:
    from playwright.async_api import async_playwright

    results = []
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(browser_profile_dir()),
            headless=True,
            viewport={"width": 1280, "height": 2600},
            ignore_https_errors=True,
        )
        for label, url in URLS:
            item = {"label": label, "url": url}
            page = None
            try:
                page = await ctx.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                await page.wait_for_timeout(3000)
                body = await page.locator("body").inner_text()
                item["final_url"] = page.url
                item["body_len"] = len(body)
                item["has_87127"] = "87127" in body
                item["has_liuxuan"] = "六玄" in body
                item["has_anchor"] = "综合绝杀" in body
                periods = sorted({int(x) for x in re.findall(r"(?<!\d)(\d{2,4})\s*期", body)})
                item["periods_tail"] = periods[-8:]
                item["period_hit"] = PERIOD in periods
                idx = body.find("综合绝杀")
                if idx < 0:
                    idx = body.find("六玄")
                if idx >= 0:
                    item["context"] = re.sub(r"\s+", " ", body[max(0, idx - 200): idx + 600])
                (OUT / f"pw_liuxuan_new_{label.replace('#', '_')}.txt").write_text(body, encoding="utf-8")
                # 渲染后的 iframe 也记录下来
                frames = [f.url for f in page.frames]
                item["frames"] = frames[:6]
            except Exception as exc:  # noqa: BLE001
                item["error"] = f"{type(exc).__name__}: {exc}"
            finally:
                if page is not None:
                    try:
                        await page.close()
                    except Exception:
                        pass
            results.append(item)
            print(label, json.dumps({k: v for k, v in item.items() if k != "context"}, ensure_ascii=False))
            if item.get("context"):
                print("   CTX:", item["context"][:500])
        await ctx.close()

    (OUT / "liuxuan_new_probe.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


import asyncio  # noqa: E402

asyncio.run(main())
