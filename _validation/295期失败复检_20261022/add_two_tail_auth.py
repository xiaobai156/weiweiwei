# -*- coding: utf-8 -*-
"""把「再度归来」新 URL 加入双尾授权表 TWO_TAIL_SITE_URLS（旧条目保留）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.persistence.atomic_file import _atomic_write_text_unlocked, file_lock  # noqa: E402

CONST = ROOT / "shawei" / "config" / "constants.py"
OLD = "https://0130190827.673454.xyz/bbs/topic.php?id=20144"
NEW = "https://0130190827.673454.xyz/bbs/topic.php?id=20330"

with file_lock(CONST):
    text = CONST.read_text(encoding="utf-8")
    if f'"{NEW}"' in text:
        print("新地址已在双尾授权表")
    else:
        line = f'    "{OLD}",'
        if line not in text:
            raise SystemExit(f"未找到旧条目: {line}")
        text = text.replace(line, line + "\n" + f'    "{NEW}",', 1)
        _atomic_write_text_unlocked(CONST, text, encoding="utf-8")
        print("已加入双尾授权表")

# 校验
from shawei.config.constants import TWO_TAIL_SITE_URLS  # noqa: E402
print("新地址在授权表:", NEW in TWO_TAIL_SITE_URLS, "| 条目总数:", len(TWO_TAIL_SITE_URLS))
