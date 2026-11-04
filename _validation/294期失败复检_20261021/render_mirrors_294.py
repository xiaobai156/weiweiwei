# -*- coding: utf-8 -*-
"""浏览器渲染书签新式镜像，定位我们站点帖子链接与 294 期数据（只读）。"""
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

# 论坛 -> (镜像URL, 我们在这个论坛的站)
MIRRORS = [
    ("金算盘", "https://lonwrl.bqy9l-s52t4-zdxbkp.xyz:17488/", ["澳彩碼王"]),
    ("曾道人", "https://wqpqqc.ek4n8-bsb5r-yiufum.xyz:17466/", ["怪咖小生"]),
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
            viewport={"width": 1366, "height": 3000},
            ignore_https_errors=True,
        )
        for forum, url, our_sites in MIRRORS:
            item = {"forum": forum, "url": url}
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
                (OUT / f"render_{forum}.txt").write_text(body, encoding="utf-8")
                (OUT / f"render_{forum}.html").write_text(html, encoding="utf-8")
                # 我们的站是否出现
                item["site_hits"] = [s for s in ALL_SITES if s in body]
                # 论坛名
                item["has_forum_name"] = forum in body
                # 帖子链接
                links = re.findall(r'href="([^"]+)"', html)
                topic_links = [
                    h for h in dict.fromkeys(links)
                    if re.search(r"(topic|read\.php|thread|article)", h, re.I)
                ]
                item["topic_links"] = topic_links[:12]
                periods = sorted({int(x) for x in re.findall(r"(?<!\d)(\d{2,4})\s*期", body)})
                item["periods_tail"] = periods[-8:]
                item["has_294"] = PERIOD in periods
                # 与本站相关的片段
                for s in our_sites:
                    idx = body.find(s)
                    if idx >= 0:
                        item.setdefault("contexts", []).append(
                            {"site": s, "ctx": re.sub(r"\s+", " ", body[max(0, idx - 200): idx + 300])}
                        )
            except Exception as exc:  # noqa: BLE001
                item["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
            finally:
                if page is not None:
                    try:
                        await page.close()
                    except Exception:
                        pass
            results.append(item)
            print(forum, json.dumps({k: v for k, v in item.items() if k != "contexts"},
                                    ensure_ascii=False)[:600])
            for c in item.get("contexts", []):
                print("   CTX", c["site"], ":", c["ctx"][:260])
        await ctx.close()

    (OUT / "mirror_render_294.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


asyncio.run(main())
