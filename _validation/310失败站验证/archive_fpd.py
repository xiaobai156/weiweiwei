# -*- coding: utf-8 -*-
"""封存 奉陪到底：只在该条目末尾追加 archived 字段，保持原文件排版与换行不变。"""
from __future__ import annotations

import json
from pathlib import Path

PATH = Path("sites.json")
NEEDLE = '"name": "奉陪到底"'


def main() -> None:
    with PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        raw = handle.read()
    nl = "\r\n" if "\r\n" in raw else "\n"
    start = raw.index(NEEDLE)
    obj_start = raw.rindex("{", 0, start)
    obj_end = raw.index("}", start) + 1
    block = raw[obj_start:obj_end]
    if '"archived"' in block:
        print("已封存，无需重复操作")
        return
    last_brace = block.rindex("}")
    head = block[:last_brace].rstrip()
    if not head.endswith(","):
        head += ","
    new_block = head + nl + nl + '    "archived": true' + nl + "  }"
    with PATH.open("w", encoding="utf-8", newline="") as handle:
        handle.write(raw[:obj_start] + new_block + raw[obj_end:])
    data = json.loads(PATH.read_text(encoding="utf-8-sig"))
    entry = next(item for item in data if item["name"] == "奉陪到底")
    print("写入后条目:", entry)


if __name__ == "__main__":
    main()
