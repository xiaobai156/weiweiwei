"""328 两站渲染取证（修正：render_browser_documents 返回文档列表，不是元组）。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent
CASES = {
    "百万惊喜": "https://mbsqhpk.8ivvt-u3cx5-enwlld.xyz:29400/article/manager/6a33d147dfa16552b923d081?url=lhzj",
    "澳彩碼王": "https://12388990827.794555.xyz/bbs/topic.php?id=19959",
}


def main() -> None:
    from shawei.fetch.browser import render_browser_documents

    for name, url in CASES.items():
        print(f"\n=== {name} ===")
        try:
            docs = render_browser_documents(url, 45)
        except Exception as exc:  # noqa: BLE001
            print(f"  渲染失败: {type(exc).__name__}: {str(exc)[:220]}")
            continue
        print(f"  文档 {len(docs)} 份: {[len(d) for d in docs]}")
        for i, doc in enumerate(docs):
            (OUT / f"render_{name}_{i}.txt").write_text(doc, encoding="utf-8")
        body = docs[0] if docs else ""
        html = docs[1] if len(docs) > 1 else ""
        print(f"  body 含328 {body.count('328')} | 含本站名 {body.count(name)}")
        print(f"  html 含328 {html.count('328')} | 含本站名 {html.count(name)}")
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        print(f"  body 行数 {len(lines)}, 前 20 行:")
        for i, line in enumerate(lines[:20]):
            print(f"    {i} {line[:110]}")
        rows = [line for line in lines if re.search(r"\d{3}\s*期", line)]
        print(f"  含期数行 {len(rows)} 条, 最后 6 条:")
        for line in rows[-6:]:
            print("    ", line[:150])
        hits = [line for line in lines if "328" in line]
        print(f"  含 328 的行 {len(hits)} 条:")
        for line in hits[:8]:
            print("    ", line[:150])


if __name__ == "__main__":
    main()
