# -*- coding: utf-8 -*-
"""对比影子副本与正式版 298 期结果。"""
from __future__ import annotations

import re
from pathlib import Path

BASE = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集")
FORMAL = BASE / "七类数据统一归纳" / "298期-尾.txt"
SHADOW = BASE / "杀尾-修复版2" / "_shadow" / "七类数据统一归纳" / "298期-尾.txt"
FORMAL_FAIL = BASE / "七类数据统一归纳失败" / "298期-尾-失败.txt"
SHADOW_FAIL = BASE / "杀尾-修复版2" / "_shadow" / "七类数据统一归纳失败" / "298期-尾-失败.txt"

RANK = re.compile(r"^\d尾\s+\d+\s+\d+$")


def parse(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or RANK.match(line) or not re.match(r"^\d尾", line):
            continue
        m = re.match(r"^((?:\d尾\s+)+)\s*(.+)$", line)
        if m:
            rows[m.group(2).strip()] = m.group(1).strip()
    return rows


def fail_names(path: Path) -> list[str]:
    if not path.exists():
        return []
    out = []
    for block in re.split(r"(?:\r?\n){2,}", path.read_text(encoding="utf-8-sig").strip()):
        head = block.strip().splitlines()[0] if block.strip() else ""
        parts = head.split(" ")
        if len(parts) > 1:
            out.append(parts[1])
    return out


formal, shadow = parse(FORMAL), parse(SHADOW)
print("正式版站点数", len(formal), "｜影子版站点数", len(shadow))

only_formal = sorted(set(formal) - set(shadow))
only_shadow = sorted(set(shadow) - set(formal))
diff = sorted(n for n in set(formal) & set(shadow) if formal[n] != shadow[n])

print(f"\n仅正式版有 ({len(only_formal)}): {only_formal}")
print(f"仅影子版有 ({len(only_shadow)}): {only_shadow}")
print(f"\n值不同 ({len(diff)}):")
for n in diff:
    print(f"  {n}: 正式={formal[n]}  影子={shadow[n]}")

print("\n正式版失败:", fail_names(FORMAL_FAIL))
print("影子版失败:", fail_names(SHADOW_FAIL))
