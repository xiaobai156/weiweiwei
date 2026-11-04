"""只读复检 276 期失败站「傻傻熊二」第 3 路：首页该站条目指向的 topic URL 与相邻站点条目。不写任何正式文件。"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "browser-profile"
OUT = Path(__file__).parent
HOME = "https://ihdfsxo.kgqq8-mbcz5-qpbkfh.xyz:16677/"


async def main() -> None:
    out: dict = {"home": HOME}
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(PROFILE), headless=True, viewport={"width": 1400, "height": 2600}
        )
        page = await ctx.new_page()
        await page.goto(HOME, wait_until="domcontentloaded", timeout=60000)
        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        await page.wait_for_timeout(3000)
        html = await page.content()
        (OUT / "rendered_home.html").write_text(html, encoding="utf-8")
        out["html_len"] = len(html)
        out["author_occurrences"] = html.count("傻傻熊二")

        # 1) 精确抓取含「傻傻熊二」的 <a> 锚点
        anchors = await page.eval_on_selector_all(
            "a",
            """els => els.map(e => ({href: e.href, text: (e.innerText||'').replace(/\\s+/g,' ').trim().slice(0,80)}))""",
        )
        out["xiong_anchors"] = [a for a in anchors if "傻傻熊二" in a["text"] or "258481" in a["href"]]
        out["xiong_anchors_all"] = [a for a in anchors if "熊二" in a["text"] or "熊二" in a["href"]]
        out["total_anchors"] = len(anchors)
        out["anchors_276"] = [a for a in anchors if a["text"].startswith("276")][:40]
        out["anchors_275"] = [a for a in anchors if a["text"].startswith("275")][:40]

        # 2) 顺带列出 /topic/ 链接里 id 最大的 10 个
        ids = []
        for a in anchors:
            m = re.search(r"/topic/(\d+)\.html", a["href"])
            if m:
                ids.append((int(m.group(1)), a["href"], a["text"][:60]))
        out["topic_id_max"] = sorted(ids, reverse=True)[:15]
        out["topic_id_count"] = len(ids)
        await ctx.close()

    (OUT / "probe_home_link_out.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in out.items()}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
