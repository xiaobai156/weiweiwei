# -*- coding: utf-8 -*-
"""有无可用替代入口：http 明文 / 无 SNI / 不同 SNI。"""
from __future__ import annotations

import socket
import ssl
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"
TARGETS = (
    ("无量寿佛", "1214.775486.xyz", "/bbs/topic.php?id=20198"),
    ("一心为民", "88888020827.983654.xyz", "/bbs/topic.php?id=20915"),
)


def main() -> None:
    for name, host, path in TARGETS:
        print(f"== {name} ({host}) ==")
        for scheme in ("http", "https"):
            url = f"{scheme}://{host}{path}"
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    body = resp.read()
                    print(f"  {scheme} -> {resp.status} {len(body)} bytes")
            except Exception as exc:  # noqa: BLE001
                print(f"  {scheme} -> {type(exc).__name__}: {str(exc)[:120]}")
        for sni in (None, "1214.775486.xyz", host):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            try:
                with socket.create_connection((host, 443), timeout=10) as raw:
                    with ctx.wrap_socket(raw, server_hostname=sni) as tls:
                        cert = tls.getpeercert()
                        print(f"  SNI={sni!r} -> OK, 证书主题={dict(x[0] for x in cert['subject'])}")
            except Exception as exc:  # noqa: BLE001
                print(f"  SNI={sni!r} -> {type(exc).__name__}: {str(exc)[:100]}")


if __name__ == "__main__":
    main()
