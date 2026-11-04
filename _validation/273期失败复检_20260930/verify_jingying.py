"""只读复检第二轮：精英战队记录是否真实不存在（区分异常/无数据）。"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

PROFILE = Path(__file__).resolve().parents[2] / "browser-profile"
BASE = "https://buzsxio.821n4-hgj04-edkrft.xyz:29455"
TARGET_ID = "6a4e865857dc857ae1c13534"
PAGE = f"{BASE}/article/manager/{TARGET_ID}?url=bxj"

PROBE_APIS = [
    f"{BASE}/api/proxy/manager-articles",
    f"{BASE}/api/proxy/manager-articles?url=bxj",
    f"{BASE}/api/proxy/landing-page-data?url=bxj",
    f"{BASE}/api/proxy/site-config?url=bxj",
]


async def main() -> None:
    out: dict = {"page_body": "", "page_status_note": "", "api": [], "listing_hits": []}
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(PROFILE), headless=True, viewport={"width": 1280, "height": 2600}
        )
        page = await ctx.new_page()
        await page.goto(PAGE, wait_until="domcontentloaded", timeout=45000)
        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        await page.wait_for_timeout(2500)
        out["page_body"] = (await page.locator("body").inner_text())[:600]

        for api in PROBE_APIS:
            res = await page.evaluate(
                """async (u) => {
                    try {
                        const r = await fetch(u, {credentials:'include'});
                        const t = await r.text();
                        return {status: r.status, len: t.length, head: t.slice(0,160),
                                hasTargetId: t.includes('6a4e865857dc857ae1c13534'),
                                hasName: t.includes('精英战队')};
                    } catch (e) { return {status:-1, err:String(e)}; }
                }""",
                api,
            )
            out["api"].append({"url": api, **res})

        # 站点首页/列表页里是否还挂着「精英战队」
        await page.goto(f"{BASE}/?url=bxj", wait_until="domcontentloaded", timeout=45000)
        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        await page.wait_for_timeout(2500)
        for _ in range(8):
            await page.mouse.wheel(0, 1400)
            await page.wait_for_timeout(200)
        body = await page.locator("body").inner_text()
        html = await page.content()
        out["listing_hits"] = {
            "root_body_len": len(body),
            "name_in_body": "精英战队" in body,
            "name_in_html": "精英战队" in html,
            "target_id_in_html": TARGET_ID in html,
        }
        await ctx.close()
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
