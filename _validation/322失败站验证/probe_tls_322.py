"""gboqrz 主机 TLS 取证：SSL 协议错误是本机链路还是站方配置。"""

from __future__ import annotations

import json
import socket
import ssl
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
HOSTS = [
    ("gboqrz.sm0a0-x9x2c-xyvjdr.work", 443),
    ("www.baidu.com", 443),
    ("bemenx.rsaha-bn3j2-tjpxnk.xyz", 16677),
]


def probe(host: str, port: int) -> dict:
    info: dict = {"host": host, "port": port}
    try:
        info["dns"] = sorted({item[4][0] for item in socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)})
    except Exception as exc:
        info["dns_error"] = f"{type(exc).__name__}: {exc}"
        return info
    for label, sni in (("带SNI", host), ("无SNI", None)):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            with socket.create_connection((host, port), timeout=15) as sock:
                with ctx.wrap_socket(sock, server_hostname=sni) as tls:
                    info[label] = {"ok": True, "version": tls.version(), "cipher": tls.cipher()[0]}
        except Exception as exc:
            info[label] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    try:
        import requests

        for scheme in ("https", "http"):
            url = f"{scheme}://{host}:{port}/" if port != 443 else f"{scheme}://{host}/"
            try:
                resp = requests.get(url, timeout=20, verify=False, headers={"User-Agent": "Mozilla/5.0"})
                info[f"requests_{scheme}"] = {"status": resp.status_code, "len": len(resp.text), "head": resp.text[:120]}
            except Exception as exc:
                info[f"requests_{scheme}"] = {"error": f"{type(exc).__name__}: {str(exc)[:160]}"}
    except ImportError:
        pass
    return info


def main() -> None:
    import urllib3

    urllib3.disable_warnings()
    report = [probe(host, port) for host, port in HOSTS]
    (OUT / "probe_tls_322.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for row in report:
        print("=" * 20, row["host"])
        print(json.dumps(row, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
