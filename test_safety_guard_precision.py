from __future__ import annotations

import pytest

from shawei.domain.models import Record
from shawei.parsers.safety_guards import enforce_parsed_records


def test_unrelated_multidigit_other_field_does_not_invalidate_valid_tail() -> None:
    record = Record(
        tail=5,
        period=251,
        site_name="审计站",
        source_snippet="251期绝杀一尾[5] 杀码23 开猴23准",
    )
    assert enforce_parsed_records(
        [record],
        source="dedicated",
        parser_name="legacy_single_tail",
        document=record.source_snippet,
        site_name="审计站",
    ) == [record]


def test_row_period_after_label_is_not_a_multidigit_tail() -> None:
    record = Record(
        tail=7,
        period=255,
        site_name="审计站",
        source_snippet="大江东 大江东◆每期精杀一尾 255期 杀 : [7尾]开 ?? 准",
    )
    assert enforce_parsed_records(
        [record],
        source="dedicated",
        parser_name="ttss_list_article_top_tail",
        document=record.source_snippet,
        site_name="审计站",
    ) == [record]


def test_repeated_same_digit_presentation_is_one_exact_tail() -> None:
    cases = (
        ("255期 绝杀一尾(777)开?2?", 7),
        ("255期 杀一尾[666尾]开:0000准", 6),
        ("092期 [绝杀一尾] [555尾]开:29", 5),
        ("255期 杀掉一尾〖222尾〗开:0000准", 2),
    )
    for text, tail in cases:
        record = Record(
            tail=tail, period=255, site_name="审计站", source_snippet=text
        )
        assert enforce_parsed_records(
            [record],
            source="dedicated",
            parser_name="topic_published_body_tail",
            document=text,
            site_name="审计站",
        ) == [record]


def test_decorative_symbols_are_not_other_fields() -> None:
    dedicated = Record(
        tail=7,
        period=255,
        site_name="审计站",
        source_snippet="东方黑看 255期✠精杀一尾✠(7尾)开0000准",
    )
    assert enforce_parsed_records(
        [dedicated],
        source="dedicated",
        parser_name="dongfang_current_tail",
        document=dedicated.source_snippet,
        site_name="审计站",
    ) == [dedicated]

    compact = Record(
        tail=2,
        period=255,
        site_name="审计站",
        source_snippet="255期 『通彩精英』👈 绝杀一尾👈[2]开: 08 错",
    )
    assert enforce_parsed_records(
        [compact],
        source="compact",
        parser_name="",
        document=compact.source_snippet,
        site_name="审计站",
    ) == [compact]


def test_bracket_kill_value_notation_is_a_direct_value() -> None:
    record = Record(
        tail=1,
        period=200,
        site_name="审计站",
        source_snippet="造车合辙 主体255期 200期绝杀一尾[杀1尾]特开:47错",
    )
    assert enforce_parsed_records(
        [record],
        source="dedicated",
        parser_name="topic_published_body_tail",
        document=record.source_snippet,
        site_name="审计站",
    ) == [record]


def test_four_repeated_digits_are_still_one_tail_value() -> None:
    record = Record(
        tail=4,
        period=255,
        site_name="审计站",
        source_snippet="255期绝杀一尾[4444]开:0000准",
    )
    assert enforce_parsed_records(
        [record],
        source="section",
        parser_name="",
        document=record.source_snippet,
        site_name="审计站",
    ) == [record]


def test_verified_scope_tail_notations_are_direct_values() -> None:
    cases = (
        ("不拘小节 主帖标题255期 255期 杀肖杀尾 [狗+7 尾]开?00准", 7, "bujuxiaojie_topic_tail"),
        ("吹毛求疵 主帖标题255期 203期:[杀肖杀尾][杀龙肖杀9尾]开猴45准", 9, "chuimao_primary_topic_tail"),
        ("故里春意 主帖标题255期 162期杀肖杀尾[鸡肖.2尾]开蛇01准", 2, "gulichunyi_topic_tail"),
        ("行舒唱晚 主帖标题255期 255期:杀肖杀尾[猴＋1尾] 开0000准", 1, "xingshuchangwan_topic_tail"),
        ("风驰电掣 主帖标题255期 012期[绝杀一尾]一[5尾]开:羊11对", 5, "fengchi_topic_main_tail"),
        ("鳌愤龙愁 主体255期 108期:杀一尾[ 4 44 尾 ]开:狗45准", 4, "topic_published_body_tail"),
        ("鳌愤龙愁 主体255期 190期:杀一尾[ 4 4 4 尾 ]开:兔16准", 4, "topic_published_body_tail"),
    )
    for text, tail, parser in cases:
        record = Record(
            tail=tail, period=255, site_name="审计站", source_snippet=text
        )
        assert enforce_parsed_records(
            [record],
            source="dedicated",
            parser_name=parser,
            document=text,
            site_name="审计站",
        ) == [record]


def test_period_strip_does_not_hide_mixed_multidigit_tail() -> None:
    record = Record(
        tail=3,
        period=255,
        site_name="审计站",
        source_snippet="255期绝杀一尾 杀[23]尾 开猴23准",
    )
    with pytest.raises(LookupError, match="多位值"):
        enforce_parsed_records(
            [record],
            source="dedicated",
            parser_name="legacy_single_tail",
            document=record.source_snippet,
            site_name="审计站",
        )
