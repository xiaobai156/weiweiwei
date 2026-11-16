# -*- coding: utf-8 -*-
"""317：强制可见后取 body 文本，落盘并按配置解析，确认三站数据是否真实可读。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from playwright.sync_api import sync_playwright  # noqa: E402

from shawei.config.rules import effective_rule_for  # noqa: E402
from shawei.fetch.browser import browser_profile_dir  # noqa: E402
from shawei.parsers.common import extract_absolute_kill_section_records  # noqa: E402
from shawei.parsers.dedicated import DEDICATED_PARSER_HANDLERS, DedicatedContext  # noqa: E402

OUT = Path(__file__).parent
TARGETS = [
    ("刘半仙", "https://smnwgqcm.vkk2k-rpbnk-qtocig.xyz:16677/", "top"),
    ("飞龙在天", "https://anhomo.n03wh-m2skn-wssphn.xyz/", "top"),
    ("跑马图", "https://sxapnxtw.w9lkt-9vch6-idlact.work:17477/", "bottom"),
]


def main() -> None:
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(browser_profile_dir()),
            headless=True,
            viewport={"width": 1280, "height": 900},
            ignore_https_errors=True,
            locale="zh-CN",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for name, url, pick in TARGETS:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            page.add_style_tag(content="*{content-visibility:visible!important}")
            page.wait_for_timeout(600)
            text = page.locator("body").inner_text()
            html = page.content()
            (OUT / f"forced_{name}.txt").write_text(text, encoding="utf-8")
            (OUT / f"forced_{name}.html").write_text(html, encoding="utf-8")
            rule = effective_rule_for(url, name)
            if rule.dedicated_parser:
                handler = DEDICATED_PARSER_HANDLERS[rule.dedicated_parser]
                ctx_ = DedicatedContext(
                    pick=pick,
                    target_period=317,
                    chunk_keywords=rule.chunk_keywords,
                    exclude_keywords=rule.exclude_keywords,
                    max_chunk_span=rule.max_chunk_span,
                    require_draw_signal=rule.require_draw_signal,
                    require_site_keyword=rule.require_site_keyword,
                )
                recs = handler(html, name, rule.dedicated_parser, ctx_)
            else:
                recs = extract_absolute_kill_section_records(
                    html,
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
            print(f"=== {name} pick={pick} text={len(text)} html={len(html)} records={len(recs)}", flush=True)
            for r in recs[:6]:
                print(f"    {r.period} 尾{r.tail} 值{r.tail_values} err={r.validation_error!r} "
                      f"snippet={r.source_snippet[:60]}", flush=True)
        ctx.close()


if __name__ == "__main__":
    main()
