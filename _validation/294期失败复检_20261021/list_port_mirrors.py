# -*- coding: utf-8 -*-
"""列出书签里全部「带端口」的新式镜像域名，并匹配旧论坛名（只读）。"""
from __future__ import annotations

import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
ent = json.loads((OUT / "bookmark_hosts_all.json").read_text(encoding="utf-8"))["entries"]

PORT_HOST = re.compile(r":\d{2,5}$")

print("=== 带端口的镜像域名条目 ===")
rows = []
for host, items in ent.items():
    if not PORT_HOST.search(host):
        continue
    for url, bname, src in items:
        rows.append((host, bname.strip(), url))
for host, bname, url in sorted(set(rows)):
    print(f"  {host:44s} {bname[:26]:28s} {url}")

print(f"\n共 {len(set(rows))} 条")

print("\n=== 所有「澳门/香港」开头的新式书签 ===")
for host, items in ent.items():
    for url, bname, src in items:
        if bname.strip().startswith(("澳门", "香港")) and PORT_HOST.search(host):
            print(f"  {bname.strip()[:24]:26s} {url}")

(OUT / "port_mirrors.json").write_text(
    json.dumps(sorted(set(rows)), ensure_ascii=False, indent=2), encoding="utf-8"
)
