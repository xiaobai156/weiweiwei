# -*- coding: utf-8 -*-
"""从全部书签文件提取候选 BBS 域名池，供后续逐站验证（只读）。

要点：
- 我们的 10 个失败站是论坛内的帖子（bbs/topic.php?id=NNNN）
- 每个旧 .xyz 域名 = 一个论坛；要找到同一论坛的新域名
- 书签条目 = 论坛首页，可据名称（如 张扬先生/大掌柜）匹配同族域名的其他记录
"""
from __future__ import annotations

import collections
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

# 我们的 10 个站 + 所在旧域名
SITE_BY_HOST = {
    "1214.775486.xyz": ["坚持战斗", "无量寿佛"],
    "0130190827.673454.xyz": ["再度归来"],
    "67806780827.325346.xyz": ["童颜鹤发"],
    "88888020827.983654.xyz": ["一心为民"],
    "0130190827.657954.xyz": ["怪咖小生"],
    "12388990827.794555.xyz": ["澳彩碼王"],
    "12388990827.688756.xyz": ["寻宝探码", "财源滚滚"],
    "88888020827.997595.xyz": ["海角天涯"],
}

all_entries: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
for path in BOOKMARKS:
    if not path.exists():
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    for url, name in re.findall(r'<A[^>]*HREF="([^"]+)"[^>]*>([^<]*)</A>', text, re.I):
        host = re.sub(r"^https?://", "", url).split("/")[0].lower()
        all_entries[host].append((url.strip(), name.strip(), path.name))

print("书签涉及域名总数", len(all_entries))

# 1) 每个旧域名，找同名前缀族的其他域名（数字前缀相同的轮换域名）
print("\n=== 按数字前缀族归并（旧域名 + 兄弟域名）===")
def prefix(host: str) -> str:
    m = re.match(r"^(\d{4,})\.", host)
    return m.group(1) if m else ""

family: dict[str, list[str]] = collections.defaultdict(list)
for host in all_entries:
    p = prefix(host)
    if p:
        family[p].append(host)

for host, sites in SITE_BY_HOST.items():
    p = prefix(host)
    print(f"\n旧域名 {host}  站={sites}  前缀族={p}")
    for sibling in sorted(family.get(p, [])):
        names = [n for _, n, _ in all_entries[sibling]][:3]
        mark = " <=旧" if sibling == host else ""
        print(f"    {sibling}{mark}  书签名={names}")

# 2) 全部 bbs 类域名
print("\n=== 全部含 /bbs 的候选域名 ===")
bbs_hosts = {}
for host, items in all_entries.items():
    if any("/bbs" in u for u, _, _ in items):
        bbs_hosts[host] = items[0]
for host in sorted(bbs_hosts):
    url, name, src = bbs_hosts[host]
    print(f"    {host:40s} {name[:26]:28s} {url}")

(OUT / "bookmark_hosts_all.json").write_text(
    json.dumps(
        {
            "entries": {h: v for h, v in all_entries.items()},
            "families": {k: sorted(v) for k, v in family.items()},
            "bbs_hosts": sorted(bbs_hosts),
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
print("\n已写出 bookmark_hosts_all.json")
