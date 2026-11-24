"""324 三站渲染取证：拿页面的真实可见文本，看有没有 324 期行。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent

TARGETS = {
    "逞心如意": "https://jkofyya.6sf58-wbz5a-thviwx.work:29477/article/admin/6a13f137c1d9e28d71e57742?url=jbp",
    "转嗔为喜": "https://djimkyw.n7ht1-wp4vm-ljitjr.xyz:29488/article/manager/6a329f1573fa32d0b73c0ca0?url=cmzj",
    "寻宝探码": "https://12388990827.688756.xyz/bbs/topic.php?id=19155",
}


def summarize(name: str, docs: list[str]) -> None:
    print(f"\n=== {name} ({len(docs)} 文档) ===")
    for i, doc in enumerate(docs):
        path = OUT / f"render_{name}_{i}.txt"
        path.write_text(doc, encoding="utf-8", errors="replace")
        plain = re.sub(r"<script.*?</script>|<style.*?</style>", " ", doc, flags=re.S)
        plain = re.sub(r"<[^>]+>", " ", plain)
        periods = sorted({int(m) for m in re.findall(r"(?<!\d)(\d{3})\s*期", plain)})
        lines = [line.strip() for line in plain.splitlines() if line.strip()]
        rows = [line for line in lines if re.search(r"(?<!\d)32[0-9]\s*期", line)]
        print(f"  doc{i}: {len(doc)} 字符 | {name in plain} | 期数 {periods[:4]}..{periods[-4:] if periods else []}")
        for row in rows[:8]:
            print("    ", row[:180])


def main() -> None:
    from shawei.fetch.browser import render_browser_documents

    for name, url in TARGETS.items():
        try:
            docs = render_browser_documents(url, 45)
            summarize(name, docs)
        except Exception as exc:
            print(f"\n=== {name} ===\n  渲染异常: {type(exc).__name__}: {str(exc)[:200]}")


if __name__ == "__main__":
    main()
