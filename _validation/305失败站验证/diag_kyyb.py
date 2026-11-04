"""诊断：可见一斑 305 期为何被判为 bottom 边界 304（只读）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2")
sys.path.insert(0, str(ROOT))

from shawei.config.rules import effective_rule_for  # noqa: E402
from shawei.fetch.http_client import FETCH_STATUS, RENDER_STATUS  # noqa: E402
from shawei.services.crawl_site import collect_site_records  # noqa: E402

URL = "https://gboqrz.sm0a0-x9x2c-xyvjdr.work/topic/241106.html"
NAME = "可见一斑"
PICK = "bottom"
PERIOD = 305

rule = effective_rule_for(URL)
print("rule:", rule)
print("chunk_keywords:", rule.chunk_keywords)
print("table_headers:", rule.table_headers)
print("direction window:", rule.direction_window if hasattr(rule, "direction_window") else "n/a")

try:
    records = collect_site_records(URL, NAME, pick=PICK, timeout=20, target_period=PERIOD)
except Exception as exc:  # noqa: BLE001
    print("collect 失败:", type(exc).__name__, exc)
    records = []

print("records:", len(records))
for r in records[-8:]:
    print(" ", r)
print("FETCH_STATUS:", {k: v for k, v in FETCH_STATUS.items() if URL.split("/")[2] in k})
print("RENDER_STATUS:", RENDER_STATUS)
