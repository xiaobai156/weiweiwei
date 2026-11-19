"""323 夜月花朝：修复后直接走解析器，确认 323 期取值。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent
TARGET = "https://u6agr.dgj1u-jtp00-hcqvut.xyz/topic/226654.html"


def main() -> None:
    from shawei.config.rules import effective_rule_for
    from shawei.validation.validator import validate_documents

    rule = effective_rule_for(TARGET, "夜月花朝")
    docs = [
        (OUT / "doc_0.txt").read_text(encoding="utf-8"),
        (OUT / "doc_1.txt").read_text(encoding="utf-8"),
    ]
    for period in (323, 322, 324):
        decision = validate_documents(docs, "夜月花朝", None, "top", rule, period)
        recs = [r for r in decision.records if r.period == period]
        print(f"期数 {period}: 候选 {len(decision.candidates)} 记录数 {len(decision.records)}")
        for r in recs[:2]:
            print("   命中:", r.period, r.tail, r.draw_text, "|", r.source_snippet[:80])
        if not recs:
            print("   前 3 条记录:", [(r.period, r.tail) for r in decision.records[:3]])


if __name__ == "__main__":
    main()
