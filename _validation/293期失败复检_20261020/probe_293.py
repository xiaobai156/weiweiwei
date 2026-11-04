# -*- coding: utf-8 -*-
"""293 期两个失败站只读验证：赤兔 / 昙花一现，确认站方是否已发布 293 期。

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
PERIOD = 293
PERIOD_RE = re.compile(r"(?<!\d)(\d{2,4})\s*期")

TARGETS = [
    ("赤兔", "https://zwpwuwq.fxnb4-uer1b-uftjcw.work:16677/#am", "top"),
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
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                await page.wait_for_timeout(3000)
                body = await page.locator("body").inner_text()
                item["final_url"] = page.url
                item["body_len"] = len(body)
                item["name_hit"] = name in body
                periods = sorted({int(x) for x in PERIOD_RE.findall(body)})
                item["periods_tail"] = periods[-8:]
                item["has_293"] = PERIOD in periods
                item["max_period"] = periods[-1] if periods else None
                # 抓 293 / 292 附近原文
                ctxs = []
                for p in (PERIOD, PERIOD - 1):
                    for m in re.finditer(rf"(?<!\d){p}\s*期", body):
                        s = m.start()
                        ctxs.append(re.sub(r"\s+", " ", body[max(0, s - 120): s + 300]))
                        break
                item["contexts"] = ctxs
                (OUT / f"pw_{name}_293.txt").write_text(body, encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                item["error"] = f"{type(exc).__name__}: {exc}"
            finally:
                if page is not None:
                    try:
                        await page.close()
                    except Exception:
                        pass
            results.append(item)
            print(name, json.dumps({k: v for k, v in item.items() if k != "contexts"}, ensure_ascii=False))
            for c in item.get("contexts", []):
                print("   CTX:", c[:300])
        await ctx.close()

    (OUT / "probe_293.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


import asyncio  # noqa: E402

asyncio.run(main())
