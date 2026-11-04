# -*- coding: utf-8 -*-
"""按「论坛名」在全部书签里找同一论坛的多个域名（只读）。

旧域名对应的论坛名（来自书签）：
1214.775486.xyz        -> 张扬先生139779com
0130190827.673454.xyz  -> 大掌柜
12388990827.794555.xyz -> 金算盘
12388990827.688756.xyz -> 聚贤庄
67806780827.325346.xyz -> 玲珑
88888020827.983654.xyz -> 公式王
88888020827.997595.xyz -> 澳门财神
0130190827.657954.xyz  -> 曾道人
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
FORUM_NAMES = [
    "张扬先生", "大掌柜", "金算盘", "聚贤庄", "玲珑",
    "公式王", "澳门财神", "曾道人",
]

ent = json.loads((OUT / "bookmark_hosts_all.json").read_text(encoding="utf-8"))["entries"]

print("书签域名数", len(ent))
print("\n=== 按论坛名精确匹配（书签名 equals/startswith）===")
for name in FORUM_NAMES:
    rows = []
    for host, items in ent.items():
        for url, bname, src in items:
            if bname.strip() == name or bname.strip().startswith(name):
                rows.append((host, url, bname.strip(), src))
    print(f"\n{name}: {len(rows)} 条")
    seen = set()
    for host, url, bname, src in rows:
        if (host, url) in seen:
            continue
        seen.add((host, url))
        print(f"    {host:34s} {bname[:24]:26s} {url}")

print("\n=== 全库中名称含关键词的条目（模糊）===")
KEYS = ["张扬", "大掌柜", "金算盘", "聚贤庄", "玲珑", "公式王", "财神", "曾道人"]
for key in KEYS:
    rows = []
    for host, items in ent.items():
        for url, bname, src in items:
            if key in bname:
                rows.append((host, bname.strip(), url))
    uniq = list(dict.fromkeys(rows))
    print(f"\n关键词 {key}: {len(uniq)} 条")
    for host, bname, url in uniq[:8]:
        print(f"    {host:34s} {bname[:26]:28s} {url}")

(OUT / "forum_name_hits.json").write_text(
    json.dumps(ent, ensure_ascii=False, indent=2), encoding="utf-8"
)
