# -*- coding: utf-8 -*-
"""把 292 期失败清单里 6 个换址站的 URL 换成新 URL（只改 URL，其余字段原样）。

用项目自身的 file_lock + 原子替换；不新增/删除任何失败条目。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.persistence.atomic_file import _atomic_write_text_unlocked, file_lock  # noqa: E402

FAIL = ROOT.parent / "七类数据统一归纳失败" / "292期-尾-失败.txt"
NEW_ORIGIN = "https://dzdsqxrw.1mppg-x8rsf-cxwlxc.cyou:17455"

MAP = {
    "https://tulprhfc.wghcb-bnmgm-hyymaz.work:16655/topic/324698.html": f"{NEW_ORIGIN}/topic/324698.html",
    "https://jogavu.6bl6s-ilo1w-yfnvvl.work:16677/topic/678625.html": f"{NEW_ORIGIN}/topic/678625.html",
    "https://whsbrmz.qclrc-4mk42-vnxbyg.work:16677/topic/248009.html": f"{NEW_ORIGIN}/topic/248009.html",
    "https://tulprhfc.wghcb-bnmgm-hyymaz.work:16655/topic/305414.html": f"{NEW_ORIGIN}/topic/305414.html",
    "https://iboatq.pjgpm-epbf7-lxpezb.work:16677/topic/324703.html": f"{NEW_ORIGIN}/topic/324703.html",
    "https://pvxiftuf.yumkw-u4s81-hpytyz.work:16677/topic/559099.html": f"{NEW_ORIGIN}/topic/559099.html",
}


def main() -> int:
    with file_lock(FAIL):
        text = FAIL.read_text(encoding="utf-8-sig")
        original = text
        hits = 0
        for old, new in MAP.items():
            if old in text:
                text = text.replace(old, new)
                hits += 1
        if hits == 0:
            print("失败清单里没有匹配的旧URL，未写入")
            return 0
        _atomic_write_text_unlocked(FAIL, text, encoding="utf-8-sig")
    print(f"失败清单已同步 {hits} 条 URL")
    print("改动前长度", len(original), "改动后长度", len(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
