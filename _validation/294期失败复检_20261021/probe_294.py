# -*- coding: utf-8 -*-
"""294 期失败站只读验证：11 站浏览器渲染 + 期数/站名核查。

只读：不写正式 TXT、不写缓存、不改配置。
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
PERIOD = 294
PERIOD_RE = re.compile(r"(?<!\d)(\d{2,4})\s*期")

TARGETS = [
    ("坚持战斗", "https://1214.775486.xyz/bbs/topic.php?id=20200", "bottom"),
    ("无量寿佛", "https://1214.775486.xyz/bbs/topic.php?id=20198", "bottom"),
    ("再度归来", "https://0130190827.673454.xyz/bbs/topic.php?id=20144", "bottom"),
    ("童颜鹤发", "https://67806780827.325346.xyz/bbs/topic.php?id=19812", "bottom"),
    ("一心为民", "https://88888020827.983654.xyz/bbs/topic.php?id=20758", "bottom"),
    ("怪咖小生", "https://0130190827.657954.xyz/bbs/topic.php?id=20210", "bottom"),
    ("澳彩碼王", "https://12388990827.794555.xyz/bbs/topic.php?id=21353", "bottom"),
    ("寻宝探码", "https://12388990827.688756.xyz/bbs/topic.php?id=18520", "bottom"),
    ("财源滚滚", "https://12388990827.688756.xyz/bbs/topic.php?id=19930", "bottom"),
    ("海角天涯", "https://88888020827.997595.xyz/bbs/topic.php?id=18490", "bottom"),
    ("昙花一现", "http://38.177.253.132:31882/read.php?tid=1904", "bottom"),
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
        for name, url, pick in TARGETS:
            item = {"name": name, "url": url, "pick": pick}
            page = None
            try:
                page = await ctx.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=40000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=12000)
                except Exception:
                    pass
                await page.wait_for_timeout(2500)
                body = await page.locator("body").inner_text()
                item["final_url"] = page.url
                item["body_len"] = len(body)
                item["name_hit"] = name in body
                periods = sorted({int(x) for x in PERIOD_RE.findall(body)})
                item["periods_tail"] = periods[-8:]
                item["has_target"] = PERIOD in periods
                item["max_period"] = periods[-1] if periods else None
                (OUT / f"pw_{name}.txt").write_text(body, encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                item["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
            finally:
                if page is not None:
                    try:
                        await page.close()
                    except Exception:
                        pass
            results.append(item)
            print(name, json.dumps(item, ensure_ascii=False)[:300])
        await ctx.close()

    (OUT / "probe_294.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


import asyncio  # noqa: E402

asyncio.run(main())
