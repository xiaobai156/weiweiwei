# -*- coding: utf-8 -*-
"""解封后补回 10 个站的 294 期失败记录（缓存 failure_reasons 已保留，直接取用）。

写入走项目自带 write_optional_fail_file。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.persistence import txt_writer  # noqa: E402

CACHE = ROOT / "recent_10_cache.json"
FAIL = ROOT.parent / "七类数据统一归纳失败" / "294期-尾-失败.txt"
PERIOD = 294
NAMES = [
    "坚持战斗", "无量寿佛", "再度归来", "童颜鹤发", "一心为民",
    "怪咖小生", "澳彩碼王", "寻宝探码", "财源滚滚", "海角天涯",
]

payload = json.loads(CACHE.read_text(encoding="utf-8-sig"))
lines: list[str] = []
for item in payload.get("sites", []):
    if item.get("name") not in NAMES:
        continue
    reason = (item.get("failure_reasons") or {}).get(str(PERIOD))
    if reason:
        lines.append(str(reason))
    else:
        print(f"  警告 {item['name']} 缓存没有 {PERIOD} 失败原因")

print("将写回", len(lines), "条")
txt_writer.write_optional_fail_file(FAIL, lines)
print("失败文件存在:", FAIL.exists())
if FAIL.exists():
    print("行数", len([l for l in FAIL.read_text(encoding="utf-8-sig").splitlines() if l.strip()]))
