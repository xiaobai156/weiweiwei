# -*- coding: utf-8 -*-
"""同编号不同后缀探测：旧域名标签保持不变，换 TLD 找新站（只读）。

旧域名：1214.775486.xyz / 0130190827.673454.xyz / 67806780827.325346.xyz
       88888020827.983654.xyz / 0130190827.657954.xyz / 12388990827.794555.xyz
       12388990827.688756.xyz / 88888020827.997595.xyz
"""
from __future__ import annotations

import json
import socket
import ssl
from pathlib import Path
from urllib.request import Request, urlopen

OUT = Path(__file__).resolve().parent
ctx = ssl._create_unverified_context()
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

OLD = [
    "1214.775486.xyz",
    "0130190827.673454.xyz",
    "67806780827.325346.xyz",
    "88888020827.983654.xyz",
    "0130190827.657954.xyz",
    "12388990827.794555.xyz",
    "12388990827.688756.xyz",
    "88888020827.997595.xyz",
]
TLDS = ["shop", "top", "cyou", "vip", "cc", "icu", "work", "com", "net", "buzz", "site", "online"]


def dns_ok(host: str) -> bool:
    try:
        socket.getaddrinfo(host, None)
        return True
    except Exception:  # noqa: BLE001
        return False


def http_probe(url: str) -> str:
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=12, context=ctx) as r:
            return f"{r.status} {len(r.read())}"
    except Exception as exc:  # noqa: BLE001
        return f"ERR {type(exc).__name__}"


results = []
for old in OLD:
    label, _, _ = old.partition(".xyz")
    print(f"\n=== {old}  (label={label})")
    for tld in TLDS:
        host = f"{label}.{tld}"
        if not dns_ok(host):
            continue
        out = http_probe(f"https://{host}/bbs/")
        print(f"   DNS-OK  {host:34s} https/bbs -> {out}")
        results.append({"old": old, "host": host, "resp": out})

(OUT / "same_label_probe.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("\nDNS 命中数", len(results))
