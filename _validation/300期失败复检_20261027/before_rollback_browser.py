from __future__ import annotations

import atexit
import asyncio
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from shawei.fetch.http_client import RENDER_CACHE, RENDER_STATUS, RUNTIME_CACHE_LOCK


RENDER_FLIGHTS: dict[tuple[str, int], threading.Event] = {}
RENDER_FLIGHTS_LOCK = threading.Lock()
_BROWSER_RUNTIME: "_BrowserRuntime | None" = None
_BROWSER_RUNTIME_LOCK = threading.Lock()


def browser_profile_dir() -> Path:
    """Return the persistent Playwright profile used by crawler renders."""
    configured = os.environ.get("SHAWEI_BROWSER_PROFILE")
    return Path(configured) if configured else Path(__file__).resolve().parents[2] / "browser-profile"


@dataclass(frozen=True)
class BrowserRenderOptions:
    wait_for_network_idle: bool = True
    post_load_wait_ms: int = 1200
    scroll_count: int = 6
    scroll_wait_ms: int = 200
    # 部分站点的目标表格藏在标签页里，必须先点开对应标签才会渲染。
    # 用 anchor（区块定位词）在同一容器内找 tab_text 并触发点击，
    # 避免只按文字全局点击时被遮挡或点错同名元素。
    click_anchor: str = ""
    click_tab_text: str = ""

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
        profile_dir = browser_profile_dir()
        profile_dir.mkdir(parents=True, exist_ok=True)
        launch_persistent = getattr(
            self._playwright.chromium, "launch_persistent_context", None
        )
        # 与 HTTP 兜底路径（curl --insecure）保持一致：站方证书过期/自签时不阻断渲染，
        # 否则 net::ERR_CERT_DATE_INVALID 会让整站当期被误判为抓取失败。
        if launch_persistent is None:  # test doubles may expose only the legacy API
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 2600},
                ignore_https_errors=True,
            )
        else:
            self._context = await launch_persistent(
                str(profile_dir),
                headless=True,
                viewport={"width": 1280, "height": 2600},
                ignore_https_errors=True,
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
            if options.click_tab_text:
                try:
                    await page.evaluate(
                        """(args) => {
                          const [anchor, tabText] = args;
                          const all = [...document.querySelectorAll('*')];
                          const titles = all.filter(
                            (e) => e.children.length === 0
                              && (e.textContent || '').includes(anchor)
                          );
                          if (!titles.length) return 'anchor-notfound';
                          let box = titles[0];
                          for (let i = 0; i < 8 && box.parentElement; i += 1) {
                            box = box.parentElement;
                          }
                          const tabs = [...box.querySelectorAll('*')].filter(
                            (e) => e.children.length === 0
                              && (e.textContent || '').trim() === tabText
                          );
                          if (!tabs.length) return 'tab-notfound';
                          const el = tabs[tabs.length - 1];
                          el.scrollIntoView({block: 'center'});
                          ['mousedown', 'mouseup', 'click'].forEach(
                            (type) => el.dispatchEvent(
                              new MouseEvent(type, {
                                bubbles: true, cancelable: true, view: window,
                              })
                            )
                          );
                          return 'clicked';
                        }""",
                        [options.click_anchor, options.click_tab_text],
                    )
                    await page.wait_for_timeout(2500)
                except Exception:
                    pass
            # 滚动只用于触发懒加载；部分站点在滚动阶段会让渲染进程崩溃（Page crashed），
            # 此时正文往往已经完整可读，先留存滚动前快照，崩溃时回退到该快照而不是整站判失败。
            snapshot: list[str] = []
            try:
                snapshot = [await page.locator("body").inner_text(), await page.content()]
            except Exception:
                snapshot = []
            try:
                for _ in range(options.scroll_count):
                    await page.mouse.wheel(0, 1400)
                    await page.wait_for_timeout(options.scroll_wait_ms)
            except Exception as scroll_error:
                if any(document.strip() for document in snapshot):
                    return snapshot, ""
                return [], f"{type(scroll_error).__name__}: {scroll_error}"
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


def render_browser_documents(
    url: str,
    timeout: int = 20,
    options: BrowserRenderOptions | None = None,
) -> list[str]:
    cache_key = (
        url,
        int(timeout),
        (options.click_anchor, options.click_tab_text) if options else ("", ""),
    )
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
            rendered, render_error = _get_browser_runtime().render(url, timeout, options)
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
