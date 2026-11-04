# -*- coding: utf-8 -*-
"""把 295 期失败清单里的 7 个旧 URL 换成新 URL（身份校验前置）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.persistence.atomic_file import _atomic_write_text_unlocked, file_lock  # noqa: E402

FAIL = ROOT.parent / "七类数据统一归纳失败" / "295期-尾-失败.txt"
MAP = {
    "https://0130190827.673454.xyz/bbs/topic.php?id=20144": "https://0130190827.673454.xyz/bbs/topic.php?id=20330",
    "https://67806780827.325346.xyz/bbs/topic.php?id=19812": "https://67806780827.325346.xyz/bbs/topic.php?id=19581",
    "https://88888020827.983654.xyz/bbs/topic.php?id=20758": "https://88888020827.983654.xyz/bbs/topic.php?id=20915",
    "https://12388990827.794555.xyz/bbs/topic.php?id=21353": "https://12388990827.794555.xyz/bbs/topic.php?id=19959",
    "https://12388990827.688756.xyz/bbs/topic.php?id=18520": "https://12388990827.688756.xyz/bbs/topic.php?id=19155",
    "https://12388990827.688756.xyz/bbs/topic.php?id=19930": "https://12388990827.688756.xyz/bbs/topic.php?id=19128",
    "https://88888020827.997595.xyz/bbs/topic.php?id=18490": "https://88888020827.997595.xyz/bbs/topic.php?id=19471",
}

with file_lock(FAIL):
    text = FAIL.read_text(encoding="utf-8-sig")
    n = 0
    for old, new in MAP.items():
        if old in text:
            text = text.replace(old, new)
            n += 1
    if n:
        _atomic_write_text_unlocked(FAIL, text, encoding="utf-8-sig")
    print(f"失败清单同步 {n} 条 URL")
