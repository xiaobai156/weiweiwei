"""只读复检 275 期失败站「潇洒人生」：浏览器渲染 + 原始 HTML 双路取证据。不写任何正式文件。"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "browser-profile"
OUT = Path(__file__).parent

URL = "https://0130190827.767566.xyz/bbs/topic.php?id=30780"
PERIOD_RE = re.compile(r"2[0-9]{2}\s*期")


async def main() -> None:
    out: dict = {"url": URL, "period_lines": [], "raw_period_hits": {}, "requests": []}
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(PROFILE), headless=True, viewport={"width": 1400, "height": 2600}
        )
        page = await ctx.new_page()

        def on_response(resp):
            u = resp.url
            if "view-source" in u:
                return
            ct = (resp.headers or {}).get("content-type", "")
            if "topic.php" in u or "html" in ct:
                out["requests"].append({"url": u, "status": resp.status, "ct": ct})

        page.on("response", on_response)
        try:
            await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            try:
                await page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass
            await page.wait_for_timeout(2500)
            for _ in range(8):
                await page.mouse.wheel(0, 1500)
                await page.wait_for_timeout(250)
            out["title"] = await page.title()
            body = await page.locator("body").inner_text()
            out["body_len"] = len(body)
            out["period_lines"] = [ln.strip() for ln in body.splitlines() if PERIOD_RE.search(ln)][
                :60
            ]
            out["has_275"] = "275" in body
            out["tail_lines"] = [
                ln.strip() for ln in body.splitlines() if ln.strip()
            ][:40]
            # 原始 HTML（未经 JS 渲染）
            raw = await page.evaluate(
                """async (u) => {
                    const r = await fetch(u, {credentials:'include'});
                    const t = await r.text();
                    return {status: r.status, len: t.length, text: t.slice(0, 200000)};
                }""",
                URL,
            )
            out["raw_status"] = raw["status"]
            out["raw_len"] = raw["len"]
            out["raw_has_275"] = "275" in raw["text"]
            for m in re.finditer(r".{0,60}2[0-9]{2}\s*期.{0,120}", raw["text"]):
                s = m.group(0)
                if s not in out["raw_period_hits"]:
                    out["raw_period_hits"][s] = 1
            out["raw_period_hits"] = list(out["raw_period_hits"])[:30]
            out["raw_head"] = raw["text"][:1500]
        except Exception as exc:
            out["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            await ctx.close()

    (OUT / "probe_xiaosa_out.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in out.items() if k != "raw_head"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
