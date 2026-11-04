"""只读复检 276 期失败站「傻傻熊二」：浏览器渲染 + 网络请求双路取证据。不写任何正式文件。"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "browser-profile"
OUT = Path(__file__).parent

URL = "https://ihdfsxo.kgqq8-mbcz5-qpbkfh.xyz:16677/topic/258481.html"
PERIOD_RE = re.compile(r"2[0-9]{2}\s*期")


async def main() -> None:
    out: dict = {"url": URL, "period_lines": [], "requests": []}
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(PROFILE), headless=True, viewport={"width": 1400, "height": 2600}
        )
        page = await ctx.new_page()

        def on_response(resp):
            u = resp.url
            ct = (resp.headers or {}).get("content-type", "")
            if "view-source" in u:
                return
            if "/topic/" in u or "html" in ct or "json" in ct or "api" in u.lower():
                out["requests"].append({"url": u, "status": resp.status, "ct": ct})

        page.on("response", on_response)
        try:
            await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            try:
                await page.wait_for_load_state("networkidle", timeout=25000)
            except Exception:
                pass
            await page.wait_for_timeout(3000)
            for _ in range(8):
                await page.mouse.wheel(0, 1500)
                await page.wait_for_timeout(250)
            out["title"] = await page.title()
            body = await page.locator("body").inner_text()
            out["body_len"] = len(body)
            (OUT / "rendered_body_258481.txt").write_text(body, encoding="utf-8")
            lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
            out["body_lines"] = len(lines)
            out["period_lines"] = [ln for ln in lines if PERIOD_RE.search(ln)][:60]
            out["has_276"] = "276" in body
            out["has_276qi"] = "276期" in body
            out["has_author"] = "傻傻熊二" in body
            out["hints"] = {
                kw: body.count(kw)
                for kw in ("下架", "不存在", "删除", "无权", "购买", "登录", "注册", "已关闭", "错误")
                if kw in body
            }
            out["head_lines"] = lines[:25]
            out["tail_lines"] = lines[-25:]
            html = await page.content()
            (OUT / "rendered_258481.html").write_text(html, encoding="utf-8")
            out["html_len"] = len(html)
            out["html_period_hits"] = list(
                dict.fromkeys(re.findall(r"2[0-9]{2}\s*期[^<\n]{0,80}", html))
            )[:30]
            out["links"] = sorted(
                {a for a in await page.eval_on_selector_all("a", "els => els.map(e => e.href)")}
            )[:60]
        except Exception as exc:
            out["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            await ctx.close()

    (OUT / "probe_shasha_out.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
