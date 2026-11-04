"""只读复检 276 期失败站「傻傻熊二」第 4 路：绕过浏览器缓存重取帖页，看作者历史是否已有 276 行。不写任何正式文件。"""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "browser-profile"
OUT = Path(__file__).parent
URL = "https://ihdfsxo.kgqq8-mbcz5-qpbkfh.xyz:16677/topic/258481.html"
PERIOD_RE = re.compile(r"2[0-9]{2}\s*期")


async def render(pw, *, bust: bool, use_profile: bool) -> dict:
    rec: dict = {"bust": bust, "use_profile": use_profile}
    url = f"{URL}?v={int(time.time())}" if bust else URL
    if use_profile:
        ctx = await pw.chromium.launch_persistent_context(
            str(PROFILE), headless=True, viewport={"width": 1400, "height": 2400}
        )
    else:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1400, "height": 2400})
    try:
        if bust:
            await ctx.set_extra_http_headers({"Cache-Control": "no-cache", "Pragma": "no-cache"})
            await ctx.route(
                "**/*",
                lambda route: route.continue_(headers={**route.request.headers, "cache-control": "no-cache"}),
            )
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        await page.wait_for_timeout(3000)
        body = await page.locator("body").inner_text()
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        pl = [ln for ln in lines if PERIOD_RE.search(ln)]
        rec["body_len"] = len(body)
        rec["author_hits"] = body.count("傻傻熊二")
        rec["has_276qi"] = "276期" in body
        rec["has_276_line"] = any(re.match(r"276\s*期", ln) for ln in lines)
        rec["tail_period_lines"] = pl[-8:]
        rec["first_period_lines"] = pl[:3]
        rec["hits_276"] = [ln for ln in lines if "276" in ln][:8]
        (OUT / f"recheck_{'bust' if bust else 'plain'}_{'prof' if use_profile else 'fresh'}.txt").write_text(
            body, encoding="utf-8"
        )
    except Exception as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        await ctx.close()
    return rec


async def main() -> None:
    out = []
    async with async_playwright() as pw:
        out.append(await render(pw, bust=False, use_profile=True))
        out.append(await render(pw, bust=True, use_profile=False))
    (OUT / "probe_recheck_out.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
