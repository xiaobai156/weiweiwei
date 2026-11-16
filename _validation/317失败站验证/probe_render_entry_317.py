# -*- coding: utf-8 -*-
"""317：真实渲染入口取证——确认 body 快照是否丢失 content-visibility 区块。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shawei.fetch.browser import render_browser_documents  # noqa: E402

TARGETS = [
    ("刘半仙", "https://smnwgqcm.vkk2k-rpbnk-qtocig.xyz:16677/", "绝杀一尾"),
    ("飞龙在天", "https://anhomo.n03wh-m2skn-wssphn.xyz/", "绝杀一尾"),
    ("跑马图", "https://sxapnxtw.w9lkt-9vch6-idlact.work:17477/", "绝杀二尾"),
]


def main() -> None:
    for name, url, key in TARGETS:
        docs = render_browser_documents(url, 25)
        print(f"=== {name} 文档数={len(docs)}", flush=True)
        for i, doc in enumerate(docs):
            is_html = bool(re.search(r"<[A-Za-z][^>]*>", doc))
            rows = [m for m in re.findall(r"3[01]\d期[^<\n]{0,40}", doc) if key in m]
            print(f"   [{i}] 类型={'html' if is_html else 'text'} 长度={len(doc)} "
                  f"含{key}的数据行={len(rows)} 示例={rows[:3]}", flush=True)


if __name__ == "__main__":
    main()
