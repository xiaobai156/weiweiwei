"""只读：抽取 bbsapiext.php / topicapiext.php 的调用参数，尝试用接口验证帖子状态。"""
from __future__ import annotations

import json
import re
from pathlib import Path

OUT = Path(__file__).parent

for fname in ("raw_topic_30780.html", "raw_bbs_index.html", "raw_rcg.html"):
    path = OUT / fname
    if not path.exists():
        continue
    text = path.read_text(encoding="utf-8")
    print("=" * 20, fname, "len", len(text))
    for kw in ("apiext", "ajax", "action=", "post("):
        for i, m in enumerate(re.finditer(re.escape(kw), text)):
            if i >= 6:
                break
            seg = re.sub(r"\s+", " ", text[max(0, m.start() - 160) : m.start() + 260])
            print(f"  [{kw}] {seg}")
    print()
