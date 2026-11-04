# -*- coding: utf-8 -*-
"""封存六玄网：sites.json 该条加 archived:true（字节级最小改动，保留原有 \\r\\r\\n 行尾）。

以字节定位目标片段，不经过文本换行归一化，避免破坏文件其余部分。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.persistence.atomic_file import file_lock  # noqa: E402

SITES = ROOT / "sites.json"

OLD = (
    b'    "name": "\xe5\x85\xad\xe7\x8e\x84\xe7\xbd\x91",\r\r\n'
    b'    "url": "https://lx11.www87127b.com:8443/#87127",\r\r\n'
    b'    "pick": "top"\r\r\n'
    b'  },'
)
NEW = (
    b'    "name": "\xe5\x85\xad\xe7\x8e\x84\xe7\xbd\x91",\r\r\n'
    b'    "url": "https://lx11.www87127b.com:8443/#87127",\r\r\n'
    b'    "pick": "top",\r\r\n'
    b'    "archived": true\r\r\n'
    b'  },'
)

with file_lock(SITES):
    raw = SITES.read_bytes()
    hits = raw.count(OLD)
    print("字节匹配次数", hits)
    if hits != 1:
        raise SystemExit("中止：匹配次数不为 1")
    updated = raw.replace(OLD, NEW, 1)
    tmp = SITES.with_name(SITES.name + ".tmp")
    tmp.write_bytes(updated)
    tmp.replace(SITES)
print("sites.json 已封存六玄网，字节数", len(raw), "->", len(updated))
