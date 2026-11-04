# -*- coding: utf-8 -*-
"""渲染 pa4dwcnd64.772149.shop（书签名=一心为民），核对我们站点与 294 期（只读）。"""
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

URLS = [
    ("bbs首页", f"{BASE}/bbs/"),
    ("旧ID帖子", f"{BASE}/bbs/topic.php?id=20758"),
]

ALL_SITES = [
    "坚持战斗", "无量寿佛", "再度归来", "童颜鹤发", "一心为民",
    "怪咖小生", "澳彩碼王", "寻宝探码", "财源滚滚", "海角天涯",
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
                await page.wait_for_timeout(3500)
                body = await page.locator("body").inner_text()
                html = await page.content()
                item["final_url"] = page.url
                item["body_len"] = len(body)
                item["site_hits"] = [s for s in ALL_SITES if s in body]
                periods = sorted({int(x) for x in re.findall(r"(?<!\d)(\d{2,4})\s*期", body)})
                item["periods_tail"] = periods[-8:]
                item["has_294"] = PERIOD in periods
                (OUT / f"render_772149_{label}.txt").write_text(body, encoding="utf-8")
                (OUT / f"render_772149_{label}.html").write_text(html, encoding="utf-8")
                idx = body.find("一心为民")
                if idx >= 0:
                    item["ctx"] = re.sub(r"\s+", " ", body[max(0, idx - 300): idx + 500])
                # 帖子链接
                links = [h for h in dict.fromkeys(re.findall(r'href="([^"]+)"', html))
                         if "topic.php" in h or "id=" in h]
                item["links"] = links[:10]
            except Exception as exc:  # noqa: BLE001
                item["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
            finally:
                if page is not None:
                    try:
                        await page.close()
                    except Exception:
                        pass
            results.append(item)
            print(label, json.dumps({k: v for k, v in item.items() if k != "ctx"},
                                    ensure_ascii=False)[:500])
            if item.get("ctx"):
                print("   CTX:", item["ctx"][:400])
        await ctx.close()

    (OUT / "render_772149.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


asyncio.run(main())
