# -*- coding: utf-8 -*-
"""从活着的论坛页面里挖出全部外链域名（站群互推），从中找我们 8 个旧域名的同族新域名（只读）。

思路：老站群常年互挂导航，新域名往往和同族一起出现。
输出：全部外链 host + 是否含我们旧域名数字片段。
"""
from __future__ import annotations

import collections
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
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
OLD_HOSTS = {
    "1214.775486.xyz", "0130190827.673454.xyz", "67806780827.325346.xyz",
    "88888020827.983654.xyz", "0130190827.657954.xyz", "12388990827.794555.xyz",
    "12388990827.688756.xyz", "88888020827.997595.xyz",
}

hosts: collections.Counter = collections.Counter()
per_file: dict[str, set[str]] = {}

for f in sorted(OUT.glob("forum_*.html")):
    text = f.read_text(encoding="utf-8", errors="replace")
    found = {
        re.sub(r"^https?://", "", u).split("/")[0].lower()
        for u in re.findall(r'https?://([^"\'\s<>]+)', text)
    }
    per_file[f.name] = found
    for h in found:
        hosts[h] += 1

print("活跃论坛页面外链域名总数", len(hosts))

print("\n=== 命中我们旧域名数字片段的域名 ===")
hit_any = False
for host in sorted(hosts):
    for frag, sites in FRAGMENTS.items():
        if frag in host and host not in OLD_HOSTS:
            hit_any = True
            print(f"  {host}  片段={frag} 站={sites}")
if not hit_any:
    print("  （无）")

print("\n=== 全部 .shop / .top / .cyou / .vip 类域名（新站群特征）===")
newish = [h for h in hosts if re.search(r"\.(shop|top|cyou|vip)$", h)]
for h in sorted(newish):
    print(f"  {h}  出现 {hosts[h]} 次")

print("\n=== 含 bbs 的域名 ===")
for h in sorted(hosts):
    if "bbs" in h:
        print(f"  {h}  x{hosts[h]}")

(OUT / "forum_outlinks.json").write_text(
    str(sorted(hosts)), encoding="utf-8"
)
