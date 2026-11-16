# -*- coding: utf-8 -*-
"""封存 无量寿佛、一心为民：只追加 archived 字段，保持文件原有排版/换行不变。"""
from __future__ import annotations

import json
from pathlib import Path

PATH = Path("sites.json")
NAMES = ("无量寿佛", "一心为民")


def detect_nl(raw: str) -> str:
    for candidate in ("\r\r\n", "\r\n", "\n"):
        if raw.count(candidate) * len(candidate) > len(raw) * 0.3:
            return candidate
    return "\n"


def archive(raw: str, name: str) -> str:
    needle = f'"name": "{name}"'
    start = raw.index(needle)
    obj_start = raw.rindex("{", 0, start)
    obj_end = raw.index("}", start) + 1
    block = raw[obj_start:obj_end]
    if '"archived"' in block:
        print(f"{name} 已封存，跳过")
        return raw
    nl = detect_nl(raw)
    pick_idx = block.rindex('"pick"')
    line_end = block.index(nl, pick_idx)
    pick_line = block[pick_idx:line_end]
    if not pick_line.rstrip().endswith(","):
        pick_line = pick_line.rstrip() + ","
    pad = nl * 4
    new_block = (
        block[:pick_idx] + pick_line + pad + '    "archived": true' + nl + "  }"
    )
    print(f"{name} 封存：原块 {len(block)} -> {len(new_block)} 字节")
    return raw[:obj_start] + new_block + raw[obj_end:]


def main() -> None:
    with PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        raw = handle.read()
    before = len(raw)
    for name in NAMES:
        raw = archive(raw, name)
    if len(raw) != before:
        with PATH.open("w", encoding="utf-8", newline="") as handle:
            handle.write(raw)
    data = json.loads(PATH.read_text(encoding="utf-8-sig"))
    for name in NAMES:
        entry = next(item for item in data if item["name"] == name)
        print("写入后条目:", entry)
    archived = [item["name"] for item in data if item.get("archived")]
    print(f"总条目 {len(data)}，封存 {len(archived)}，活动 {len(data) - len(archived)}")


if __name__ == "__main__":
    main()
