# -*- coding: utf-8 -*-
"""317：修复后复跑真实渲染入口 + 各站配置解析。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shawei.config.rules import effective_rule_for  # noqa: E402
from shawei.fetch.browser import render_browser_documents  # noqa: E402
from shawei.validation.validator import validate_documents  # noqa: E402

TARGETS = [
    ("刘半仙", "https://smnwgqcm.vkk2k-rpbnk-qtocig.xyz:16677/", 317, "top"),
    ("飞龙在天", "https://anhomo.n03wh-m2skn-wssphn.xyz/", 317, "top"),
    ("跑马图", "https://sxapnxtw.w9lkt-9vch6-idlact.work:17477/", 317, "bottom"),
]


def main() -> None:
    for name, url, period, pick in TARGETS:
        docs = render_browser_documents(url, 30)
        print(f"=== {name} 文档数={len(docs)} 长度={[len(d) for d in docs]}", flush=True)
        rule = effective_rule_for(url, name)
        try:
            decision = validate_documents(
                docs, name, None, pick, rule, period
            )
        except Exception as exc:  # noqa: BLE001
            print(f"   校验异常 {type(exc).__name__}: {exc}", flush=True)
            continue
        print(
            f"   选定={[(r.period, r.tail) for r in decision.records[:3]]} "
            f"候选={len(decision.candidates)}",
            flush=True,
        )


if __name__ == "__main__":
    main()
