# -*- coding: utf-8 -*-
"""315 期张天师解析取证：用已保存的渲染正文复现解析与守卫判定。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shawei.config.rules import effective_rule_for  # noqa: E402
from shawei.parsers import safety_guards  # noqa: E402
from shawei.parsers.topic import extract_discuz_main_post_records  # noqa: E402

URL = "https://wwlhc.com/thread-87037-1-1.html"
NAME = "张天师"
PERIOD = 315
HERE = Path(__file__).parent


def main() -> None:
    text = (HERE / "render_zts_315.html").read_text(encoding="utf-8")
    rule = effective_rule_for(URL, NAME)
    print("chunk_keywords:", rule.chunk_keywords)
    print("exclude_keywords:", rule.exclude_keywords)
    print("require_draw_signal:", rule.require_draw_signal)
    records = extract_discuz_main_post_records(
        text,
        NAME,
        rule.chunk_keywords,
        rule.exclude_keywords,
        rule.require_draw_signal,
        PERIOD,
        site_url=URL,
    )
    print("记录数:", len(records))
    for rec in records:
        print(f"  period={rec.period} tail={rec.tail} values={getattr(rec, 'tail_values', None)} "
              f"text={getattr(rec, 'value_text', None)!r} snippet={rec.source_snippet[:90]!r}")
    try:
        kept = safety_guards.enforce_parsed_records(
            records,
            source="dedicated",
            parser_name="discuz_main_post_kill_tail",
            document=text,
            site_name=NAME,
        )
        print("守卫通过:", [(r.period, r.tail) for r in kept])
    except Exception as exc:  # noqa: BLE001
        print(f"守卫拒绝 {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
