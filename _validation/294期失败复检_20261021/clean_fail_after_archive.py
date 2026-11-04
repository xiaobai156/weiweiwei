# -*- coding: utf-8 -*-
"""封存后清理失败清单：剔除已封存的 11 站记录。

用项目自身写入层 write_optional_fail_file（空清单会自动删除文件）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.persistence import txt_writer  # noqa: E402

FAIL = ROOT.parent / "七类数据统一归纳失败" / "294期-尾-失败.txt"
NAMES = [
    "坚持战斗", "无量寿佛", "再度归来", "童颜鹤发", "一心为民",
    "怪咖小生", "澳彩碼王", "寻宝探码", "财源滚滚", "海角天涯", "昙花一现",
]

if not FAIL.exists():
    print("失败清单不存在，无需清理")
    raise SystemExit(0)

text = FAIL.read_text(encoding="utf-8-sig")
blocks = [b.strip() for b in re.split(r"(?:\r?\n){2,}", text.strip()) if b.strip()]
print("清理前条目", len(blocks))

kept, removed = [], []
for block in blocks:
    head = block.splitlines()[0]
    hit = next((n for n in NAMES if re.match(rf"失败\s+{re.escape(n)}\s", head)), None)
    if hit:
        removed.append(hit)
    else:
        kept.append(head)

txt_writer.write_optional_fail_file(FAIL, kept)
print("剔除", len(removed), "条:", removed)
print("剩余", len(kept), "条")
print("失败文件存在:", FAIL.exists())
