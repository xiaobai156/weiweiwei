from __future__ import annotations

import gzip
import re
import ssl
import subprocess
import sys
import threading
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
    return stripped in {"", "abcabc", "ok", "success"}


def _decode_http_body(raw: bytes, encoding: str = "", charset: str | None = None) -> str:
    content_encoding = (encoding or "").lower()
    if content_encoding == "gzip" or raw.startswith(b"\x1f\x8b"):
        raw = gzip.decompress(raw)
    elif content_encoding == "deflate":
        raw = zlib.decompress(raw)
    selected_charset = (charset or detect_html_charset(raw) or "utf-8").lower()
    if selected_charset in {"gb2312", "gbk"}:
        selected_charset = "gb18030"
    return raw.decode(selected_charset, errors="replace")


def _cache_fetch_result(url: str, text: str) -> str:
    with FETCH_CACHE_LOCK:
        FETCH_CACHE[url] = text
        FETCH_STATUS[url] = "ok"
    return text


def _curl_executable() -> str:
    return "curl.exe" if sys.platform.startswith("win") else "curl"


def _curl_fetch_text(url: str, headers: dict[str, str], timeout: int) -> str:
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


def fetch_text(url: str, timeout: int = 8) -> str:
    with FETCH_CACHE_LOCK:
        cached = FETCH_CACHE.get(url)
    if cached is not None:
        return cached

    primary_error: Exception | None = None
    request = Request(url, headers=DEFAULT_HEADERS)
    context = ssl._create_unverified_context()
    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            raw = response.read()
            encoding = (response.headers.get("Content-Encoding") or "").lower()
            get_charset = getattr(response.headers, "get_content_charset", None)
            header_charset = get_charset() if get_charset is not None else None
        text = _decode_http_body(raw, encoding, header_charset)
        if not _looks_like_placeholder_response(text):
            return _cache_fetch_result(url, text)
        primary_error = RuntimeError("HTTP响应是占位内容")
    except HTTPError as exc:
        with FETCH_CACHE_LOCK:
            FETCH_STATUS[url] = (
                "404"
                if _is_http_404_error(exc)
                else f"error:{type(exc).__name__}: {exc}"
            )
        raise
    except Exception as exc:
        if _is_http_404_error(exc):
            with FETCH_CACHE_LOCK:
                FETCH_STATUS[url] = "404"
            raise
        primary_error = exc

    # A single fixed transport fallback keeps the one known compatibility path
    # without turning a failed request into a header/TLS/retry matrix.
    try:
        text = _curl_fetch_text(url, DEFAULT_HEADERS, timeout)
        if _looks_like_placeholder_response(text):
            raise RuntimeError("curl响应是占位内容")
        return _cache_fetch_result(url, text)
    except Exception as fallback_error:
        final_error = primary_error or fallback_error
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
    return bool(re.search(r"(?:http error|returned error:)\s*404\b", text))
