from __future__ import annotations

import json
import ssl
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from email.message import Message
from types import ModuleType
from urllib.error import HTTPError, URLError

import pytest

from shawei.domain.models import Record, SiteConfig, StrictRule
from shawei.fetch import browser, decoding, document_discovery, profile
from shawei.fetch.dynamic_article import (
    admin_article_api_urls,
    dynamic_article_id,
    manager_article_api_urls,
)
from shawei.fetch import http_client
from shawei.services import crawl_site


ARTICLE_URL = "https://example.test/article/admin/target-123"
ARTICLE_API_URL = admin_article_api_urls(ARTICLE_URL)[0]
MANAGER_ARTICLE_URL = "https://example.test/article/manager/target-123"
MANAGER_ARTICLE_API_URL = manager_article_api_urls(MANAGER_ARTICLE_URL)[0]
LOTTERY_ARTICLE_URL = "https://example.test/article/lottery/target-123"
LOTTERY_ARTICLE_API_URL = "https://example.test/api/proxy/manager-articles/target-123"
TARGET_ID = "target-123"


def _http_error(url: str, code: int, message: str) -> HTTPError:
    return HTTPError(url, code, message, hdrs=Message(), fp=None)


def test_base64_decoder_does_not_corrupt_plain_ascii_text() -> None:
    assert decoding._decode_b64("test") is None
    assert decoding._decode_b64("MjM05pyfIOe7neadgOS4gOWwviA35bC+") == "234期 绝杀一尾 7尾"


def test_http_only_site_does_not_start_browser_after_transport_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://http-only.example/topic/1.html"
    render_calls: list[str] = []
    monkeypatch.setattr(crawl_site, "effective_rule_for", lambda *_args: StrictRule())
    monkeypatch.setattr(
        document_discovery,
        "collect_documents",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ssl.SSLError("TLS failed")),
    )
    monkeypatch.setattr(
        browser,
        "render_browser_documents",
        lambda target, _timeout: render_calls.append(target) or [],
    )
    http_client.clear_fetch_cache(url)

    with pytest.raises(ssl.SSLError, match="TLS failed"):
        crawl_site.collect_site_records(url, "HTTP专用站", target_period=234)

    assert render_calls == []


def test_root_page_uses_http_only_unless_rule_explicitly_requests_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://static-root.example/"
    render_calls: list[str] = []
    monkeypatch.setattr(crawl_site, "effective_rule_for", lambda *_args: StrictRule())
    monkeypatch.setattr(
        document_discovery, "collect_documents", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        browser,
        "render_browser_documents",
        lambda target, _timeout: render_calls.append(target) or [],
    )
    http_client.clear_fetch_cache(url)

    assert crawl_site.collect_site_records(url, "静态根站", target_period=234) == []
    assert render_calls == []


def test_explicit_browser_site_does_not_also_fetch_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://browser-only.example/"
    http_calls: list[str] = []
    render_calls: list[str] = []
    monkeypatch.setattr(
        crawl_site,
        "effective_rule_for",
        lambda *_args: StrictRule(prefer_rendered=True),
    )
    monkeypatch.setattr(
        document_discovery,
        "collect_documents",
        lambda target, *_args, **_kwargs: http_calls.append(target) or [],
    )
    monkeypatch.setattr(
        browser,
        "render_browser_documents",
        lambda target, _timeout: render_calls.append(target)
        or ["234期 绝杀一尾 7尾 开准"],
    )
    monkeypatch.setattr(
        crawl_site,
        "_extract_site_records_from_documents",
        lambda *_args: [Record(tail=7, period=234, site_name="浏览器专用站")],
    )
    http_client.clear_fetch_cache(url)

    records = crawl_site.collect_site_records(
        url, "浏览器专用站", target_period=234
    )

    assert [record.value() for record in records] == ["7"]
    assert render_calls == [url]
    assert http_calls == []


def test_explicit_browser_site_uses_its_configured_render_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://slow-browser.example/"
    render_calls: list[tuple[str, int]] = []
    monkeypatch.setattr(
        crawl_site,
        "effective_rule_for",
        lambda *_args: StrictRule(prefer_rendered=True, render_timeout=20),
    )
    monkeypatch.setattr(
        document_discovery,
        "collect_documents",
        lambda *_args, **_kwargs: pytest.fail("固定浏览器站不应请求HTTP"),
    )
    monkeypatch.setattr(
        browser,
        "render_browser_documents",
        lambda target, timeout: render_calls.append((target, timeout))
        or ["239期 绝杀一尾 3尾 开准"],
    )
    monkeypatch.setattr(
        crawl_site,
        "_extract_site_records_from_documents",
        lambda *_args: [Record(tail=3, period=239, site_name="慢速浏览器站")],
    )
    http_client.clear_fetch_cache(url)

    records = crawl_site.collect_site_records(
        url, "慢速浏览器站", timeout=8, target_period=239
    )

    assert [record.value() for record in records] == ["3"]
    assert render_calls == [(url, 20)]


def test_followed_target_transport_error_is_not_hidden_as_empty_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page_url = "https://list.example/list.html"
    page = '<a href="detail.html">目标站 每期绝杀一尾</a>'
    monkeypatch.setattr(
        document_discovery,
        "fetch_text",
        lambda *_args: (_ for _ in ()).throw(ssl.SSLError("detail TLS failed")),
    )

    with pytest.raises(ssl.SSLError, match="detail TLS failed"):
        document_discovery.collect_followed_link_documents(
            page_url,
            page,
            ("目标站", "每期绝杀一尾"),
            timeout=5,
        )


def test_follow_link_pagination_transport_error_is_not_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page_url = "https://list.example/list.aspx?id=33"
    page = '<a href="list.aspx?id=33&page=2">下一页</a>'
    monkeypatch.setattr(
        document_discovery,
        "fetch_text",
        lambda *_args: (_ for _ in ()).throw(TimeoutError("next page timed out")),
    )

    with pytest.raises(TimeoutError, match="next page timed out"):
        document_discovery.collect_followed_link_documents(
            page_url,
            page,
            ("不存在的目标",),
            timeout=5,
            paginate=True,
        )
SITE_NAME = "测试站"
TARGET_PERIOD = 234


def _rule() -> StrictRule:
    return StrictRule(allowed_sources=("compact",), chunk_keywords=("绝杀一尾",))


def _run_admin_article_case(monkeypatch, api_result) -> list[tuple[str, int]]:
    render_calls: list[tuple[str, int]] = []

    def fake_fetch(url: str, _timeout: int) -> str:
        if url == ARTICLE_API_URL:
            if isinstance(api_result, BaseException):
                raise api_result
            return api_result
        if "/api/proxy/manager-articles/" in url:
            raise _http_error(url, 500, "secondary endpoint unavailable")
        return "<html><body>动态页面壳</body></html>"

    def fake_render(url: str, timeout: int) -> list[str]:
        render_calls.append((url, timeout))
        return [
            f'<article data-id="{TARGET_ID}">'
            f"{SITE_NAME} {TARGET_PERIOD}期 绝杀一尾 7尾 开准"
            "</article>"
        ]

    monkeypatch.setattr(document_discovery, "fetch_text", fake_fetch)
    monkeypatch.setattr(browser, "render_browser_documents", fake_render)

    with pytest.raises(Exception):
        crawl_site._collect_admin_article_records(
            ARTICLE_URL,
            SITE_NAME,
            "top",
            5,
            TARGET_PERIOD,
            _rule(),
            ("audit", str(api_result)),
        )
    return render_calls


@pytest.mark.parametrize(
    "api_result",
    [
        pytest.param(ssl.SSLError("TLS handshake failed"), id="tls-error"),
        pytest.param(
            _http_error(ARTICLE_API_URL, 500, "server error"),
            id="http-500",
        ),
        pytest.param(URLError("network is unavailable"), id="network-error"),
        pytest.param("not-json", id="untrusted-json"),
        pytest.param(
            json.dumps(
                [
                    {
                        "id": TARGET_ID,
                        "authorNickname": SITE_NAME,
                        "title": "第一份",
                        "html": "234期 绝杀一尾 1尾",
                    },
                    {
                        "id": TARGET_ID,
                        "authorNickname": SITE_NAME,
                        "title": "第二份",
                        "html": "234期 绝杀一尾 2尾",
                    },
                ]
            ),
            id="duplicate-target-id",
        ),
    ],
)
def test_admin_article_never_renders_after_non_fallback_api_failure(
    monkeypatch, api_result
) -> None:
    assert _run_admin_article_case(monkeypatch, api_result) == []


def _run_allowed_admin_article_case(monkeypatch, api_result):
    render_calls: list[tuple[str, int]] = []

    def fake_fetch(url: str, _timeout: int) -> str:
        if url == ARTICLE_API_URL:
            if isinstance(api_result, BaseException):
                raise api_result
            return api_result
        if "/api/proxy/manager-articles/" in url:
            raise _http_error(url, 404, "secondary endpoint unavailable")
        return "<html><body>动态页面壳</body></html>"

    def fake_render(url: str, timeout: int) -> list[str]:
        render_calls.append((url, timeout))
        return [
            f'<article data-id="{TARGET_ID}">'
            f"{SITE_NAME} {TARGET_PERIOD}期 绝杀一尾 7尾 开准"
            "</article>"
        ]

    monkeypatch.setattr(document_discovery, "fetch_text", fake_fetch)
    monkeypatch.setattr(browser, "render_browser_documents", fake_render)
    monkeypatch.setattr(
        crawl_site,
        "_extract_site_records_from_documents",
        lambda *_args: [Record(tail=7, period=TARGET_PERIOD, site_name=SITE_NAME)],
    )

    records = crawl_site._collect_admin_article_records(
        ARTICLE_URL,
        SITE_NAME,
        "top",
        5,
        TARGET_PERIOD,
        _rule(),
        ("allowed", str(api_result)),
    )
    return records, render_calls


def test_admin_article_404_is_allowed_to_render(monkeypatch) -> None:
    records, render_calls = _run_allowed_admin_article_case(
        monkeypatch,
        _http_error(ARTICLE_API_URL, 404, "not found"),
    )

    assert [record.value() for record in records] == ["7"]
    assert render_calls == [(ARTICLE_URL, 5)]


def test_admin_article_404_does_not_override_a_later_network_error(monkeypatch) -> None:
    render_calls: list[tuple[str, int]] = []

    def fail_collect(*_args, **_kwargs):
        raise URLError("page network is unavailable")

    monkeypatch.setattr(document_discovery, "collect_documents", fail_collect)
    monkeypatch.setattr(
        browser,
        "render_browser_documents",
        lambda url, timeout: render_calls.append((url, timeout)) or [],
    )

    with pytest.raises(URLError, match="page network is unavailable"):
        crawl_site._collect_admin_article_records(
            ARTICLE_URL,
            SITE_NAME,
            "top",
            5,
            TARGET_PERIOD,
            _rule(),
            ("404-network",),
        )

    assert render_calls == []


def test_admin_article_200_empty_body_is_allowed_to_render(monkeypatch) -> None:
    empty_body = json.dumps(
        {
            "id": TARGET_ID,
            "authorNickname": SITE_NAME,
            "title": "空壳文章",
            "html": "",
        }
    )

    records, render_calls = _run_allowed_admin_article_case(
        monkeypatch, empty_body
    )

    assert [record.value() for record in records] == ["7"]
    assert render_calls == [(ARTICLE_URL, 5)]


def test_admin_landing_untrusted_json_does_not_render_after_primary_404(monkeypatch) -> None:
    url = f"{ARTICLE_URL}?url=landing"
    primary_api_url = admin_article_api_urls(url)[0]
    landing_api_url = "https://example.test/api/proxy/landing-page-data?url=landing"
    render_calls: list[tuple[str, int]] = []

    def fake_fetch(requested_url: str, _timeout: int) -> str:
        if requested_url == primary_api_url:
            raise _http_error(requested_url, 404, "not found")
        if requested_url == landing_api_url:
            return "not-json"
        if "/api/proxy/manager-articles/" in requested_url:
            raise _http_error(requested_url, 404, "not found")
        return "<html><body>动态页面壳</body></html>"

    monkeypatch.setattr(document_discovery, "fetch_text", fake_fetch)
    monkeypatch.setattr(
        browser,
        "render_browser_documents",
        lambda requested_url, timeout: render_calls.append((requested_url, timeout)) or [],
    )

    with pytest.raises(LookupError, match="有效JSON"):
        crawl_site._collect_admin_article_records(
            url,
            SITE_NAME,
            "top",
            5,
            TARGET_PERIOD,
            _rule(),
            ("landing-untrusted",),
        )

    assert render_calls == []


def test_admin_article_nonempty_200_document_missing_target_does_not_render(
    monkeypatch,
) -> None:
    nonempty_wrong_period = json.dumps(
        {
            "id": TARGET_ID,
            "authorNickname": SITE_NAME,
            "title": "完整但不是目标期",
            "html": "233期 绝杀一尾 1尾 开准",
        }
    )

    render_calls = _run_admin_article_case(monkeypatch, nonempty_wrong_period)

    assert render_calls == []


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(LookupError("目标ID冲突"), id="id-conflict"),
        pytest.param(LookupError("错栏目"), id="wrong-column"),
        pytest.param(LookupError("字段错误"), id="wrong-field"),
        pytest.param(ssl.SSLError("TLS handshake failed"), id="tls-error"),
    ],
)
def test_crawl_current_site_does_not_retry_non_boundary_failures(
    monkeypatch, failure
) -> None:
    calls: list[int] = []
    sleeps: list[float] = []

    def fail_once_or_forever(*_args, **_kwargs):
        calls.append(1)
        raise failure

    monkeypatch.setattr(crawl_site, "collect_site_records", fail_once_or_forever)
    monkeypatch.setattr(crawl_site, "clear_fetch_cache", lambda _url: pytest.fail("非边界失败不应清缓存"))
    monkeypatch.setattr(crawl_site.time, "sleep", sleeps.append)

    result = crawl_site.crawl_current_site(
        1,
        1,
        SiteConfig(name=SITE_NAME, url=ARTICLE_URL, pick="top"),
        TARGET_PERIOD,
        timeout=5,
        retries=2,
    )

    assert result.success_line is None
    assert len(calls) == 1
    assert sleeps == []


@pytest.mark.parametrize(
    "failure_message",
    [
        pytest.param("绝对top边界是233期，不是指定234期", id="boundary"),
        pytest.param("没有找到234期目标数据", id="missing-period"),
    ],
)
def test_crawl_current_site_retries_boundary_or_missing_failures(
    monkeypatch, failure_message
) -> None:
    calls: list[int] = []
    clears: list[str] = []
    sleeps: list[float] = []

    def fail_then_succeed(*_args, **_kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise LookupError(failure_message)
        return [Record(tail=7, period=TARGET_PERIOD, site_name=SITE_NAME)]

    monkeypatch.setattr(crawl_site, "collect_site_records", fail_then_succeed)
    monkeypatch.setattr(crawl_site, "clear_fetch_cache", clears.append)
    monkeypatch.setattr(crawl_site.time, "sleep", sleeps.append)

    result = crawl_site.crawl_current_site(
        1,
        1,
        SiteConfig(name=SITE_NAME, url=ARTICLE_URL, pick="top"),
        TARGET_PERIOD,
        timeout=5,
        retries=1,
    )

    assert result.success_line == f"7尾 {SITE_NAME}"
    assert len(calls) == 2
    assert clears == [ARTICLE_URL]
    assert sleeps == [1.5]


def test_crawl_current_site_uses_one_retry_loop_for_missing_period(monkeypatch) -> None:
    calls: list[int] = []
    clears: list[str] = []
    sleeps: list[float] = []

    def always_returns_other_period(*_args, **_kwargs):
        calls.append(1)
        return [Record(tail=7, period=TARGET_PERIOD - 1, site_name=SITE_NAME)]

    monkeypatch.setattr(crawl_site, "collect_site_records", always_returns_other_period)
    monkeypatch.setattr(crawl_site, "clear_fetch_cache", clears.append)
    monkeypatch.setattr(crawl_site.time, "sleep", sleeps.append)

    result = crawl_site.crawl_current_site(
        1,
        1,
        SiteConfig(name=SITE_NAME, url=ARTICLE_URL, pick="top"),
        TARGET_PERIOD,
        timeout=5,
        retries=1,
    )

    assert result.success_line is None
    assert len(calls) == 2
    assert clears == [ARTICLE_URL]
    assert sleeps == [1.5]


def test_browser_deduplicates_concurrent_same_url_rendering(monkeypatch) -> None:
    url = "https://example.test/render-once"
    http_client.clear_fetch_cache(url)
    launch_started = threading.Event()
    release_render = threading.Event()
    second_call_entered = threading.Event()
    launch_count = 0
    call_count = 0
    count_lock = threading.Lock()

    class FakeRuntime:
        def render(self, _url: str, _timeout: int):
            nonlocal launch_count
            with count_lock:
                launch_count += 1
            launch_started.set()
            assert release_render.wait(2)
            return ["渲染正文", "<html><body>渲染正文</body></html>"], ""

    original_render = browser.render_browser_documents

    def wrapped_render(render_url: str, timeout: int):
        nonlocal call_count
        with count_lock:
            call_count += 1
            if call_count == 2:
                second_call_entered.set()
        return original_render(render_url, timeout)

    monkeypatch.setattr(browser, "_get_browser_runtime", lambda: FakeRuntime())
    monkeypatch.setattr(browser, "render_browser_documents", wrapped_render)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(browser.render_browser_documents, url, 5)
            assert launch_started.wait(2)
            second = executor.submit(browser.render_browser_documents, url, 5)
            assert second_call_entered.wait(2)
            release_render.set()
            assert first.result() == ["渲染正文", "<html><body>渲染正文</body></html>"]
            assert second.result() == ["渲染正文", "<html><body>渲染正文</body></html>"]
    finally:
        http_client.clear_fetch_cache(url)

    assert launch_count == 1


class _FakeResponse:
    def __init__(self, body: bytes, headers=None):
        self._body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._body

    def get_content_charset(self):
        return None


def test_browser_reuses_runtime_for_different_urls(monkeypatch) -> None:
    counters = {
        "playwright": 0,
        "launch": 0,
        "context": 0,
        "page": 0,
        "page_close": 0,
    }

    class FakePage:
        class _Mouse:
            async def wheel(self, _x, _y):
                return None

        mouse = _Mouse()

        async def goto(self, _url, **_kwargs):
            return None

        async def wait_for_load_state(self, *_args, **_kwargs):
            return None

        async def wait_for_timeout(self, _timeout):
            return None

        def locator(self, _selector):
            return self

        async def inner_text(self):
            return "渲染正文"

        async def content(self):
            return "<html><body>渲染正文</body></html>"

        async def close(self):
            counters["page_close"] += 1

    class FakeContext:
        async def new_page(self):
            counters["page"] += 1
            return FakePage()

    class FakeBrowser:
        async def new_page(self, **_kwargs):
            counters["page"] += 1
            return FakePage()

        async def new_context(self, **_kwargs):
            counters["context"] += 1
            return FakeContext()

        async def close(self):
            return None

    class FakeChromium:
        async def launch(self, **_kwargs):
            counters["launch"] += 1
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

        async def stop(self):
            return None

    class FakeManager:
        async def start(self):
            counters["playwright"] += 1
            return FakePlaywright()

        async def __aenter__(self):
            return await self.start()

        async def __aexit__(self, *_args):
            return None

    playwright_package = ModuleType("playwright")
    playwright_api = ModuleType("playwright.async_api")
    setattr(playwright_api, "async_playwright", lambda: FakeManager())
    monkeypatch.setitem(sys.modules, "playwright", playwright_package)
    monkeypatch.setitem(sys.modules, "playwright.async_api", playwright_api)

    browser._shutdown_browser_runtime()
    urls = (
        "https://example.test/render-a",
        "https://example.test/render-b",
    )
    try:
        http_client.clear_fetch_cache()
        assert browser.render_browser_documents(urls[0], 5)
        assert browser.render_browser_documents(urls[1], 5)
    finally:
        browser._shutdown_browser_runtime()
        http_client.clear_fetch_cache()

    assert counters["playwright"] == 1
    assert counters["launch"] == 1
    assert counters["context"] == 1
    assert counters["page"] == 2
    assert counters["page_close"] == 2


def test_browser_closes_failed_page_and_runtime_survives(monkeypatch) -> None:
    counters = {"launch": 0, "context": 0, "page": 0, "page_close": 0, "browser_close": 0, "stop": 0}

    class FakePage:
        def __init__(self, url: str = ""):
            self.url = url

        class _Mouse:
            async def wheel(self, _x, _y):
                return None

        mouse = _Mouse()

        async def goto(self, url, **_kwargs):
            self.url = url
            if url.endswith("/broken"):
                raise RuntimeError("page failed")

        async def wait_for_load_state(self, *_args, **_kwargs):
            return None

        async def wait_for_timeout(self, _timeout):
            return None

        def locator(self, _selector):
            return self

        async def inner_text(self):
            return "后续正文"

        async def content(self):
            return "<html><body>后续正文</body></html>"

        async def close(self):
            counters["page_close"] += 1

    class FakeContext:
        async def new_page(self):
            counters["page"] += 1
            return FakePage()

    class FakeBrowser:
        async def new_context(self, **_kwargs):
            counters["context"] += 1
            return FakeContext()

        async def close(self):
            counters["browser_close"] += 1

    class FakeChromium:
        async def launch(self, **_kwargs):
            counters["launch"] += 1
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

        async def stop(self):
            counters["stop"] += 1

    class FakeManager:
        async def start(self):
            return FakePlaywright()

    playwright_package = ModuleType("playwright")
    playwright_api = ModuleType("playwright.async_api")
    setattr(playwright_api, "async_playwright", lambda: FakeManager())
    monkeypatch.setitem(sys.modules, "playwright", playwright_package)
    monkeypatch.setitem(sys.modules, "playwright.async_api", playwright_api)

    browser._shutdown_browser_runtime()
    broken_url = "https://example.test/broken"
    good_url = "https://example.test/after-failure"
    try:
        http_client.clear_fetch_cache()
        with pytest.raises(RuntimeError, match="page failed"):
            browser.render_browser_documents(broken_url, 5)
        assert browser.render_browser_documents(good_url, 5)
    finally:
        browser._shutdown_browser_runtime()
        http_client.clear_fetch_cache()

    assert counters["launch"] == 1
    assert counters["context"] == 1
    assert counters["page"] == 2
    assert counters["page_close"] == 2
    assert counters["browser_close"] == 1
    assert counters["stop"] == 1


def test_browser_rejects_whitespace_only_render(monkeypatch) -> None:
    url = "https://example.test/empty-render"

    class EmptyRuntime:
        def render(self, _url, _timeout):
            return ["", "   \n"], ""

    monkeypatch.setattr(browser, "_get_browser_runtime", lambda: EmptyRuntime())
    http_client.clear_fetch_cache(url)

    with pytest.raises(RuntimeError, match="浏览器渲染为空"):
        browser.render_browser_documents(url, 5)


def test_profile_topic_keyword_uses_qvuu_parser_not_site_name() -> None:
    assert profile._profile_topic_keyword("ordinary_profile", "强烈招牌") == "绝杀一尾"
    assert profile._profile_topic_keyword("qvuu_qiangli_zhaopai_two_tail", "普通站名") == "二尾"


def test_manager_article_non_fallback_api_errors_never_render(monkeypatch, api_result) -> None:
    render_calls: list[tuple[str, int]] = []
    page_calls: list[str] = []

    def fake_fetch(url: str, _timeout: int) -> str:
        if url == MANAGER_ARTICLE_API_URL:
            if isinstance(api_result, BaseException):
                raise api_result
            return api_result
        if url == MANAGER_ARTICLE_URL:
            page_calls.append(url)
            return "<html><body>动态页面壳</body></html>"
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(document_discovery, "fetch_text", fake_fetch)
    monkeypatch.setattr(crawl_site, "effective_rule_for", lambda *_args: _rule())
    monkeypatch.setattr(
        browser,
        "render_browser_documents",
        lambda url, timeout: render_calls.append((url, timeout)) or [
            f'<article data-id="{TARGET_ID}">{TARGET_PERIOD}期 绝杀一尾 7尾</article>'
        ],
    )
    http_client.clear_fetch_cache(MANAGER_ARTICLE_URL)
    try:
        with pytest.raises(Exception):
            crawl_site.collect_site_records(
                MANAGER_ARTICLE_URL,
                SITE_NAME,
                "top",
                timeout=5,
                target_period=TARGET_PERIOD,
            )
    finally:
        http_client.clear_fetch_cache(MANAGER_ARTICLE_URL)

    assert render_calls == []
    assert page_calls == []


@pytest.fixture(
    params=[
        pytest.param(ssl.SSLError("TLS handshake failed"), id="tls-error"),
        pytest.param(_http_error(MANAGER_ARTICLE_API_URL, 500, "server error"), id="http-500"),
        pytest.param(URLError("network is unavailable"), id="network-error"),
        pytest.param("not-json", id="untrusted-json"),
        pytest.param(
            json.dumps(
                [
                    {"id": TARGET_ID, "authorNickname": SITE_NAME, "title": "第一份", "html": "234期 绝杀一尾 1尾"},
                    {"id": TARGET_ID, "authorNickname": SITE_NAME, "title": "第二份", "html": "234期 绝杀一尾 2尾"},
                ]
            ),
            id="duplicate-target-id",
        ),
    ]
)
def api_result(request):
    return request.param


def test_manager_article_404_can_render(monkeypatch) -> None:
    render_calls: list[tuple[str, int]] = []

    def fake_fetch(url: str, _timeout: int) -> str:
        if url == MANAGER_ARTICLE_API_URL:
            raise _http_error(url, 404, "not found")
        if url == MANAGER_ARTICLE_URL:
            return "<html><body>动态页面壳</body></html>"
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(document_discovery, "fetch_text", fake_fetch)
    monkeypatch.setattr(crawl_site, "effective_rule_for", lambda *_args: _rule())
    monkeypatch.setattr(
        browser,
        "render_browser_documents",
        lambda url, timeout: render_calls.append((url, timeout)) or [
            f'<article data-id="{TARGET_ID}">{SITE_NAME} {TARGET_PERIOD}期 绝杀一尾 7尾</article>'
        ],
    )
    monkeypatch.setattr(
        crawl_site,
        "_extract_site_records_from_documents",
        lambda *_args: [Record(tail=7, period=TARGET_PERIOD, site_name=SITE_NAME)],
    )

    http_client.clear_fetch_cache(MANAGER_ARTICLE_URL)
    try:
        records = crawl_site.collect_site_records(
            MANAGER_ARTICLE_URL, SITE_NAME, "top", timeout=5, target_period=TARGET_PERIOD
        )
    finally:
        http_client.clear_fetch_cache(MANAGER_ARTICLE_URL)

    assert [record.value() for record in records] == ["7"]
    assert render_calls == [(MANAGER_ARTICLE_URL, 5)]


def test_manager_article_empty_200_can_render(monkeypatch) -> None:
    empty_body = json.dumps(
        {"id": TARGET_ID, "authorNickname": SITE_NAME, "title": "空壳文章", "html": ""}
    )
    render_calls: list[tuple[str, int]] = []

    def fake_fetch(url: str, _timeout: int) -> str:
        if url == MANAGER_ARTICLE_API_URL:
            return empty_body
        raise AssertionError(f"page fallback must not fetch: {url}")

    monkeypatch.setattr(document_discovery, "fetch_text", fake_fetch)
    monkeypatch.setattr(crawl_site, "effective_rule_for", lambda *_args: _rule())
    monkeypatch.setattr(
        browser,
        "render_browser_documents",
        lambda url, timeout: render_calls.append((url, timeout)) or [
            f'<article data-id="{TARGET_ID}">{SITE_NAME} {TARGET_PERIOD}期 绝杀一尾 7尾</article>'
        ],
    )
    monkeypatch.setattr(
        crawl_site,
        "_extract_site_records_from_documents",
        lambda *_args: [Record(tail=7, period=TARGET_PERIOD, site_name=SITE_NAME)],
    )

    http_client.clear_fetch_cache(MANAGER_ARTICLE_URL)
    try:
        records = crawl_site.collect_site_records(
            MANAGER_ARTICLE_URL, SITE_NAME, "top", timeout=5, target_period=TARGET_PERIOD
        )
    finally:
        http_client.clear_fetch_cache(MANAGER_ARTICLE_URL)

    assert [record.value() for record in records] == ["7"]
    assert render_calls == [(MANAGER_ARTICLE_URL, 5)]


def test_manager_article_nonempty_missing_period_does_not_render(monkeypatch) -> None:
    nonempty_wrong_period = json.dumps(
        {"id": TARGET_ID, "authorNickname": SITE_NAME, "title": "完整文章", "html": "233期 绝杀一尾 1尾"}
    )
    render_calls: list[tuple[str, int]] = []
    page_calls: list[str] = []

    def fake_fetch(url: str, _timeout: int) -> str:
        if url == MANAGER_ARTICLE_API_URL:
            return nonempty_wrong_period
        page_calls.append(url)
        raise AssertionError(f"nonempty API result must not fetch page: {url}")

    monkeypatch.setattr(document_discovery, "fetch_text", fake_fetch)
    monkeypatch.setattr(crawl_site, "effective_rule_for", lambda *_args: _rule())
    monkeypatch.setattr(
        browser,
        "render_browser_documents",
        lambda url, timeout: render_calls.append((url, timeout)) or [],
    )

    http_client.clear_fetch_cache(MANAGER_ARTICLE_URL)
    try:
        with pytest.raises(Exception):
            crawl_site.collect_site_records(
                MANAGER_ARTICLE_URL,
                SITE_NAME,
                "top",
                timeout=5,
                target_period=TARGET_PERIOD,
            )
    finally:
        http_client.clear_fetch_cache(MANAGER_ARTICLE_URL)

    assert render_calls == []
    assert page_calls == []


def test_dynamic_article_routes_include_lottery_and_manager_page_is_not_prefetched(monkeypatch) -> None:
    calls: list[str] = []
    valid_api = json.dumps(
        {"id": TARGET_ID, "authorNickname": SITE_NAME, "title": "完整文章", "html": "234期 绝杀一尾 7尾"}
    )

    def fake_fetch(url: str, _timeout: int) -> str:
        calls.append(url)
        if url == MANAGER_ARTICLE_API_URL:
            return valid_api
        raise AssertionError(f"manager page must not be fetched: {url}")

    monkeypatch.setattr(document_discovery, "fetch_text", fake_fetch)
    documents = document_discovery.collect_documents(MANAGER_ARTICLE_URL, timeout=5, site_name=SITE_NAME)

    assert documents
    assert calls == [MANAGER_ARTICLE_API_URL]
    assert dynamic_article_id(ARTICLE_URL) == TARGET_ID
    assert dynamic_article_id(MANAGER_ARTICLE_URL) == TARGET_ID
    assert dynamic_article_id(LOTTERY_ARTICLE_URL) == TARGET_ID
    assert manager_article_api_urls(LOTTERY_ARTICLE_URL) == [LOTTERY_ARTICLE_API_URL]


def test_admin_apis_are_complete_source_before_browser_fallback(monkeypatch) -> None:
    render_calls: list[tuple[str, int]] = []
    page_calls: list[str] = []
    valid_api = json.dumps(
        {"id": TARGET_ID, "authorNickname": SITE_NAME, "title": "完整文章", "html": "234期 绝杀一尾 7尾"}
    )
    admin_manager_api_url = manager_article_api_urls(ARTICLE_URL)[0]

    def fake_fetch(url: str, _timeout: int) -> str:
        if url == ARTICLE_API_URL:
            raise _http_error(url, 404, "not found")
        if url == admin_manager_api_url:
            return valid_api
        page_calls.append(url)
        raise AssertionError(f"dynamic article page must not be fetched: {url}")

    monkeypatch.setattr(document_discovery, "fetch_text", fake_fetch)
    monkeypatch.setattr(
        browser,
        "render_browser_documents",
        lambda url, timeout: render_calls.append((url, timeout)) or [],
    )
    monkeypatch.setattr(
        crawl_site,
        "_extract_site_records_from_documents",
        lambda *_args: [Record(tail=7, period=TARGET_PERIOD, site_name=SITE_NAME)],
    )

    http_client.clear_fetch_cache(ARTICLE_URL)
    try:
        records = crawl_site._collect_admin_article_records(
            ARTICLE_URL,
            SITE_NAME,
            "top",
            5,
            TARGET_PERIOD,
            _rule(),
            ("admin-404-manager-complete",),
        )
    finally:
        http_client.clear_fetch_cache(ARTICLE_URL)

    assert [record.value() for record in records] == ["7"]
    assert render_calls == []
    assert page_calls == []


def test_admin_empty_api_allows_secondary_manager_complete_source(monkeypatch) -> None:
    render_calls: list[tuple[str, int]] = []
    empty_api = json.dumps(
        {"id": TARGET_ID, "authorNickname": SITE_NAME, "title": "空壳文章", "html": ""}
    )
    valid_api = json.dumps(
        {"id": TARGET_ID, "authorNickname": SITE_NAME, "title": "完整文章", "html": "234期 绝杀一尾 7尾"}
    )
    admin_manager_api_url = manager_article_api_urls(ARTICLE_URL)[0]

    def fake_fetch(url: str, _timeout: int) -> str:
        if url == ARTICLE_API_URL:
            return empty_api
        if url == admin_manager_api_url:
            return valid_api
        raise AssertionError(f"dynamic article page must not be fetched: {url}")

    monkeypatch.setattr(document_discovery, "fetch_text", fake_fetch)
    monkeypatch.setattr(
        browser,
        "render_browser_documents",
        lambda url, timeout: render_calls.append((url, timeout)) or [],
    )
    monkeypatch.setattr(
        crawl_site,
        "_extract_site_records_from_documents",
        lambda *_args: [Record(tail=7, period=TARGET_PERIOD, site_name=SITE_NAME)],
    )

    http_client.clear_fetch_cache(ARTICLE_URL)
    try:
        records = crawl_site._collect_admin_article_records(
            ARTICLE_URL,
            SITE_NAME,
            "top",
            5,
            TARGET_PERIOD,
            _rule(),
            ("admin-empty-manager-complete",),
        )
    finally:
        http_client.clear_fetch_cache(ARTICLE_URL)

    assert [record.value() for record in records] == ["7"]
    assert render_calls == []


def test_admin_complete_api_only_requests_authorized_apis(monkeypatch) -> None:
    calls: list[str] = []
    valid_api = json.dumps(
        {"id": TARGET_ID, "authorNickname": SITE_NAME, "title": "完整文章", "html": "234期 绝杀一尾 7尾"}
    )
    admin_manager_api_url = manager_article_api_urls(ARTICLE_URL)[0]

    def fake_fetch(url: str, _timeout: int) -> str:
        calls.append(url)
        if url in {ARTICLE_API_URL, admin_manager_api_url}:
            return valid_api
        raise AssertionError(f"dynamic article page must not be fetched: {url}")

    monkeypatch.setattr(document_discovery, "fetch_text", fake_fetch)
    assert document_discovery.collect_documents(ARTICLE_URL, timeout=5, site_name=SITE_NAME)
    assert calls == [ARTICLE_API_URL, admin_manager_api_url]


def test_lottery_article_non_fallback_error_never_renders(monkeypatch) -> None:
    render_calls: list[tuple[str, int]] = []

    def fake_fetch(url: str, _timeout: int) -> str:
        if url == LOTTERY_ARTICLE_API_URL:
            raise ssl.SSLError("TLS handshake failed")
        raise AssertionError(f"dynamic article page must not be fetched: {url}")

    monkeypatch.setattr(document_discovery, "fetch_text", fake_fetch)
    monkeypatch.setattr(crawl_site, "effective_rule_for", lambda *_args: _rule())
    monkeypatch.setattr(
        browser,
        "render_browser_documents",
        lambda url, timeout: render_calls.append((url, timeout)) or [],
    )

    http_client.clear_fetch_cache(LOTTERY_ARTICLE_URL)
    try:
        with pytest.raises(Exception):
            crawl_site.collect_site_records(
                LOTTERY_ARTICLE_URL,
                SITE_NAME,
                "top",
                timeout=5,
                target_period=TARGET_PERIOD,
            )
    finally:
        http_client.clear_fetch_cache(LOTTERY_ARTICLE_URL)

    assert render_calls == []


def test_lottery_article_404_can_render(monkeypatch) -> None:
    render_calls: list[tuple[str, int]] = []

    def fake_fetch(url: str, _timeout: int) -> str:
        if url == LOTTERY_ARTICLE_API_URL:
            raise _http_error(url, 404, "not found")
        raise AssertionError(f"dynamic article page must not be fetched: {url}")

    monkeypatch.setattr(document_discovery, "fetch_text", fake_fetch)
    monkeypatch.setattr(crawl_site, "effective_rule_for", lambda *_args: _rule())
    monkeypatch.setattr(
        browser,
        "render_browser_documents",
        lambda url, timeout: render_calls.append((url, timeout))
        or [f'<article data-id="{TARGET_ID}">{SITE_NAME} {TARGET_PERIOD}期 绝杀一尾 7尾</article>'],
    )
    monkeypatch.setattr(
        crawl_site,
        "_extract_site_records_from_documents",
        lambda *_args: [Record(tail=7, period=TARGET_PERIOD, site_name=SITE_NAME)],
    )

    http_client.clear_fetch_cache(LOTTERY_ARTICLE_URL)
    try:
        records = crawl_site.collect_site_records(
            LOTTERY_ARTICLE_URL,
            SITE_NAME,
            "top",
            timeout=5,
            target_period=TARGET_PERIOD,
        )
    finally:
        http_client.clear_fetch_cache(LOTTERY_ARTICLE_URL)

    assert [record.value() for record in records] == ["7"]
    assert render_calls == [(LOTTERY_ARTICLE_URL, 5)]


def test_fetch_text_network_failure_has_one_fixed_fallback_without_sleep(monkeypatch) -> None:
    url = "https://example.test/network-failure"
    urllib_calls: list[str] = []
    curl_calls: list[tuple] = []

    def fail_urlopen(*_args, **_kwargs):
        urllib_calls.append(url)
        raise URLError("network down")

    monkeypatch.setattr(http_client, "urlopen", fail_urlopen)
    def fail_curl(*args):
        curl_calls.append(args)
        raise RuntimeError("curl unavailable")

    monkeypatch.setattr(http_client, "_curl_fetch_text", fail_curl)
    http_client.clear_fetch_cache(url)

    with pytest.raises(URLError):
        http_client.fetch_text(url, timeout=5)

    assert urllib_calls == [url]
    assert len(curl_calls) == 1
    assert not hasattr(http_client, "time")


def test_fetch_text_404_is_recorded_without_curl_fallback(monkeypatch) -> None:
    url = "https://example.test/not-found"
    urllib_calls: list[str] = []
    curl_calls: list[tuple] = []

    def fail_urlopen(*_args, **_kwargs):
        urllib_calls.append(url)
        raise _http_error(url, 404, "not found")

    monkeypatch.setattr(http_client, "urlopen", fail_urlopen)
    monkeypatch.setattr(http_client, "_curl_fetch_text", lambda *args: curl_calls.append(args) or "curl body")
    http_client.clear_fetch_cache(url)

    with pytest.raises(HTTPError):
        http_client.fetch_text(url, timeout=5)

    assert urllib_calls == [url]
    assert curl_calls == []
    assert http_client.FETCH_STATUS[url] == "404"


def test_fetch_text_textual_404_is_recorded_without_curl_fallback(monkeypatch) -> None:
    url = "https://example.test/textual-not-found"
    urllib_calls: list[str] = []
    curl_calls: list[tuple] = []

    def fail_urlopen(*_args, **_kwargs):
        urllib_calls.append(url)
        raise URLError("HTTP Error 404: not found")

    monkeypatch.setattr(http_client, "urlopen", fail_urlopen)
    monkeypatch.setattr(http_client, "_curl_fetch_text", lambda *args: curl_calls.append(args) or "curl body")
    http_client.clear_fetch_cache(url)

    with pytest.raises(URLError):
        http_client.fetch_text(url, timeout=5)

    assert urllib_calls == [url]
    assert curl_calls == []
    assert http_client.FETCH_STATUS[url] == "404"


def test_network_error_text_containing_404_is_not_an_http_404() -> None:
    assert not http_client._is_http_404_error(
        URLError("network route 404 unavailable")
    )


def test_fetch_text_placeholder_uses_one_fixed_curl_fallback(monkeypatch) -> None:
    url = "https://example.test/placeholder"
    urllib_calls: list[str] = []
    curl_calls: list[tuple] = []

    def placeholder_urlopen(*_args, **_kwargs):
        urllib_calls.append(url)
        return _FakeResponse(b"success")

    def fixed_curl(*args):
        curl_calls.append(args)
        return "234期 绝杀一尾 7尾"

    monkeypatch.setattr(http_client, "urlopen", placeholder_urlopen)
    monkeypatch.setattr(http_client, "_curl_fetch_text", fixed_curl)
    http_client.clear_fetch_cache(url)

    assert http_client.fetch_text(url, timeout=5) == "234期 绝杀一尾 7尾"
    assert urllib_calls == [url]
    assert len(curl_calls) == 1
    assert len(curl_calls[0]) == 3


def test_fetch_text_keeps_short_raw_data_without_business_guessing(monkeypatch) -> None:
    url = "https://example.test/short-json"
    curl_calls: list[tuple] = []
    monkeypatch.setattr(http_client, "urlopen", lambda *_args, **_kwargs: _FakeResponse(b'{"x":1}'))
    monkeypatch.setattr(
        http_client,
        "_curl_fetch_text",
        lambda *args: curl_calls.append(args) or "unexpected curl body",
    )
    http_client.clear_fetch_cache(url)

    assert http_client.fetch_text(url, timeout=5) == '{"x":1}'
    assert curl_calls == []


def test_fetch_text_http_500_does_not_retry_with_curl(monkeypatch) -> None:
    url = "https://example.test/server-error"
    curl_calls: list[tuple] = []

    def fail_urlopen(*_args, **_kwargs):
        raise _http_error(url, 500, "server error")

    monkeypatch.setattr(http_client, "urlopen", fail_urlopen)
    monkeypatch.setattr(
        http_client,
        "_curl_fetch_text",
        lambda *args: curl_calls.append(args) or "unexpected curl body",
    )
    http_client.clear_fetch_cache(url)

    with pytest.raises(HTTPError):
        http_client.fetch_text(url, timeout=5)
    assert curl_calls == []
