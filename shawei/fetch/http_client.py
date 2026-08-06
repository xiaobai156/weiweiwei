from __future__ import annotations

import gzip
import ssl
import subprocess
import sys
import threading
import time
import zlib
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from shawei.config.constants import DEFAULT_HEADERS
from shawei.domain.models import Record
from shawei.fetch.decoding import detect_html_charset


FETCH_CACHE: dict[str, str] = {}


FETCH_STATUS: dict[str, str] = {}


FETCH_CHILDREN: dict[str, set[str]] = {}


FETCH_CACHE_LOCK = threading.Lock()


RENDER_CACHE: dict[tuple[str, int], list[str]] = {}


RENDER_STATUS: dict[tuple[str, int], str] = {}


RECORD_CACHE: dict[tuple[str, str, str, int, int | None], list["Record"]] = {}


RUNTIME_CACHE_LOCK = threading.Lock()


def _looks_like_placeholder_response(text: str) -> bool:
    stripped = (text or "").strip().strip("'\"").lower()
    return stripped in {"abcabc", "ok", "success"} or (len(stripped) <= 12 and "<" not in stripped and "期" not in stripped)


def _decode_http_body(raw: bytes, encoding: str = "", charset: str | None = None) -> str:
    content_encoding = (encoding or "").lower()
    if content_encoding == "gzip" or raw.startswith(b"\x1f\x8b"):
        raw = gzip.decompress(raw)
    elif content_encoding == "deflate":
        raw = zlib.decompress(raw)
    return raw.decode(charset or detect_html_charset(raw) or "utf-8", errors="replace")


def _cache_fetch_result(url: str, text: str) -> str:
    with FETCH_CACHE_LOCK:
        FETCH_CACHE[url] = text
        FETCH_STATUS[url] = "ok"
    return text


def _curl_executable() -> str:
    return "curl.exe" if sys.platform.startswith("win") else "curl"


def _curl_fetch_text(url: str, headers: dict[str, str], timeout: int, extra_args: tuple[str, ...] = ()) -> str:
    command = [
        _curl_executable(),
        "-L",
        "--compressed",
        "--fail",
        "--silent",
        "--show-error",
        "--insecure",
        "--connect-timeout",
        str(max(3, timeout)),
        "--max-time",
        str(max(5, timeout + 3)),
        *extra_args,
    ]
    for key, value in headers.items():
        if key.lower() == "accept-encoding":
            continue
        command.extend(["-H", f"{key}: {value}"])
    command.append(url)
    completed = subprocess.run(command, capture_output=True, timeout=max(8, timeout + 5))
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"curl exit {completed.returncode}: {stderr}")
    return _decode_http_body(completed.stdout)


def _curl_fallback_variants(error: Exception) -> list[tuple[str, ...]]:
    lowered = str(error).lower()
    variants: list[tuple[str, ...]] = [
        ("--http1.1",),
        ("--http1.1", "--ssl-no-revoke"),
    ]
    if "schannel" in lowered or "ssl" in lowered or "tls" in lowered or "handshake" in lowered or "eof occurred" in lowered:
        variants.extend(
            [
                ("--http1.1", "--ssl-no-revoke", "--tlsv1.2"),
                ("--http1.1", "--tlsv1.2"),
            ]
        )
    if "http error 502" in lowered or "bad gateway" in lowered:
        variants.extend([("--http1.1", "--retry", "1", "--retry-delay", "1")])
    return variants


def fetch_text(url: str, timeout: int = 8) -> str:
    with FETCH_CACHE_LOCK:
        cached = FETCH_CACHE.get(url)
    if cached is not None:
        return cached

    last_error: Exception | None = None
    header_variants = [DEFAULT_HEADERS, {key: value for key, value in DEFAULT_HEADERS.items() if key.lower() != "accept-encoding"}]
    for headers in header_variants:
        for attempt in range(2):
            request = Request(url, headers=headers)
            context = ssl._create_unverified_context()
            try:
                with urlopen(request, timeout=timeout, context=context) as response:
                    raw = response.read()
                    encoding = (response.headers.get("Content-Encoding") or "").lower()
                    header_charset = response.headers.get_content_charset()
                text = _decode_http_body(raw, encoding, header_charset)
                if _looks_like_placeholder_response(text) and headers is DEFAULT_HEADERS:
                    break
                return _cache_fetch_result(url, text)
            except Exception as exc:
                last_error = exc
                if attempt >= 1:
                    break
                time.sleep(0.3 * (attempt + 1))

    for headers in header_variants:
        for extra_args in _curl_fallback_variants(last_error or RuntimeError("fetch failed")):
            try:
                text = _curl_fetch_text(url, headers, timeout, extra_args)
                if _looks_like_placeholder_response(text) and headers is DEFAULT_HEADERS:
                    continue
                return _cache_fetch_result(url, text)
            except Exception as exc:
                last_error = exc
    final_error = last_error or RuntimeError("fetch failed")
    with FETCH_CACHE_LOCK:
        FETCH_STATUS[url] = "404" if _is_http_404_error(final_error) else f"error:{type(final_error).__name__}: {final_error}"
    raise final_error


def _related_fetch_urls(url: str) -> set[str]:
    # Imported lazily to keep the network transport independent from the
    # higher-level dynamic document adapters during module initialization.
    from shawei.fetch.dynamic_article import (
        admin_article_api_urls,
        admin_article_landing_data_url,
        manager_article_api_urls,
    )
    from shawei.fetch.profile import (
        forum_detail_api_urls,
        spa_user_forum_api_urls,
        user_release_api_urls,
    )

    related = {url}
    related.update(admin_article_api_urls(url))
    related.update(manager_article_api_urls(url))
    related.update(user_release_api_urls(url))
    related.update(spa_user_forum_api_urls(url))
    related.update(forum_detail_api_urls(url))
    landing = admin_article_landing_data_url(url)
    if landing is not None:
        related.add(landing[1])
    related.update(FETCH_CHILDREN.get(url, set()))
    return related


def clear_fetch_cache(url: str | None = None) -> None:
    with FETCH_CACHE_LOCK:
        if url is None:
            FETCH_CACHE.clear()
            FETCH_STATUS.clear()
            FETCH_CHILDREN.clear()
        else:
            for related_url in _related_fetch_urls(url):
                FETCH_CACHE.pop(related_url, None)
                FETCH_STATUS.pop(related_url, None)
            FETCH_CHILDREN.pop(url, None)
    with RUNTIME_CACHE_LOCK:
        if url is None:
            RENDER_CACHE.clear()
            RENDER_STATUS.clear()
            RECORD_CACHE.clear()
        else:
            for key in [key for key in RENDER_CACHE if key[0] == url]:
                RENDER_CACHE.pop(key, None)
            for key in [key for key in RENDER_STATUS if key[0] == url]:
                RENDER_STATUS.pop(key, None)
            for key in [key for key in RECORD_CACHE if key[0] == url]:
                RECORD_CACHE.pop(key, None)


def _is_http_404_error(exc: Exception) -> bool:
    if isinstance(exc, HTTPError) and exc.code == 404:
        return True
    text = str(exc).lower()
    return "http error 404" in text or "returned error: 404" in text or " 404" in text
