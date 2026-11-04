# -*- coding: utf-8 -*-
"""读取六玄网新域名渲染后的 iframe 内容，找「综合绝杀」正文与最新期号（只读）。"""
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
BASE = "https://ulgvaugz.1vh1x-5fer6-nlzydr.work:17455/"
PERIOD = 292


async def main() -> None:
    from playwright.async_api import async_playwright

    info: dict[str, object] = {}
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(browser_profile_dir()),
            headless=True,
            viewport={"width": 1280, "height": 2600},
            ignore_https_errors=True,
        )
        page = await ctx.new_page()
        await page.goto(BASE, wait_until="domcontentloaded", timeout=45000)
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await page.wait_for_timeout(3000)

        frames = []
        for frame in page.frames:
            try:
                text = await frame.locator("body").inner_text()
            except Exception:
                continue
            frames.append({"url": frame.url, "len": len(text), "text": text})
        info["frames"] = [{"url": f["url"], "len": f["len"]} for f in frames]
        for i, f in enumerate(frames):
            (OUT / f"liuxuan_new_frame{i}.txt").write_text(f["text"], encoding="utf-8")

        # 在所有 frame 里找综合绝杀区块
        for f in frames:
            text = f["text"]
            if "综合绝杀" not in text and "绝杀" not in text:
                continue
            periods = sorted({int(x) for x in re.findall(r"(?<!\d)(\d{2,4})\s*期", text)})
            hit = {
                "frame": f["url"],
                "len": f["len"],
                "periods_tail": periods[-8:],
                "has_292": PERIOD in periods,
                "has_anchor": "综合绝杀" in text,
            }
            idx = text.find("综合绝杀")
            if idx >= 0:
                hit["context"] = re.sub(r"\s+", " ", text[max(0, idx - 150): idx + 700])
            info.setdefault("hits", []).append(hit)
            print(json.dumps(hit, ensure_ascii=False)[:900])

        await ctx.close()

    (OUT / "liuxuan_new_frames.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
    )


asyncio.run(main())
