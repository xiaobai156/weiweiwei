"""只读复检 273 期两站：浏览器验证 + 专属接口状态。不写任何正式文件。"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from playwright.async_api import async_playwright

PROFILE = Path(__file__).resolve().parents[2] / "browser-profile"

TARGETS = {
    "千祥云集": {
        "url": "https://dfgrufao.tz0ex-y6o7v-lazxsq.work:29400/article/admin/6a041b804ea5c20141013dc8?url=lbw",
        "id": "6a041b804ea5c20141013dc8",
        "kind": "admin",
    },
    "精英战队": {
        "url": "https://buzsxio.821n4-hgj04-edkrft.xyz:29455/article/manager/6a4e865857dc857ae1c13534?url=bxj",
        "id": "6a4e865857dc857ae1c13534",
        "kind": "manager",
    },
}

PERIOD_RE = re.compile(r"27[0-9]\s*期")


def api_urls(base: str, kind: str, article_id: str) -> list[str]:
    origin = base.split("/article/")[0]
    return [
        f"{origin}/api/proxy/admin-articles/{article_id}",
        f"{origin}/api/proxy/manager-articles/{article_id}",
    ]


async def check(name: str, info: dict) -> dict:
    out = {"name": name, "url": info["url"], "api": [], "period_lines": [], "title": "", "body_len": 0, "error": ""}
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(PROFILE), headless=True, viewport={"width": 1280, "height": 2600}
        )
        page = await ctx.new_page()
        try:
            await page.goto(info["url"], wait_until="domcontentloaded", timeout=45000)
            try:
                await page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass
            await page.wait_for_timeout(2000)
            for _ in range(6):
                await page.mouse.wheel(0, 1400)
                await page.wait_for_timeout(250)
            body = await page.locator("body").inner_text()
            out["body_len"] = len(body)
            out["title"] = await page.title()
            out["period_lines"] = [ln.strip() for ln in body.splitlines() if PERIOD_RE.search(ln)][:40]
            for api in api_urls(info["url"], info["kind"], info["id"]):
                try:
                    res = await page.evaluate(
                        """async (u) => {
                            try {
                                const r = await fetch(u, {credentials:'include'});
                                const t = await r.text();
                                return {status: r.status, len: t.length, head: t.slice(0, 120),
                                        hasId: t.includes(u.split('/').pop())};
                            } catch (e) { return {status: -1, err: String(e)}; }
                        }""",
                        api,
                    )
                except Exception as exc:
                    res = {"status": -2, "err": f"{type(exc).__name__}: {exc}"}
                out["api"].append({"url": api, **res})
        except Exception as exc:
            out["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            await ctx.close()
    return out


async def main() -> None:
    results = [await check(name, info) for name, info in TARGETS.items()]
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
