"""323 夜月花朝取证：渲染页面，看该站是否已发 323 期、top 边界位置。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent
TARGET = "https://u6agr.dgj1u-jtp00-hcqvut.xyz/topic/226654.html"


def main() -> None:
    from shawei.config.rules import effective_rule_for

    rule = effective_rule_for(TARGET, "夜月花朝")
    print("规则:", rule)

    from shawei.fetch.browser import render_browser_documents

    docs = render_browser_documents(TARGET, 45)
    print("文档数:", len(docs), [len(d) for d in docs])
    for i, doc in enumerate(docs):
        (OUT / f"doc_{i}.txt").write_text(doc, encoding="utf-8")

    body = docs[0]
    (OUT / "render_body.txt").write_text(body, encoding="utf-8")
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    print("body 行数:", len(lines), "字符:", len(body))
    print("含 夜月花朝:", "夜月花朝" in body)
    periods = sorted({int(m) for m in re.findall(r"(?<!\d)(\d{3})\s*期", body)})
    print("期数范围:", periods[:5], "..", periods[-5:], "共", len(periods))
    print("含 323:", 323 in periods, "| 含 322:", 322 in periods)

    hits = [(n, ln) for n, ln in enumerate(lines) if re.search(r"(?<!\d)32[0-9]\s*期", ln)]
    print("\n--- 32x 期行（前 15 条） ---")
    for n, ln in hits[:15]:
        print(f"[{n}] {ln[:110]}")


if __name__ == "__main__":
    main()
