from __future__ import annotations

import asyncio

import pytest

from shawei.fetch.browser import BrowserRenderOptions, _BrowserRuntime


class _FakeLocator:
    async def inner_text(self) -> str:
        return "body text"


class _FakePage:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.locator_result = _FakeLocator()

    async def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.calls.append(("goto", url, wait_until, timeout))

    async def wait_for_load_state(self, state: str, *, timeout: int) -> None:
        self.calls.append(("load_state", state, timeout))

    async def wait_for_timeout(self, delay_ms: int) -> None:
        self.calls.append(("wait", delay_ms))

    class _Mouse:
        def __init__(self, calls: list[tuple[object, ...]]) -> None:
            self.calls = calls

        async def wheel(self, x: int, y: int) -> None:
            self.calls.append(("wheel", x, y))

    @property
    def mouse(self) -> _Mouse:
        return self._Mouse(self.calls)

    def locator(self, selector: str) -> _FakeLocator:
        self.calls.append(("locator", selector))
        return self.locator_result

    async def content(self) -> str:
        self.calls.append(("content",))
        return "<body>body text</body>"


class _FakeContext:
    def __init__(self, page: _FakePage) -> None:
        self.page = page

    async def new_page(self) -> _FakePage:
        return self.page


def test_default_render_options_keep_legacy_wait_and_scroll_values() -> None:
    page = _FakePage()
    runtime = _BrowserRuntime.__new__(_BrowserRuntime)
    runtime._context = _FakeContext(page)

    documents, error = asyncio.run(runtime._render_page("https://example.test", 20))

    assert error == ""
    assert documents == ["body text", "<body>body text</body>"]
    assert [call for call in page.calls if call[0] == "load_state"] == [
        ("load_state", "networkidle", 15000)
    ]
    assert [call for call in page.calls if call[0] == "wait"] == [
        ("wait", 1200),
        ("wait", 200),
        ("wait", 200),
        ("wait", 200),
        ("wait", 200),
        ("wait", 200),
        ("wait", 200),
    ]
    assert [call for call in page.calls if call[0] == "wheel"] == [
        ("wheel", 0, 1400)
    ] * 6


def test_explicit_render_options_reduce_wait_and_scroll_work() -> None:
    page = _FakePage()
    runtime = _BrowserRuntime.__new__(_BrowserRuntime)
    runtime._context = _FakeContext(page)

    documents, error = asyncio.run(
        runtime._render_page(
            "https://example.test",
            20,
            BrowserRenderOptions(
                wait_for_network_idle=False,
                post_load_wait_ms=0,
                scroll_count=1,
                scroll_wait_ms=0,
            ),
        )
    )

    assert error == ""
    assert documents == ["body text", "<body>body text</body>"]
    assert not any(call[0] == "load_state" for call in page.calls)
    assert [call for call in page.calls if call[0] == "wait"] == [("wait", 0), ("wait", 0)]
    assert [call for call in page.calls if call[0] == "wheel"] == [("wheel", 0, 1400)]


def test_render_options_reject_negative_delays() -> None:
    try:
        BrowserRenderOptions(post_load_wait_ms=-1)
    except ValueError as exc:
        assert "post_load_wait_ms" in str(exc)
    else:
        raise AssertionError("negative wait must be rejected")


class _CrashingMouse:
    def __init__(self, calls: list[tuple[object, ...]]) -> None:
        self.calls = calls

    async def wheel(self, x: int, y: int) -> None:
        self.calls.append(("wheel", x, y))
        raise RuntimeError("Page.wait_for_timeout: Page crashed")


class _CrashingPage(_FakePage):
    """滚动阶段渲染进程崩溃：正文在崩溃前已可读，必须回退到该快照。"""

    @property
    def mouse(self) -> _CrashingMouse:
        return _CrashingMouse(self.calls)


class _EmptyCrashingPage(_CrashingPage):
    def locator(self, selector: str) -> _FakeLocator:
        self.calls.append(("locator", selector))

        class _EmptyLocator:
            async def inner_text(self) -> str:
                return "   "

        return _EmptyLocator()

    async def content(self) -> str:
        self.calls.append(("content",))
        return "   "


def test_render_falls_back_to_pre_scroll_snapshot_when_scroll_crashes() -> None:
    page = _CrashingPage()
    runtime = _BrowserRuntime.__new__(_BrowserRuntime)
    runtime._context = _FakeContext(page)

    documents, error = asyncio.run(runtime._render_page("https://example.test", 20))

    assert error == ""
    assert documents == ["body text", "<body>body text</body>"]


def test_render_reports_error_when_scroll_crashes_and_snapshot_is_empty() -> None:
    page = _EmptyCrashingPage()
    runtime = _BrowserRuntime.__new__(_BrowserRuntime)
    runtime._context = _FakeContext(page)

    documents, error = asyncio.run(runtime._render_page("https://example.test", 20))

    assert documents == []
    assert "Page crashed" in error


class _FakeChromium:
    def __init__(self) -> None:
        self.launch_calls: list[dict[str, object]] = []
        self.context_calls: list[dict[str, object]] = []

    async def launch(self, **kwargs: object) -> object:
        self.launch_calls.append(kwargs)

        class _FakeBrowser:
            async def new_context(inner_self, **context_kwargs: object) -> object:
                self.context_calls.append(context_kwargs)
                return object()

        return _FakeBrowser()

    async def launch_persistent_context(self, path: str, **kwargs: object) -> object:
        self.context_calls.append({"path": path, **kwargs})
        return object()


class _FakePlaywright:
    def __init__(self, chromium: _FakeChromium) -> None:
        self.chromium = chromium


def _start_runtime(monkeypatch, tmp_path, with_persistent: bool):
    from shawei.fetch import browser as browser_module

    chromium = _FakeChromium()
    if not with_persistent:
        chromium.launch_persistent_context = None

    class _Starter:
        async def start(self) -> _FakePlaywright:
            return _FakePlaywright(chromium)

    monkeypatch.setattr("playwright.async_api.async_playwright", lambda: _Starter())
    monkeypatch.setattr(browser_module, "browser_profile_dir", lambda: tmp_path)
    runtime = _BrowserRuntime.__new__(_BrowserRuntime)
    asyncio.run(runtime._start())
    return chromium


@pytest.mark.parametrize("with_persistent", [True, False])
def test_browser_contexts_ignore_expired_https_certificates(
    monkeypatch, tmp_path, with_persistent: bool
) -> None:
    # 站方证书过期（net::ERR_CERT_DATE_INVALID）不应阻断渲染：与 curl --insecure 约定一致。
    chromium = _start_runtime(monkeypatch, tmp_path, with_persistent)

    assert len(chromium.context_calls) == 1
    assert chromium.context_calls[0]["ignore_https_errors"] is True
