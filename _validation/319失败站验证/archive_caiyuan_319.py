# -*- coding: utf-8 -*-
"""封存 财源滚滚：只在条目末尾追加 archived 字段，保持原排版与换行不变。"""
from __future__ import annotations

import json
from pathlib import Path

PATH = Path("sites.json")
NAME = "财源滚滚"


def detect_nl(raw: str) -> str:
    for candidate in ("\r\r\n", "\r\n", "\n"):
        if raw.count(candidate) * len(candidate) > len(raw) * 0.3:
            return candidate
    return "\n"


def main() -> None:
    with PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        raw = handle.read()
    needle = f'"name": "{NAME}"'
    start = raw.index(needle)
    obj_start = raw.rindex("{", 0, start)
    obj_end = raw.index("}", start) + 1
    block = raw[obj_start:obj_end]
    if '"archived"' in block:
        print(f"{NAME} 已封存，无需重复操作")
        return
    nl = detect_nl(raw)
    pick_idx = block.rindex('"pick"')
    line_end = block.index(nl, pick_idx)
    pick_line = block[pick_idx:line_end].rstrip()
    if not pick_line.endswith(","):
        pick_line += ","
    new_block = (
        block[:pick_idx] + pick_line + nl * 4 + '    "archived": true' + nl + "  }"
    )
    with PATH.open("w", encoding="utf-8", newline="") as handle:
        handle.write(raw[:obj_start] + new_block + raw[obj_end:])
    print(f"{NAME} 封存：{len(block)} -> {len(new_block)} 字节")
    data = json.loads(PATH.read_text(encoding="utf-8-sig"))
    entry = next(item for item in data if item["name"] == NAME)
    print("写入后条目:", entry)
    archived = [item["name"] for item in data if item.get("archived")]
    print(f"总条目 {len(data)}，封存 {len(archived)}，活动 {len(data) - len(archived)}")


if __name__ == "__main__":
    main()
