# -*- coding: utf-8 -*-
"""315 期两台 TLS 报错站点的链路取证：静态请求 + Chromium 两种栈各试。"""
from __future__ import annotations

import socket
import ssl
import urllib.error
import urllib.request

URLS = (
    ("无量寿佛", "https://1214.775486.xyz/bbs/topic.php?id=20198"),
    ("一心为民", "https://88888020827.983654.xyz/bbs/topic.php?id=20915"),
)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def probe_static(name: str, url: str) -> None:
    host = url.split("/")[2]
    try:
        ips = sorted({info[4][0] for info in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)})
    except Exception as exc:  # noqa: BLE001
        print(f"[{name}] DNS 失败 {type(exc).__name__}: {exc}")
        return
    print(f"[{name}] DNS {host} -> {ips}")
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((host, 443), timeout=10) as raw:
            with ctx.wrap_socket(raw, server_hostname=host) as tls:
                print(f"[{name}] 直接 TLS 握手 OK, 证书CN={dict(x[0] for x in tls.getpeercert()['subject'])}")
    except Exception as exc:  # noqa: BLE001
        print(f"[{name}] 直接 TLS 失败 {type(exc).__name__}: {exc}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            body = resp.read()
            print(f"[{name}] urllib OK {resp.status} {len(body)} bytes")
            return
    except urllib.error.HTTPError as exc:
        body = exc.read()
        print(f"[{name}] urllib HTTPError {exc.code} {len(body)} bytes")
        return
    except Exception as exc:  # noqa: BLE001
        print(f"[{name}] urllib 失败 {type(exc).__name__}: {exc}")


def probe_browser(name: str, url: str) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            text = page.inner_text("body")[:400]
            print(f"[{name}] Chromium OK status={resp.status if resp else None} 正文前 400 字:")
            print(text.replace("\n", " | ")[:400])
        except Exception as exc:  # noqa: BLE001
            print(f"[{name}] Chromium 失败 {type(exc).__name__}: {str(exc)[:200]}")
        finally:
            browser.close()


def main() -> None:
    for name, url in URLS:
        probe_static(name, url)
        probe_browser(name, url)
        print("-" * 60)


if __name__ == "__main__":
    main()
