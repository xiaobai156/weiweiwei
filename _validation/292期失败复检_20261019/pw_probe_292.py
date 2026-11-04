"""292 期失败站浏览器直探：记录最终落地 URL、标题、正文里是否有站点名与 292 期。"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.fetch.browser import browser_profile_dir  # noqa: E402

OUT = Path(__file__).resolve().parent

TARGETS = [
    ("龙凤呈祥", "https://tulprhfc.wghcb-bnmgm-hyymaz.work:16655/topic/324698.html"),
    ("可怜春天", "https://jogavu.6bl6s-ilo1w-yfnvvl.work:16677/topic/678625.html"),
    ("正气凛然", "https://whsbrmz.qclrc-4mk42-vnxbyg.work:16677/topic/248009.html"),
    ("违背烟蒂", "https://tulprhfc.wghcb-bnmgm-hyymaz.work:16655/topic/305414.html"),
    ("清清淡淡", "https://iboatq.pjgpm-epbf7-lxpezb.work:16677/topic/324703.html"),
    ("故里春意", "https://zdwcig.iyo4d-81klf-udwkqg.work:16677/topic/350485.html"),
    ("八面驶风", "https://pvxiftuf.yumkw-u4s81-hpytyz.work:16677/topic/559099.html"),
    ("六玄网", "https://lx11.www87127b.com:8443/#87127"),
    ("昙花一现", "https://www.www144344.com/read.php?tid=1904"),
]


async def main() -> None:
    from playwright.async_api import async_playwright

    results = []
    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            str(browser_profile_dir()),
            headless=True,
            viewport={"width": 1280, "height": 2600},
            ignore_https_errors=True,
        )
        for name, url in TARGETS:
            item = {"name": name, "url": url}
            page = None
            try:
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                await page.wait_for_timeout(2500)
                for _ in range(4):
                    await page.mouse.wheel(0, 1400)
                    await page.wait_for_timeout(300)
                body = await page.locator("body").inner_text()
                content = await page.content()
                item["final_url"] = page.url
                item["title"] = await page.title()
                item["body_len"] = len(body)
                item["has_name_body"] = name in body
                item["has_name_html"] = name in content
                item["has_292_body"] = "292" in body
                item["has_292_html"] = "292" in content
                idx = body.find(name)
                if idx >= 0:
                    item["name_context"] = body[max(0, idx - 200): idx + 300]
                (OUT / f"pw_{name}.txt").write_text(body, encoding="utf-8")
            except Exception as exc:
                item["error"] = f"{type(exc).__name__}: {exc}"
            finally:
                if page is not None:
                    try:
                        await page.close()
                    except Exception:
                        pass
            results.append(item)
            print(name, json.dumps({k: v for k, v in item.items() if k != "name_context"},
                                   ensure_ascii=False))
            if item.get("name_context"):
                print("   CTX:", item["name_context"].replace("\n", " | ")[:400])
        await context.close()

    (OUT / "pw_292.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


asyncio.run(main())
