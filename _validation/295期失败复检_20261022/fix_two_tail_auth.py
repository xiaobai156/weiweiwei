# -*- coding: utf-8 -*-
"""双尾授权表：把已无站点使用的旧 URL 20144 替换为 20330，保持表与配置严格一致。"""
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
    old_line = f'    "{OLD}",\n'
    if old_line in text and f'"{NEW}"' in text:
        text = text.replace(old_line, "", 1)
        _atomic_write_text_unlocked(CONST, text, encoding="utf-8")
        print("已移除旧条目 20144，保留新条目 20330")
    else:
        print("无需改动（旧行不存在或新条目缺失）")

from shawei.config.constants import TWO_TAIL_SITE_URLS  # noqa: E402
print("20144 in table:", OLD in TWO_TAIL_SITE_URLS, "| 20330 in table:", NEW in TWO_TAIL_SITE_URLS)
