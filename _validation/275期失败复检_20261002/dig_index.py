"""只读：分析论坛首页 HTML 结构，找 潇洒人生 帖子入口 / 搜索接口。"""
from __future__ import annotations

import re
from pathlib import Path

OUT = Path(__file__).parent
text = (OUT / "raw_bbs_index.html").read_text(encoding="utf-8")

print("len", len(text))
print("topic links", len(set(re.findall(r"topic\.php\?id=(\d+)", text))))
print("ids", sorted(set(re.findall(r"topic\.php\?id=(\d+)", text)), key=int)[:60])
print("\n=== 所有 href/action (去重，前 60) ===")
links = re.findall(r"""(?:href|action)=["']([^"']+)["']""", text)
for link in list(dict.fromkeys(links))[:60]:
    print("  ", link)
print("\n=== 关键词命中 ===")
for kw in ("潇洒", "搜索", "search", "作者", "高手", "下架", "更多", "全部"):
    idxs = [m.start() for m in re.finditer(re.escape(kw), text)][:3]
    for idx in idxs:
        snippet = re.sub(r"\s+", " ", text[max(0, idx - 70) : idx + 90])
        print("  [%s] %s" % (kw, snippet))
print("\n=== 首页表格行样例（含作者名的结构） ===")
for m in list(re.finditer(r"topic\.php\?id=\d+", text))[:6]:
    print("  ---", re.sub(r"\s+", " ", text[max(0, m.start() - 400) : m.start() + 400]))
