"""只读复检 276 期失败站「傻傻熊二」第 2 路：站点首页作者索引 + 相邻 topic id。不写任何正式文件。"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "browser-profile"
OUT = Path(__file__).parent

HOST = "https://ihdfsxo.kgqq8-mbcz5-qpbkfh.xyz:16677"
TARGETS = [f"{HOST}/", f"{HOST}/index.html", f"{HOST}/topic/258480.html", f"{HOST}/topic/258482.html"]
PERIOD_RE = re.compile(r"2[0-9]{2}\s*期")


async def grab(page, url):
    rec = {"url": url}
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        rec["status"] = resp.status if resp else None
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await page.wait_for_timeout(2500)
        body = await page.locator("body").inner_text()
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        rec["title"] = await page.title()
        rec["body_len"] = len(body)
        rec["has_target_author"] = "傻傻熊二" in body
        rec["period_lines"] = [ln for ln in lines if PERIOD_RE.search(ln)][:80]
        rec["xiong_lines"] = [ln for ln in lines if "熊二" in ln][:20]
        rec["head30"] = lines[:30]
        rec["has_276qi"] = "276期" in body
        rec["topic_links"] = sorted(
            {
                a
                for a in await page.eval_on_selector_all("a", "els => els.map(e => e.href)")
                if "/topic/" in a
            }
        )[:40]
    except Exception as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
    return rec


async def main() -> None:
    out: list[dict] = []
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(PROFILE), headless=True, viewport={"width": 1400, "height": 2600}
        )
        page = await ctx.new_page()
        for url in TARGETS:
            out.append(await grab(page, url))
        await ctx.close()
    (OUT / "probe_index_out.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    for rec in out:
        print("=" * 70)
        print(rec.get("url"), "status", rec.get("status"), "title", rec.get("title"),
              "len", rec.get("body_len"), "author?", rec.get("has_target_author"),
              "276期?", rec.get("has_276qi"), rec.get("error", ""))
        print("xiong_lines:", rec.get("xiong_lines"))
        print("period_lines[:25]:", rec.get("period_lines", [])[:25])
        print("head30:", rec.get("head30", [])[:12])
        print("topic_links:", rec.get("topic_links", [])[:12])


if __name__ == "__main__":
    asyncio.run(main())
