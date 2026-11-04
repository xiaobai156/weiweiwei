"""小明哥上/可见一斑 渲染崩溃定位：分步记录 goto / networkidle / wait / scroll 哪一步崩。"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.fetch.browser import browser_profile_dir  # noqa: E402

OUT = Path(__file__).resolve().parent
URLS = [
    ("小明哥上", "https://gboqrz.sm0a0-x9x2c-xyvjdr.work/topic/172572.html"),
    ("可见一斑", "https://gboqrz.sm0a0-x9x2c-xyvjdr.work/topic/241106.html"),
]


async def probe(context, name: str, url: str) -> dict:
    info: dict[str, object] = {"name": name}
    page = None
    try:
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        info["goto"] = "ok"
        try:
            body = await page.locator("body").inner_text()
            info["body_after_goto"] = len(body)
            info["has_292_after_goto"] = "292" in body
        except Exception as exc:
            info["body_after_goto_error"] = f"{type(exc).__name__}: {exc}"
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
            info["networkidle"] = "ok"
        except Exception as exc:
            info["networkidle"] = f"{type(exc).__name__}: {exc}"
        try:
            await page.wait_for_timeout(1200)
            info["wait"] = "ok"
        except Exception as exc:
            info["wait"] = f"{type(exc).__name__}: {exc}"
        try:
            body = await page.locator("body").inner_text()
            info["body_after_wait"] = len(body)
            info["has_292_after_wait"] = "292" in body
            (OUT / f"pw2_{name}.txt").write_text(body, encoding="utf-8")
        except Exception as exc:
            info["body_after_wait_error"] = f"{type(exc).__name__}: {exc}"
        for i in range(6):
            try:
                await page.mouse.wheel(0, 1400)
                await page.wait_for_timeout(200)
            except Exception as exc:
                info[f"scroll_{i}"] = f"{type(exc).__name__}: {exc}"
                break
        else:
            info["scroll"] = "ok"
    except Exception as exc:
        info["fatal"] = f"{type(exc).__name__}: {exc}"
    finally:
        if page is not None:
            try:
                await page.close()
            except Exception:
                pass
    return info


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
        for name, url in URLS:
            results.append(await probe(context, name, url))
        await context.close()
    for item in results:
        print(json.dumps(item, ensure_ascii=False))
    (OUT / "pw2_292.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


asyncio.run(main())
