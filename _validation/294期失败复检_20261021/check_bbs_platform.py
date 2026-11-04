# -*- coding: utf-8 -*-
"""从项目配置里找出所有 bbs/topic.php 平台的站，测活，找同站群新域名（只读）。"""
from __future__ import annotations

import json
import re
import ssl
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
ctx = ssl._create_unverified_context()
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

sites = json.loads((ROOT / "sites.json").read_text(encoding="utf-8-sig"))
bbs_sites = [s for s in sites if "/bbs/topic.php" in s.get("url", "")]
print("配置里 bbs/topic.php 平台站数", len(bbs_sites))
for s in bbs_sites:
    print(f"   {s['name']:8s} {s['url']}")


def alive(url: str, timeout: int = 12) -> str:
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=timeout, context=ctx) as r:
            return f"{r.status} {len(r.read())}"
    except Exception as exc:  # noqa: BLE001
        return f"ERR {type(exc).__name__}"


print("\n=== 测活 ===")
ok, dead = [], []
for s in bbs_sites:
    r = alive(s["url"])
    tag = "OK " if r.startswith("200") else "DEAD"
    print(f"  {tag} {s['name']:8s} {r:16s} {s['url']}")
    (ok if r.startswith("200") else dead).append(s)

print(f"\n活 {len(ok)} / 死 {len(dead)}")

# 活站所属域名，作为同站群候选
hosts = {re.sub(r"^https?://", "", s["url"]).split("/")[0] for s in ok}
print("\n活站域名:", sorted(hosts))

(OUT / "bbs_platform_sites.json").write_text(
    json.dumps({"bbs_sites": bbs_sites, "alive": ok, "dead": dead}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
