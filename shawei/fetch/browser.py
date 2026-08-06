from __future__ import annotations

import asyncio
import re
from urllib.parse import urlparse

from shawei.fetch.http_client import RENDER_CACHE, RENDER_STATUS, RUNTIME_CACHE_LOCK


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def render_browser_documents(url: str, timeout: int = 20) -> list[str]:
    cache_key = (url, int(timeout))
    with RUNTIME_CACHE_LOCK:
        cached = RENDER_CACHE.get(cache_key)
        if cached is not None:
            return list(cached)

    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        with RUNTIME_CACHE_LOCK:
            RENDER_STATUS[cache_key] = f"Playwright不可用({type(exc).__name__}: {exc})"
        return []

    render_errors: list[str] = []

    async def _render() -> list[str]:
        browser = None
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": 1280, "height": 2600})
                wait_ms = max(5000, int(timeout * 1000))
                await page.goto(url, wait_until="domcontentloaded", timeout=wait_ms)
                try:
                    await page.wait_for_load_state("networkidle", timeout=min(wait_ms, 15000))
                except Exception:
                    pass
                await page.wait_for_timeout(1200)
                if "/references/" in (urlparse(url).fragment or ""):
                    try:
                        await page.get_by_text(re.compile(r"\d+\s*期\s*绝杀一尾")).first.click(timeout=3000)
                        try:
                            await page.wait_for_load_state("networkidle", timeout=min(wait_ms, 15000))
                        except Exception:
                            pass
                        await page.wait_for_timeout(1200)
                    except Exception:
                        pass
                for _ in range(6):
                    await page.mouse.wheel(0, 1400)
                    await page.wait_for_timeout(200)
                return [await page.locator("body").inner_text(), await page.content()]
        except Exception as exc:
            render_errors.append(f"{type(exc).__name__}: {exc}")
            return []
        finally:
            if browser is not None:
                await browser.close()

    rendered = [item for item in _run_async(_render()) if item]
    if rendered:
        with RUNTIME_CACHE_LOCK:
            RENDER_CACHE[cache_key] = list(rendered)
            RENDER_STATUS[cache_key] = "ok"
    else:
        with RUNTIME_CACHE_LOCK:
            RENDER_STATUS[cache_key] = "浏览器渲染为空" + (f"({render_errors[-1]})" if render_errors else "")
    return rendered


def is_root_page_url(url: str) -> bool:
    path = urlparse(url).path.strip()
    return path in {"", "/"}
