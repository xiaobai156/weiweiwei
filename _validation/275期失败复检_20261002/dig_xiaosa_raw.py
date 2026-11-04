"""只读：抽取潇洒人生帖子原始 HTML 的导航/链接证据（不写正式文件）。"""
from __future__ import annotations

import json
import re
from pathlib import Path

OUT = Path(__file__).parent
d = json.loads((OUT / "probe_xiaosa_out.json").read_text(encoding="utf-8"))
raw = d.get("raw_head", "")

print("=== raw head (whitespace collapsed) ===")
print(re.sub(r"\s+", " ", raw)[:1600])
print("\n=== links ===")
links = re.findall(r"""(?:href|src|action)=["']([^"']+)["']""", raw)
for link in dict.fromkeys(links):
    print(link)
print("\n=== 关键中文片段 ===")
for kw in ("下架", "删除", "不存在", "潇洒", "275", "274"):
    idx = raw.find(kw)
    print(kw, "->", idx, (re.sub(r"\s+", " ", raw[max(0, idx - 60) : idx + 80]) if idx >= 0 else ""))
