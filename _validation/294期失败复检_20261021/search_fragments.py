# -*- coding: utf-8 -*-
"""用旧域名里的数字片段，在全部书签里找同族轮换域名（只读）。

旧域名形如 <前缀>.<数字6>.xyz，数字片段可能是站群固定编号：
775486 / 673454 / 325346 / 983654 / 657954 / 794555 / 688756 / 997595
"""
from __future__ import annotations

import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
BOOKMARKS = [
    Path(r"C:\Users\Administrator\Desktop\每天工具\关键字扫描\bookmarks_2026_8_26.html"),
    Path(r"C:\Users\Administrator\Desktop\新建文件夹\bookmarks_2026_8_26.html"),
    Path(r"C:\Users\Administrator\Desktop\bookmarks_2026_8_27.html"),
    Path(r"C:\Users\Administrator\Documents\Codex\2026-08-26\zuo\outputs\bookmarks_2026_8_26.html"),
    Path(r"C:\Users\Administrator\Documents\Codex\2026-08-26\zuo\work\keyword_scanner\bookmarks_2026_8_26.html"),
]

FRAGMENTS = {
    "775486": ["坚持战斗", "无量寿佛"],
    "673454": ["再度归来"],
    "325346": ["童颜鹤发"],
    "983654": ["一心为民"],
    "657954": ["怪咖小生"],
    "794555": ["澳彩碼王"],
    "688756": ["寻宝探码", "财源滚滚"],
    "997595": ["海角天涯"],
}

all_text = ""
for path in BOOKMARKS:
    if path.exists():
        all_text += "\n" + path.read_text(encoding="utf-8", errors="replace")

urls = re.findall(r'(?:href|HREF)="([^"]+)"', all_text)
hosts = sorted({re.sub(r"^https?://", "", u).split("/")[0].lower() for u in urls})
print("书签域名总数", len(hosts))

print("\n=== 按数字片段搜索 ===")
hits: dict[str, list[str]] = {}
for frag, sites in FRAGMENTS.items():
    matched = [h for h in hosts if frag in h]
    hits[frag] = matched
    print(f"\n片段 {frag}  站={sites}")
    if not matched:
        print("   （书签里没有同片段域名）")
    for h in matched:
        print(f"   {h}")

# 更宽：按「数字前缀」搜索
print("\n=== 按数字前缀搜索 ===")
PREFIX = {
    "1214": ["坚持战斗", "无量寿佛"],
    "0130190827": ["再度归来", "怪咖小生"],
    "12388990827": ["澳彩碼王", "寻宝探码", "财源滚滚"],
    "67806780827": ["童颜鹤发"],
    "88888020827": ["一心为民", "海角天涯"],
}
for p, sites in PREFIX.items():
    matched = [h for h in hosts if h.startswith(p)]
    print(f"\n前缀 {p} 站={sites}")
    for h in matched:
        print(f"   {h}")

(OUT / "fragment_hits.json").write_text(
    json.dumps({"fragments": hits, "hosts": hosts}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

# 额外：把书签里所有非主流 TLD 域名列出来（新域名常见 .shop/.top/.cyou/.vip）
print("\n=== 非 .xyz/.com 的候选域名（新站群常用后缀）===")
for h in hosts:
    if re.search(r"\.(shop|top|cyou|vip|icu|cc|buzz|site|online|club)$", h):
        print("  ", h)
