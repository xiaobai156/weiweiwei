"""330 临川观月：渲染取证，看页面到底有没有 330 行。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent
URL = "https://fbgbfg.www27521c.com:8443/gsb/am04.html"


def main() -> None:
    from shawei.fetch.browser import render_browser_documents

    docs = render_browser_documents(URL, 45)
    print(f"文档 {len(docs)} 份: {[len(d) for d in docs]}")
    for i, doc in enumerate(docs):
        (OUT / f"render_{i}.txt").write_text(doc, encoding="utf-8")

    body = docs[0] if docs else ""
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    print(f"body 行数 {len(lines)}")
    print("前 20 行:")
    for i, line in enumerate(lines[:20]):
        print(f"  {i} {line[:120]}")
    print(f"\n含 330 的行 {sum('330' in l for l in lines)} 条:")
    for line in [l for l in lines if "330" in l][:10]:
        print("  ", line[:170])
    rows = [line for line in lines if re.search(r"\d{3}\s*期", line)]
    print(f"\n含期数行 {len(rows)} 条，最后 8 条:")
    for line in rows[-8:]:
        print("  ", line[:170])
    print(f"\n含期数行 前 5 条:")
    for line in rows[:5]:
        print("  ", line[:170])


if __name__ == "__main__":
    main()
