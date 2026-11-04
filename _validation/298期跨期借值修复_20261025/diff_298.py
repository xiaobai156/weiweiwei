# -*- coding: utf-8 -*-
"""对比修复前后 298 期成功 TXT 的逐站差异。"""
from __future__ import annotations

import re
from pathlib import Path

BASE = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集")
NEW = BASE / "七类数据统一归纳" / "298期-尾.txt"
OLD = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\_validation\298期跨期借值修复_20261025\before_298期-尾.txt")

RANK = re.compile(r"^\d尾\s+\d+\s+\d+$")


def parse(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or RANK.match(line) or not re.match(r"^\d尾", line):
            continue
        # 站点行：可能双尾 "4尾 5尾 站名"
        m = re.match(r"^((?:\d尾\s+)+)\s*(.+)$", line)
        if not m:
            continue
        rows[m.group(2).strip()] = m.group(1).strip()
    return rows


old = parse(OLD)
new = parse(NEW)
print("旧文件站点数", len(old))
print("新文件站点数", len(new))

only_old = sorted(set(old) - set(new))
only_new = sorted(set(new) - set(old))
diff = sorted(n for n in set(old) & set(new) if old[n] != new[n])

print(f"\n仅旧文件有 ({len(only_old)}):", only_old)
print(f"仅新文件有 ({len(only_new)}):", only_new)
print(f"\n值不同的站 ({len(diff)}):")
for n in diff:
    print(f"  {n}: 旧={old[n]}  新={new[n]}")

print("\n结论:", "完全一致，0 条差异" if not (only_old or only_new or diff) else "存在差异")
