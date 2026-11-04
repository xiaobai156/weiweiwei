# -*- coding: utf-8 -*-
"""297 期 3 个失败站只读验证：浏览器渲染，判断异常/无数据/可救（只读）。"""
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
PERIOD = 297

TARGETS = [
    ("赛马会", "https://ugtzszfp.ldpiz-8xhrd-wpkjkn.xyz:16677/topic/573703.html"),
    ("翻本行动", "https://drxgkjt.uu1oc-eyjpt-uxyccu.xyz:29400/article/manager/6a33e58fdfa16552b923d27f?url=jyb"),
    ("再度归来", "https://0130190827.673454.xyz/bbs/topic.php?id=20330"),
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
        page = await ctx.new_page()
        for name, url in TARGETS:
            item = {"name": name, "url": url}
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(2500)
                body = await page.inner_text("body")
                item["len"] = len(body)
                item["name_hit"] = name in body
                item["removed"] = "此帖子ID已被下架" in body or "已被删除" in body
                periods = sorted({int(x) for x in re.findall(r"(?<!\d)(\d{2,4})\s*期", body)})
                item["periods_tail"] = periods[-6:]
                item["has_297"] = PERIOD in periods
                item["max"] = periods[-1] if periods else None
                if item["removed"]:
                    item["verdict"] = "无数据(帖子下架)"
                elif item["has_297"]:
                    m = re.search(rf"{PERIOD}期[^\n]{{0,150}}", body)
                    item["row297"] = re.sub(r"\s+", " ", m.group(0))[:150] if m else None
                    item["verdict"] = "可救(有297期)"
                elif periods:
                    item["verdict"] = f"无数据(最新{periods[-1]}期)"
                else:
                    item["verdict"] = "异常(无期数)"
                (OUT / f"pw_{name}_297.txt").write_text(body, encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                item["error"] = f"{type(exc).__name__}: {str(exc)[:110]}"
                item["verdict"] = "异常(打不开)"
            results.append(item)
            print(f"{name:6s} {item['verdict']:18s} len={item.get('len')} "
                  f"期数={item.get('periods_tail')} | {item.get('row297') or item.get('error','')[:90]}")
        await ctx.close()

    (OUT / "probe_297.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


asyncio.run(main())
