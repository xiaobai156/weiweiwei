# -*- coding: utf-8 -*-
"""删除 310 期失败 TXT 中已封存站点（奉陪到底）的记录。

只有全部清空时才由项目写入器删除文件；这里显式清空 310 期失败文件。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shawei.config.paths import FAIL_OUTPUT_DIR  # noqa: E402
from shawei.persistence import txt_writer  # noqa: E402

PERIOD = 310
NAME = "奉陪到底"


def main() -> None:
    path = FAIL_OUTPUT_DIR / f"{PERIOD}期-尾-失败.txt"
    if not path.exists():
        print("失败文件不存在:", path)
        return
    text = path.read_text(encoding="utf-8-sig")
    blocks = [b.strip() for b in text.strip().split("\n\n") if b.strip()]
    kept = [b for b in blocks if not b.startswith(f"失败 {NAME} ")]
    removed = len(blocks) - len(kept)
    txt_writer.write_optional_fail_file(path, kept)
    print(f"移除 {removed} 条，剩余 {len(kept)} 条；文件存在: {path.exists()}")


if __name__ == "__main__":
    main()
