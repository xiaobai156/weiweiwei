"""330 临川观月：用渲染文档直接过解析，确认边界与候选。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent
URL = "https://fbgbfg.www27521c.com:8443/gsb/am04.html"
NAME = "临川观月"


def main() -> None:
    from shawei.config.rules import effective_rule_for
    from shawei.fetch.browser import render_browser_documents
    from shawei.validation.validator import validate_documents

    docs = render_browser_documents(URL, 45)
    rule = effective_rule_for(URL, NAME)
    print("rule sources:", rule.allowed_sources, "| chunk_keywords:", rule.chunk_keywords)
    for period in (330, 329, 328):
        try:
            decision = validate_documents(docs, NAME, None, "bottom", rule, period)
            print(f"{period} -> records={decision.records} candidates={len(decision.candidates)}")
        except Exception as exc:  # noqa: BLE001
            print(f"{period} -> {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
