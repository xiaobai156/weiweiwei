from __future__ import annotations

import atexit
import asyncio
import re
import threading
from dataclasses import dataclass
from urllib.parse import urlparse

from shawei.fetch.http_client import RENDER_CACHE, RENDER_STATUS, RUNTIME_CACHE_LOCK


RENDER_FLIGHTS: dict[tuple[str, int], threading.Event] = {}
RENDER_FLIGHTS_LOCK = threading.Lock()
_BROWSER_RUNTIME: "_BrowserRuntime | None" = None
_BROWSER_RUNTIME_LOCK = threading.Lock()


@dataclass(frozen=True)
class BrowserRenderOptions:
    wait_for_network_idle: bool = True
    post_load_wait_ms: int = 1200
    scroll_count: int = 6
    scroll_wait_ms: int = 200

    def __post_init__(self) -> None:
        for name, value in (
            ("post_load_wait_ms", self.post_load_wait_ms),
            ("scroll_count", self.scroll_count),
            ("scroll_wait_ms", self.scroll_wait_ms),
        ):
            if value < 0:
                raise ValueError(f"{name}不能为负数")


class _BrowserRuntime:
    def __init__(self) -> None:
        self._ready = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._startup_error: BaseException | None = None
        self._playwright = None
        self._browser = None
        self._context = None
        self._thread = threading.Thread(
            target=self._thread_main,
            name="shawei-playwright-runtime",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(30):
            raise RuntimeError("Playwright运行时启动超时")
        if self._startup_error is not None:
            raise self._startup_error

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._start())
        except BaseException as exc:
            self._startup_error = exc
            self._ready.set()
            loop.run_until_complete(self._close_resources())
            loop.close()
            return
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(self._close_resources())
            loop.close()

    async def _start(self) -> None:
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 2600}
        )

    async def _close_resources(self) -> None:
        context, self._context = self._context, None
        browser, self._browser = self._browser, None
        playwright, self._playwright = self._playwright, None
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass
        if playwright is not None:
            try:
                await playwright.stop()
            except Exception:
                pass

    async def _render_page(
        self,
        url: str,
        timeout: int,
        options: BrowserRenderOptions | None = None,
    ) -> tuple[list[str], str]:
        page = None
        options = options or BrowserRenderOptions()
        try:
            context = self._context
            if context is None:
                raise RuntimeError("Playwright Context未初始化")
            page = await context.new_page()
            wait_ms = max(5000, int(timeout * 1000))
            await page.goto(url, wait_until="domcontentloaded", timeout=wait_ms)
            if options.wait_for_network_idle:
                try:
                    await page.wait_for_load_state("networkidle", timeout=min(wait_ms, 15000))
                except Exception:
                    pass
            await page.wait_for_timeout(options.post_load_wait_ms)
            if "/references/" in (urlparse(url).fragment or ""):
                try:
                    await page.get_by_text(re.compile(r"\d+\s*期\s*绝杀一尾")).first.click(
                        timeout=3000
                    )
                    try:
                        await page.wait_for_load_state(
                            "networkidle", timeout=min(wait_ms, 15000)
                        )
                    except Exception:
                        pass
                    await page.wait_for_timeout(1200)
                except Exception:
                    pass
            for _ in range(options.scroll_count):
                await page.mouse.wheel(0, 1400)
                await page.wait_for_timeout(options.scroll_wait_ms)
            return [await page.locator("body").inner_text(), await page.content()], ""
        except Exception as exc:
            return [], f"{type(exc).__name__}: {exc}"
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass

    def render(
        self,
        url: str,
        timeout: int,
        options: BrowserRenderOptions | None = None,
    ) -> tuple[list[str], str]:
        if self._startup_error is not None:
            raise self._startup_error
        loop = self._loop
        if loop is None or not loop.is_running():
            raise RuntimeError("Playwright运行时未运行")
        future = asyncio.run_coroutine_threadsafe(
            self._render_page(url, timeout, options), loop
        )
        try:
            return future.result(timeout=max(30, int(timeout) + 20))
        except TimeoutError as exc:
            future.cancel()
            raise TimeoutError(f"浏览器渲染总超时: {url}") from exc

    def close(self) -> None:
        loop = self._loop
        if loop is None or not self._thread.is_alive():
            return
        future = asyncio.run_coroutine_threadsafe(self._close_resources(), loop)
        try:
            future.result(timeout=30)
        except Exception:
            future.cancel()
        loop.call_soon_threadsafe(loop.stop)
        self._thread.join(timeout=30)


def _get_browser_runtime() -> _BrowserRuntime:
    global _BROWSER_RUNTIME
    with _BROWSER_RUNTIME_LOCK:
        if _BROWSER_RUNTIME is None:
            _BROWSER_RUNTIME = _BrowserRuntime()
        return _BROWSER_RUNTIME


def _shutdown_browser_runtime() -> None:
    global _BROWSER_RUNTIME
    with _BROWSER_RUNTIME_LOCK:
        runtime, _BROWSER_RUNTIME = _BROWSER_RUNTIME, None
    if runtime is not None:
        runtime.close()


def render_browser_documents(url: str, timeout: int = 20) -> list[str]:
    cache_key = (url, int(timeout))
    with RUNTIME_CACHE_LOCK:
        cached = RENDER_CACHE.get(cache_key)
        cached_status = RENDER_STATUS.get(cache_key, "")
        if cached is not None:
            return list(cached)
    if cached_status and cached_status != "ok":
        raise RuntimeError(cached_status)

    with RENDER_FLIGHTS_LOCK:
        flight = RENDER_FLIGHTS.get(cache_key)
        if flight is None:
            flight = threading.Event()
            RENDER_FLIGHTS[cache_key] = flight
            owns_flight = True
        else:
            owns_flight = False

    if not owns_flight:
        flight.wait()
        with RUNTIME_CACHE_LOCK:
            cached = RENDER_CACHE.get(cache_key)
            cached_status = RENDER_STATUS.get(cache_key, "")
        if cached is not None:
            return list(cached)
        raise RuntimeError(cached_status or "浏览器渲染未产生结果")

    try:
        try:
            rendered, render_error = _get_browser_runtime().render(url, timeout)
        except Exception as exc:
            rendered = []
            render_error = f"{type(exc).__name__}: {exc}"
        rendered = [document for document in rendered if document.strip()]
        if rendered:
            with RUNTIME_CACHE_LOCK:
                RENDER_CACHE[cache_key] = list(rendered)
                RENDER_STATUS[cache_key] = "ok"
        else:
            failure_status = "浏览器渲染为空" + (
                f"({render_error})" if render_error else ""
            )
            with RUNTIME_CACHE_LOCK:
                RENDER_STATUS[cache_key] = failure_status
            raise RuntimeError(failure_status)
        return rendered
    finally:
        with RENDER_FLIGHTS_LOCK:
            finished = RENDER_FLIGHTS.pop(cache_key, None)
            if finished is not None:
                finished.set()


atexit.register(_shutdown_browser_runtime)
