# -*- coding: utf-8 -*-
"""封存后清理 297 期失败清单中「再度归来」的记录（走项目写入层）。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.persistence import txt_writer  # noqa: E402

FAIL = ROOT.parent / "七类数据统一归纳失败" / "297期-尾-失败.txt"
NAME = "再度归来"

if not FAIL.exists():
    print("失败清单不存在")
    raise SystemExit(0)

text = FAIL.read_text(encoding="utf-8-sig")
blocks = [b.strip() for b in re.split(r"(?:\r?\n){2,}", text.strip()) if b.strip()]
kept, removed = [], []
for block in blocks:
    head = block.splitlines()[0]
    if re.match(rf"失败\s+{re.escape(NAME)}\s", head):
        removed.append(NAME)
    else:
        kept.append(head)

txt_writer.write_optional_fail_file(FAIL, kept)
print(f"剔除 {len(removed)} 条，剩余 {len(kept)} 条")
print("剩余站点:", [h.split(" ")[1] for h in kept])
print("失败文件存在:", FAIL.exists())
