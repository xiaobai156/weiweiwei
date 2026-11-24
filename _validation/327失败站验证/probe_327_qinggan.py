"""327 清肝明目取证：渲染页面看本站有没有 327 行。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent
URL = "https://4.48kk49.com:1888/Article/ar_content/id/1543/tid/82.html"
NAME = "清肝明目"


def main() -> None:
    from shawei.fetch.browser import render_browser_documents

    docs, error = render_browser_documents(URL, 45)
    print(f"渲染文档 {len(docs)} 份, error={error!r}")
    for i, doc in enumerate(docs):
        (OUT / f"render_{NAME}_{i}.txt").write_text(doc, encoding="utf-8")
        print(f"  doc{i} 长度 {len(doc)} | 含327 {doc.count('327')} | 含本站名 {doc.count(NAME)}")

    body = docs[0] if docs else ""
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    print(f"\nbody 行数 {len(lines)}, 前 40 行:")
    for i, line in enumerate(lines[:40]):
        print(f"  {i} {line[:120]}")
    hit = [line for line in lines if "327" in line]
    print("\n含 327 的行:")
    for line in hit:
        print("  ", line[:160])


if __name__ == "__main__":
    main()
