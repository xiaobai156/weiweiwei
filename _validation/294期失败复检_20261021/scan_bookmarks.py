# -*- coding: utf-8 -*-
"""从浏览器书签里找 294 期 8 个 .xyz 站点的镜像/新地址（只读）。

线索：
- 旧域名形态：数字.数字.xyz + /bbs/topic.php?id=NNNN
- 站名：坚持战斗 无量寿佛 再度归来 童颜鹤发 一心为民 怪咖小生 澳彩碼王 寻宝探码 财源滚滚 海角天涯
策略：
1) 扫书签全部 href，按域名聚合，列出 .xyz / 含 bbs/topic.php 的
2) 逐条找 包含 topic.php?id=<目标ID> 的链接
3) 找 站名 出现处的相邻链接
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path

BOOKMARKS = [
    Path(r"C:\Users\Administrator\Desktop\每天工具\关键字扫描\bookmarks_2026_8_26.html"),
    Path(r"C:\Users\Administrator\Desktop\每天工具\关键字扫描\源码\bookmarks_2026_8_26.html"),
    Path(r"C:\Users\Administrator\Desktop\新建文件夹\bookmarks_2026_8_26.html"),
    Path(r"C:\Users\Administrator\Desktop\bookmarks_2026_8_27.html"),
]
OUT = Path(__file__).resolve().parent

SITE_IDS = {
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
OLD_HOSTS = {
    "1214.775486.xyz", "0130190827.673454.xyz", "67806780827.325346.xyz",
    "88888020827.983654.xyz", "12388990827.794555.xyz", "12388990827.688756.xyz",
    "88888020827.997595.xyz", "0130190827.657954.xyz",
}

for path in BOOKMARKS:
    if not path.exists():
        continue
    print("=" * 70)
    print("书签文件:", path, path.stat().st_size, "B")
    text = path.read_text(encoding="utf-8", errors="replace")
    # 书签格式：<DT><A HREF="url" ...>名称</A>
    entries = re.findall(
        r'<A[^>]*HREF="([^"]+)"[^>]*>([^<]*)</A>', text, re.I
    )
    print("书签条目", len(entries))

    hosts = collections.Counter(
        re.sub(r"^https?://", "", u).split("/")[0].lower() for u, _ in entries
    )
    xyz = {h: c for h, c in hosts.items() if h.endswith(".xyz")}
    print("唯一域名", len(hosts), "｜ .xyz 域名", len(xyz))

    # 1) 命中旧域名
    hit_old = [(u, n) for u, n in entries
               if re.sub(r"^https?://", "", u).split("/")[0].lower() in OLD_HOSTS]
    print(f"\n[旧域名直接命中] {len(hit_old)} 条")
    for u, n in hit_old[:20]:
        print("   ", n[:30], "->", u)

    # 2) 按 topic.php?id 命中目标 ID
    print(f"\n[按 topic id 命中]")
    for site, tid in SITE_IDS.items():
        pats = re.findall(rf'href="([^"]*[?&]id={tid}\b[^"]*)"', text, re.I)
        if pats:
            print(f"   {site} (id={tid}):")
            for p in dict.fromkeys(pats):
                print("       ", p)

    # 3) 站名出现处
    print(f"\n[按站名命中]")
    for site in SITE_IDS:
        if site in text:
            idx = text.find(site)
            seg = text[max(0, idx - 300): idx + 200]
            hrefs = re.findall(r'href="([^"]+)"', seg, re.I)
            print(f"   {site}: 出现；邻近链接 {hrefs[:3]}")

    # 4) 列出全部 .xyz 域名（按出现次数）
    print(f"\n[全部 .xyz 域名]")
    for h, c in sorted(xyz.items(), key=lambda kv: -kv[1]):
        mark = " <= 旧域名" if h in OLD_HOSTS else ""
        print(f"   {h}  x{c}{mark}")

    (OUT / f"bookmark_hosts_{path.stem}.json").write_text(
        json.dumps({"entries": entries[:5000], "hosts": hosts}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
