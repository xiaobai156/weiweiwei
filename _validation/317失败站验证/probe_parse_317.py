# -*- coding: utf-8 -*-
"""317：三站解析链路定位（只读，不动配置）。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shawei.config.rules import effective_rule_for  # noqa: E402
from shawei.parsers.common import extract_absolute_kill_section_records  # noqa: E402
from shawei.parsers.dedicated import DEDICATED_PARSER_HANDLERS, DedicatedContext  # noqa: E402

OUT = Path(__file__).parent
SITES = [
    ("刘半仙", "https://smnwgqcm.vkk2k-rpbnk-qtocig.xyz:16677/"),
    ("飞龙在天", "https://anhomo.n03wh-m2skn-wssphn.xyz/"),
    ("跑马图", "https://sxapnxtw.w9lkt-9vch6-idlact.work:17477/"),
]


def strip_non_content(html: str) -> str:
    """去掉 style/script/注释，避免 CSS 文本占用解析窗口。"""
    html = re.sub(r"<style\b.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<script\b.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    return html


def main() -> None:
    for name, host in SITES:
        rule = effective_rule_for(host, name)
        html = (OUT / f"render_317_{name}.html").read_text(encoding="utf-8")
        body = (OUT / f"render_317_{name}.txt").read_text(encoding="utf-8")
        print(f"=== {name} sources={rule.allowed_sources} parser={rule.dedicated_parser!r} "
              f"body_first={rule.prefer_rendered_body_text}", flush=True)
        print(f"    html={len(html)} body={len(body)} "
              f"style_blocks={len(re.findall(r'<style', html, re.I))}", flush=True)
        clean = strip_non_content(html)
        for tag, doc in (("body", body), ("html", html), ("html-无style", clean)):
            if rule.dedicated_parser:
                handler = DEDICATED_PARSER_HANDLERS[rule.dedicated_parser]
                ctx = DedicatedContext(
                    pick="bottom",
                    target_period=317,
                    chunk_keywords=rule.chunk_keywords,
                    exclude_keywords=rule.exclude_keywords,
                    max_chunk_span=rule.max_chunk_span,
                    require_draw_signal=rule.require_draw_signal,
                    require_site_keyword=rule.require_site_keyword,
                )
                try:
                    recs = handler(doc, name, rule.dedicated_parser, ctx)
                except Exception as exc:  # noqa: BLE001
                    print(f"   [{tag}] 专属解析异常 {type(exc).__name__}: {exc}", flush=True)
                    continue
            else:
                recs = extract_absolute_kill_section_records(
                    doc,
                    name,
                    section_keywords=rule.section_keywords,
                    section_stop_keywords=rule.section_stop_keywords,
                    chunk_keywords=rule.chunk_keywords,
                    exclude_keywords=rule.exclude_keywords,
                    max_section_span=rule.max_section_span,
                    max_chunk_span=rule.max_chunk_span,
                    require_draw_signal=rule.require_draw_signal,
                    require_site_keyword=rule.require_site_keyword,
                )
            pairs = [(r.period, r.tail) for r in recs[:6]]
            print(f"   [{tag}] records={len(recs)} {pairs}", flush=True)


if __name__ == "__main__":
    main()
