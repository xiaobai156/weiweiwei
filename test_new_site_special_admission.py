import pytest

from shawei.config.constants import TWO_TAIL_SITE_URLS
from shawei.config.rules import effective_rule_for
from shawei.domain.models import StrictRule
from shawei.parsers.dedicated import extract_dedicated_records
from shawei.persistence.cache_repository import is_valid_result_value
from shawei.validation.validator import validate_documents


NEW_SITES = {
    "如履薄冰": "https://sxapnxtw.w9lkt-9vch6-idlact.work:17477/topic/470055.html",
    "跑马图": "https://sxapnxtw.w9lkt-9vch6-idlact.work:17477/",
    "穷老尽气": "https://sxapnxtw.w9lkt-9vch6-idlact.work:17477/topic/220698.html",
    "赏心悦目": "https://ykeejph.z9koz-18xjn-pvglgy.xyz:16677/topic/677675.html",
    "枝外生枝": "https://ykeejph.z9koz-18xjn-pvglgy.xyz:16677/topic/682114.html",
    "夏雨雨人": "https://ykeejph.z9koz-18xjn-pvglgy.xyz:16677/topic/682113.html",
    "数据诗篇": "https://ykeejph.z9koz-18xjn-pvglgy.xyz:16677/topic/682100.html",
}


def _parse(
    text: str,
    site_name: str,
    parser_name: str,
    keyword: str,
    pick: str,
) -> list:
    return extract_dedicated_records(
        text,
        site_name,
        parser_name,
        chunk_keywords=(keyword,),
        target_period=223,
        pick=pick,
        require_site_keyword=True,
    )


def test_all_seven_urls_have_explicit_rules() -> None:
    for site_name, url in NEW_SITES.items():
        rule = effective_rule_for(url, site_name)
        assert rule.allowed_sources == ("dedicated",)
        if site_name == "枝外生枝":
            assert rule.prefer_rendered_body_text is False
        else:
            assert rule.prefer_rendered_body_text is True


def test_new_two_tail_contract_is_bound_to_names_and_urls() -> None:
    expected_names = {"如履薄冰", "跑马图", "赏心悦目", "夏雨雨人", "数据诗篇"}
    expected_urls = {
        NEW_SITES[site_name]
        for site_name in expected_names
    }
    assert expected_urls <= TWO_TAIL_SITE_URLS
    assert is_valid_result_value("6、8", NEW_SITES["如履薄冰"])
    assert is_valid_result_value("3、2", NEW_SITES["跑马图"])


def test_topic_two_tail_parser_accepts_decimal_and_adjacent_formats() -> None:
    text = (
        "224期:如履薄冰[杀特两尾]站长推荐 作者:如履薄冰 "
        "224期:[杀特两尾][5.0尾]开:0000准 "
        "223期:[杀特两尾][6.8尾]开:猴23准 "
        "222期:[杀特两尾][4.9尾]开:蛇26准"
    )
    records = _parse(text, "如履薄冰", "topic_body_two_tail", "杀特两尾", "top")
    assert [(record.period, record.tail_values) for record in records] == [
        (224, (5, 0)),
        (223, (6, 8)),
        (222, (4, 9)),
    ]
    assert records[0].validation_error == "开0000占位记录"

    adjacent = (
        "绝杀贴224期[绝杀二尾]已更新 赏心悦目发表于 "
        "223期[绝杀二尾][98]开000准 222期[绝杀二尾][07]开蛇26准"
    )
    adjacent_records = _parse(
        adjacent, "赏心悦目", "topic_body_two_tail", "绝杀二尾", "top"
    )
    assert [record.value() for record in adjacent_records] == ["9、8", "0、7"]

    no_suffix = (
        "绝杀贴224期[绝杀二尾]已更新 数据诗篇发表于 "
        "223期:[绝杀二尾][1.9]开:0000准 222期:[绝杀二尾][7.0]开:蛇26准"
    )
    no_suffix_records = _parse(
        no_suffix, "数据诗篇", "topic_body_two_tail", "绝杀二尾", "top"
    )
    assert [record.value() for record in no_suffix_records] == ["1、9", "7、0"]


def test_topic_single_tail_parser_handles_question_mark_placeholder_and_scope() -> None:
    text = (
        "民间帖223期:牛逼猛料[精准杀尾] 作者:穷老尽气 "
        "203期:精准杀尾[4]开马25准 222期:精准杀尾[7]开蛇26准 "
        "223期:精准杀尾[8]开?00准"
    )
    records = _parse(text, "穷老尽气", "topic_body_single_tail", "精准杀尾", "bottom")
    assert [(record.period, record.value()) for record in records] == [
        (203, "4"),
        (222, "7"),
        (223, "8"),
    ]
    assert records[-1].validation_error == "开0000占位记录"

    second = (
        "绝杀贴224期[杀肖杀尾]已更新 枝外生枝发表于 "
        "222期[杀肖杀尾]杀肖[龙]杀尾[2]开蛇26对 "
        "223期[杀肖杀尾]杀肖[龙]杀尾[8]开0000对"
    )
    second_records = _parse(
        second, "枝外生枝", "topic_body_single_tail", "杀肖杀尾", "bottom"
    )
    assert [record.value() for record in second_records] == ["2", "8"]


def test_root_two_tail_parser_is_scoped_to_the_named_block() -> None:
    text = (
        "澳门跑马图[三期五肖]223期[兔龙牛鸡猴]开猴23准 "
        "澳门跑马图[绝杀二尾]199期绝杀二尾[4尾5尾]开羊36准 "
        "222期绝杀二尾[4尾6尾]开蛇26错 "
        "223期绝杀二尾[3尾2尾]开0000准 "
        "澳门跑马图[正版六肖九码]223期平特一尾:888"
    )
    records = _parse(
        text, "跑马图", "root_two_tail_block", "澳门跑马图[绝杀二尾]", "bottom"
    )
    assert [(record.period, record.value()) for record in records] == [
        (199, "4、5"),
        (222, "4、6"),
        (223, "3、2"),
    ]

    rule = StrictRule(
        allowed_sources=("dedicated",),
        dedicated_parser="root_two_tail_block",
        chunk_keywords=("澳门跑马图[绝杀二尾]",),
        prefer_rendered=True,
        prefer_rendered_body_text=True,
        require_site_keyword=True,
        site_url=NEW_SITES["跑马图"],
    )
    decision = validate_documents(
        [text], "跑马图", pick="bottom", rule=rule, target_period=223
    )
    assert [record.value() for record in decision.records] == ["3、2"]


def test_top_boundary_still_rejects_a_newer_published_row() -> None:
    text = (
        "224期:如履薄冰[杀特两尾]站长推荐 作者:如履薄冰 "
        "224期:[杀特两尾][5.0尾]开:0000准 "
        "223期:[杀特两尾][6.8尾]开:猴23准"
    )
    rule = StrictRule(
        allowed_sources=("dedicated",),
        dedicated_parser="topic_body_two_tail",
        chunk_keywords=("杀特两尾",),
        prefer_rendered=True,
        prefer_rendered_body_text=True,
        require_site_keyword=True,
        site_url=NEW_SITES["如履薄冰"],
    )
    with pytest.raises(LookupError, match="绝对top边界是224期"):
        validate_documents(
            [text], "如履薄冰", pick="top", rule=rule, target_period=223
        )
