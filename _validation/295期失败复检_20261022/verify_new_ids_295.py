# -*- coding: utf-8 -*-
"""验证 7 个站的新帖子 ID：浏览器渲染 + 取 295 期值，核对站名/方向（只读）。

每站给出候选新 ID，逐一验证；确认能取到 295 期合法尾数。
"""
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

# 站名 -> [(论坛base, 新tid, 说明)]
CANDIDATES = {
    "再度归来": [("https://0130190827.673454.xyz", "20330", "绝杀二尾")],
    "童颜鹤发": [("https://67806780827.325346.xyz", "19581", "绝杀①尾")],
    "澳彩碼王": [("https://12388990827.794555.xyz", "19959", "绝杀①尾")],
    "寻宝探码": [("https://12388990827.688756.xyz", "19155", "绝杀①尾")],
    "财源滚滚": [("https://12388990827.688756.xyz", "19128", "绝杀①尾")],
    "海角天涯": [("https://88888020827.997595.xyz", "19471", "绝杀①尾")],
    # 一心为民：论坛里大量同名是"推荐人"，需专门找 绝杀一尾 栏目的帖
    "一心为民": [],
}

TAIL_RE = re.compile(r"绝杀[①1一]?尾[^\[]*\[([0-9.、\s]+)\]")


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
        for name, cands in CANDIDATES.items():
            if not cands:
                continue
            for base, tid, note in cands:
                url = f"{base}/bbs/topic.php?id={tid}"
                item = {"name": name, "url": url, "tid": tid, "note": note}
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    await page.wait_for_timeout(2500)
                    body = await page.inner_text("body")
                    item["len"] = len(body)
                    item["name_hit"] = name in body
                    item["removed"] = "此帖子ID已被下架" in body
                    # 295 期那一行
                    m = re.search(rf"{PERIOD}期[^\n]{{0,160}}", body)
                    item["row295"] = re.sub(r"\s+", " ", m.group(0))[:160] if m else None
                    if item["row295"]:
                        tails = re.findall(r"[【\[]([0-9.、]+)[】\]]", item["row295"])
                        item["tails"] = tails
                    item["verdict"] = (
                        "OK" if (item["row295"] and item["name_hit"] and not item["removed"])
                        else ("下架" if item["removed"] else "异常")
                    )
                    (OUT / f"new_{name}_{tid}.txt").write_text(body, encoding="utf-8")
                except Exception as exc:  # noqa: BLE001
                    item["error"] = f"{type(exc).__name__}: {str(exc)[:110]}"
                    item["verdict"] = "打不开"
                results.append(item)
                print(f"{name:6s} id={tid:6s} {item['verdict']:4s} "
                      f"| {item.get('row295') or item.get('error','')}")
        await ctx.close()

    (OUT / "new_ids_verify_295.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


asyncio.run(main())
