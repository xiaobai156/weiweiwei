"""324 解析取证：用已保存的渲染文本走正式校验器，看候选与边界。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent

CASES = [
    ("逞心如意", "bottom", "https://jkofyya.6sf58-wbz5a-thviwx.work:29477/article/admin/6a13f137c1d9e28d71e57742?url=jbp"),
    ("转嗔为喜", "bottom", "https://djimkyw.n7ht1-wp4vm-ljitjr.xyz:29488/article/manager/6a329f1573fa32d0b73c0ca0?url=cmzj"),
]


def main() -> None:
    from shawei.config.rules import effective_rule_for
    from shawei.validation.validator import validate_documents

    for name, pick, url in CASES:
        docs = [
            (OUT / f"render_{name}_{i}.txt").read_text(encoding="utf-8", errors="replace")
            for i in (0, 1)
            if (OUT / f"render_{name}_{i}.txt").exists()
        ]
        rule = effective_rule_for(url, name)
        print(f"\n=== {name} ({pick}) 文档 {len(docs)} 份 ===")
        for period in (324, 323):
            try:
                decision = validate_documents(docs, name, None, pick, rule, period)
                print(f"  {period}期 -> 记录 {decision.records[:3]} | 候选 {len(decision.candidates)}")
            except Exception as exc:
                print(f"  {period}期 -> {type(exc).__name__}: {str(exc)[:160]}")


if __name__ == "__main__":
    main()
