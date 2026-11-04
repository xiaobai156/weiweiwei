# -*- coding: utf-8 -*-
"""书签候选域名：先测活，再逐站核对 294 期（只读）。

阶段 1：对候选 origin 的 /bbs/ 首页发请求，记录 HTTP 状态
阶段 2：对活着的 origin，试 /bbs/topic.php?id=<目标ID>，并比对站名
"""
from __future__ import annotations

import json
import re
import ssl
import sys
from pathlib import Path
from urllib.request import Request, urlopen

OUT = Path(__file__).resolve().parent
PERIOD = 294
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
ctx = ssl._create_unverified_context()

SITES = {
    "坚持战斗": "20200",
    "无量寿佛": "20198",
    "再度归来": "20144",
    "童颜鹤发": "19812",
    "一心为民": "20758",
    "怪咖小生": "20210",
    "澳彩碼王": "21353",
    "寻宝探码": "18520",
    "财源滚滚": "19930",
    "海角天涯": "18490",
}

CANDIDATES = [
    "https://pa4dwcnd64.772149.shop",
    "https://i97lk4jb16.333741bbs1.shop",
    "https://5ipaulfv56.1081085bbs1.shop",
    "https://b7sz3gaw48.552149.shop",
    "https://z0gcdiww42.669332.shop",
    "https://sk7-fago.388998bbs-xlu3.top",
    "https://bbs02.341627.cyou",
    "https://bbs02.836280.cyou",
    "https://bbs03.836386.cyou",
    "https://bbs06.933558.vip",
    "https://bbs28.880280.xyz",
    "https://bbs8.1395200.com",
    "https://nlafoq9v.dh5565656.xyz",
    "https://0085680827.326455.xyz",
    "https://0130190808.345745.xyz",
    "https://0130190808.880646.xyz",
    "https://11008880827.456732.xyz",
    "https://11008880827.876657.xyz",
    "https://11889900827.435458.xyz",
    "https://6609960827.115646.xyz",
    "https://6609960827.456732.xyz",
    "https://66778800827.909776.xyz",
    "https://67806780827.234535.xyz",
    "https://67806780827.978754.xyz",
    "https://88888020827.833567.xyz",
    "https://88888020827.885536.xyz",
    "https://88888020827.897657.xyz",
]


def get(url: str, timeout: int = 15) -> tuple[int, str]:
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=timeout, context=ctx) as r:
            raw = r.read()
            code = r.status
    except Exception as exc:  # noqa: BLE001
        return 0, f"ERR {type(exc).__name__}: {str(exc)[:80]}"
    for enc in ("utf-8", "gb18030"):
        try:
            return code, raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return code, raw.decode("utf-8", errors="replace")


alive: list[tuple[str, str]] = []
print("=== 阶段1 测活 ===")
for base in CANDIDATES:
    code, body = get(base + "/bbs/")
    if code == 0:
        print(f"  DEAD  {base}  {body[:60]}")
        continue
    alive.append((base, body))
    hit = [n for n in SITES if n in body]
    print(f"  OK {code} {len(body):7d}  {base}  含站名={hit}")

print(f"\n活站 {len(alive)} / {len(CANDIDATES)}")

print("\n=== 阶段2 逐站试 topic.php ===")
found: dict[str, dict] = {}
for name, tid in SITES.items():
    for base, _ in alive:
        url = f"{base}/bbs/topic.php?id={tid}"
        code, body = get(url)
        if code != 200 or not body:
            continue
        if name not in body:
            continue
        periods = sorted({int(x) for x in re.findall(r"(?<!\d)(\d{2,4})\s*期", body)})
        rec = {
            "site": name,
            "tid": tid,
            "base": base,
            "url": url,
            "code": code,
            "len": len(body),
            "has_period": PERIOD in periods,
            "periods_tail": periods[-6:],
        }
        found[name] = rec
        print(f"  ✅ {name} -> {url}  294={rec['has_period']} 期数={rec['periods_tail']}")
        break
    else:
        print(f"  ❌ {name} 未在活站中命中")

(OUT / "host_probe_294.json").write_text(
    json.dumps({"alive": [b for b, _ in alive], "found": found}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print("\n命中", len(found), "/", len(SITES))
