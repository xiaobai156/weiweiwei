# -*- coding: utf-8 -*-
"""316：无量寿佛/一心为民 SNI 故障复查（只读探针，不发正式请求）。"""
from __future__ import annotations

import socket
import ssl
import sys

TARGETS = [
    ("无量寿佛", "1214.775486.xyz", 443),
    ("一心为民", "88888020827.983654.xyz", 443),
    ("对照-baidu", "www.baidu.com", 443),
]


def probe(host: str, port: int, sni: str | None) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = bool(sni)
    ctx.verify_mode = ssl.CERT_REQUIRED if sni else ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=12) as raw:
            with ctx.wrap_socket(raw, server_hostname=sni) as tls:
                cert = tls.getpeercert()
                names = [v for k, v in cert.get("subjectAltName", []) if k == "DNS"] if cert else []
                return f"OK proto={tls.version()} SAN={names[:4]}"
    except Exception as exc:  # noqa: BLE001 - 探针需要原始错误文本
        return f"{type(exc).__name__}: {exc}"


def main() -> None:
    for name, host, port in TARGETS:
        try:
            addrs = sorted({info[4][0] for info in socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)})
        except Exception as exc:  # noqa: BLE001
            addrs = [f"DNS失败 {exc}"]
        print(f"[{name}] {host} -> {addrs}", flush=True)
        print(f"   带SNI: {probe(host, port, host)}", flush=True)
        print(f"   无SNI: {probe(host, port, None)}", flush=True)
    sys.stdout.flush()


if __name__ == "__main__":
    main()
