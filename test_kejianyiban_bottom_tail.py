"""可见一斑（/topic/241106.html）专属解析的回归测试。"""
from __future__ import annotations

import pytest

from shawei.config.rules import effective_rule_for
from shawei.domain.models import Document
from shawei.parsers.dedicated import (
    DEDICATED_PARSER_HANDLERS,
    extract_dedicated_records,
)
from shawei.validation.validator import validate_documents

URL = "https://gboqrz.sm0a0-x9x2c-xyvjdr.work/topic/241106.html"
NAME = "可见一斑"
PARSER = "kejianyiban_bottom_tail"

# 当期块尾巴上的整片导航/广告，真实页面里它和当期行同属一个区块。
NAV_TAIL = """
@所有彩民:用您快人一步头脑记住40752b.com
用心服务，推荐每一位彩民
组合三肖 最稳六肖 五码必中 大小中特 ④肖⑧码 三尾中特 三码中特 爆庄二肖
★★ 博彩必备★★ 点击进入官网投注
"""

HEAD = "305期:澳门可见一斑(绝杀一尾)准准准! 作者:可见一斑"


def _page(*rows: str, nav: str = NAV_TAIL, head: str = HEAD) -> str:
    return "\n".join([head, *rows, nav])


def _rows(*rows: str) -> list[tuple[int, str]]:
    text = _page(*rows)
    records = extract_dedicated_records(
        text,
        NAME,
        PARSER,
        chunk_keywords=("可见一斑", "绝杀一尾", "绝杀1尾", "杀一尾"),
        max_chunk_span=240,
        require_draw_signal=True,
        require_site_keyword=True,
        pick="bottom",
    )
    return [(record.period, record.value()) for record in records]


def _rule():
    return effective_rule_for(URL, NAME)


def test_parser_is_registered_and_bound_to_this_url_only() -> None:
    rule = _rule()

    assert PARSER in DEDICATED_PARSER_HANDLERS
    assert rule.allowed_sources == ("dedicated",)
    assert rule.dedicated_parser == PARSER
    assert rule.site_url == URL


def test_current_period_row_survives_trailing_navigation() -> None:
    rows = _rows(
        "303期:绝杀一尾[2] 开虎17准",
        "304期:绝杀一尾[4] 开狗21准",
        "305期:绝杀一尾[6] 开0000准",
    )

    assert rows == [(303, "2"), (304, "4"), (305, "6")]


def test_pending_draw_placeholder_is_a_published_row() -> None:
    document = _page("304期:绝杀一尾[4] 开狗21准", "305期:绝杀一尾[6] 开0000准")
    records = extract_dedicated_records(
        document,
        NAME,
        PARSER,
        chunk_keywords=("可见一斑", "绝杀一尾"),
        max_chunk_span=240,
        require_site_keyword=True,
        pick="bottom",
    )

    assert records[-1].period == 305
    assert records[-1].value() == "6"
    assert records[-1].validation_error == ""
    assert records[-1].draw_text == "开0000准"
    assert records[-1].source_snippet.startswith("可见一斑 305期:绝杀一尾[6]")


def test_adjacent_periods_fail_at_the_real_boundary() -> None:
    document = _page(
        "303期:绝杀一尾[2] 开虎17准",
        "304期:绝杀一尾[4] 开狗21准",
        "305期:绝杀一尾[6] 开0000准",
    )

    for period in (303, 304, 306):
        with pytest.raises(LookupError, match="绝对bottom边界是305期"):
            validate_documents(
                [Document(URL, document, "rendered")],
                NAME,
                limit=0,
                pick="bottom",
                rule=_rule(),
                target_period=period,
            )


def test_target_period_is_read_from_its_own_row() -> None:
    document = _page(
        "304期:绝杀一尾[4] 开狗21准",
        "305期:绝杀一尾[6] 开0000准",
    )

    decision = validate_documents(
        [Document(URL, document, "rendered")],
        NAME,
        limit=0,
        pick="bottom",
        rule=_rule(),
        target_period=305,
    )

    assert [(record.period, record.value()) for record in decision.records] == [(305, "6")]


def test_other_sections_and_broken_fields_are_not_candidates() -> None:
    rows = _rows(
        "304期:平特一尾[4] 开狗21准",
        "305期:三尾中特[6] 开猴23准",
        "305期:绝杀一尾[6] 准",
        "305期:绝杀一尾[12] 开猴23准",
        "305期:绝杀一尾[6] 开猴准",
    )

    assert rows == []


def test_same_block_same_period_uses_direction_selection() -> None:
    """同一区块多行同期记录按方向取其一，是既定设计，不算冲突。"""
    document = _page(
        "304期:绝杀一尾[4] 开狗21准",
        "305期:绝杀一尾[6] 开0000准",
        "305期:绝杀一尾[7] 开0000准",
    )

    decision = validate_documents(
        [Document(URL, document, "rendered")],
        NAME,
        limit=0,
        pick="bottom",
        rule=_rule(),
        target_period=305,
    )

    assert [(record.period, record.value()) for record in decision.records] == [(305, "7")]


def test_cross_document_same_period_conflict_is_rejected() -> None:
    first = Document(
        URL,
        _page("304期:绝杀一尾[4] 开狗21准", "305期:绝杀一尾[6] 开0000准"),
        "rendered",
    )
    second = Document(
        URL,
        _page("304期:绝杀一尾[4] 开狗21准", "305期:绝杀一尾[7] 开0000准"),
        "rendered",
    )

    with pytest.raises(LookupError, match="数据冲突"):
        validate_documents(
            [first, second],
            NAME,
            limit=0,
            pick="bottom",
            rule=_rule(),
            target_period=305,
        )


def test_foreign_document_without_site_anchor_is_rejected() -> None:
    document = _page("305期:绝杀一尾[6] 开0000准", head="305期:其他站点(绝杀一尾)准准准!")

    assert (
        extract_dedicated_records(
            document,
            NAME,
            PARSER,
            chunk_keywords=("可见一斑", "绝杀一尾"),
            max_chunk_span=240,
            require_site_keyword=True,
            pick="bottom",
        )
        == []
    )


def test_dedicated_failure_does_not_fall_back_to_generic_parser() -> None:
    rule = _rule()

    assert "compact" not in rule.allowed_sources
    assert set(rule.allowed_sources) == {"dedicated"}
