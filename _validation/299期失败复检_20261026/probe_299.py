# -*- coding: utf-8 -*-
"""299 期 2 个失败站只读验证：浏览器渲染，判断异常/无数据（只读）。"""
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
PERIOD = 299
TARGETS = [
    ("赴火蹈刃", "https://sqddimfu.evs71-kia2b-gshsdc.xyz:16677/topic/219850.html"),
    ("物产丰富", "https://8818.www19753a.com/read.php?tid=501"),
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
                item["has_299"] = PERIOD in periods
                item["max"] = periods[-1] if periods else None
                (OUT / f"pw_{name}_299.txt").write_text(body, encoding="utf-8")
                rows = [
                    re.sub(r"\s+", " ", ln)[:120]
                    for ln in body.splitlines()
                    if re.search(r"(?<!\d)(29[7-9])\s*期", ln)
                ]
                item["rows"] = rows[:8]
                if item["removed"]:
                    item["verdict"] = "无数据(帖子下架)"
                elif item["has_299"]:
                    item["verdict"] = "可救(有299期)"
                elif periods:
                    item["verdict"] = f"无数据(最新{periods[-1]}期)"
                else:
                    item["verdict"] = "异常(无期数)"
            except Exception as exc:  # noqa: BLE001
                item["error"] = f"{type(exc).__name__}: {str(exc)[:110]}"
                item["verdict"] = "异常(打不开)"
            results.append(item)
            print(f"{name:6s} {item['verdict']:16s} len={item.get('len')} "
                  f"期数={item.get('periods_tail')} {item.get('error','')[:60]}")
            for r in item.get("rows", []):
                print("   ", r)
        await ctx.close()

    (OUT / "probe_299.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


asyncio.run(main())
