# -*- coding: utf-8 -*-
"""「抓错数据」风险复核回归测试。

覆盖本轮修复（用户 2026-11-06 要求：审核抓错数据风险 → 修高危项）：

1) 块内跨期借值：明确标了「上期/回顾」的值不再被当本期值
2) 方向文档域：不同文档给出不同同期值时留告警，但保留按配置选权威文档
3) same_period 站点：同期多值只告警，不推翻「按方向取边」
4) 0 成功不滚动最近 10 期缓存（避免一次故障删掉本期已抓数据）
5) section 停止词生效；停止词排在数据行之前时退回不切窗口并告警
"""
from __future__ import annotations

import pytest

from shawei.cli.daily import should_update_cache
from shawei.domain.models import StrictRule
from shawei.parsers.common import (
    _extract_tail_value,
    extract_absolute_kill_section_records,
)
from shawei.validation import validator
from shawei.validation.validator import validate_documents


def _compact_rule(**overrides) -> StrictRule:
    base = {
        "allowed_sources": ("compact",),
        "chunk_keywords": ("杀一尾", "绝杀一尾"),
        "site_url": "https://t.example/a",
    }
    base.update(overrides)
    return StrictRule(**base)


# ---------- 1. 跨期借值 ----------
def test_previous_value_before_current_not_borrowed() -> None:
    assert _extract_tail_value("298期 上期杀一尾5 本期杀一尾7 开?") == 7


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # 上期词直接管辖取值字段：必须剔除
        ("298期 上期杀一尾5 开:12准", None),
        ("298期 上期公开 杀一尾5", None),
        # 上期词后面跟了开奖战绩词：那是本行说明，不能连坐
        ("298期 上期红单 杀一尾7 开:12准", 7),
        ("上期命中 杀一尾7", 7),
        ("298期 上期红单 杀一尾7 另一栏 杀一尾5 开:12准", 7),
        ("298期 上期命中 杀一尾7 备用 杀一尾5 开:12准", 7),
        # 未列入词表的战绩/记录词：结构守卫兜住，最多失败，绝不换值
        ("298期 上期连中 杀一尾7 备用 杀一尾5 开:12准", None),
        ("298期 上期全中 杀一尾7 推荐 杀一尾5 开:12准", None),
        ("298期 上期连红 杀一尾7 另一栏 杀一尾5 开:12准", None),
        ("298期 上期喜中 杀一尾7 备用 杀一尾5 开:12准", None),
        ("298期 上期走势图 杀一尾7 推荐 杀一尾5 开:12准", None),
        ("298期 上期开出 杀一尾7 另一栏 杀一尾5 开:12准", None),
        # 反向：上期词 + 预测记录词，单值也不能借
        ("298期 上期推荐命中 杀一尾5 开:12准", None),
        ("298期 上期开奖结果 杀一尾5 开:12准", None),
        ("298期 上期战绩 杀一尾5 开:12准", None),
        # 没有期面时间词：保持按位置取首值
        ("历史最高 杀一尾7", 7),
        ("回顾 杀一尾7", 7),
        ("298期 历史最高 杀一尾7 推荐 杀一尾5 开:12准", 7),
        # 站名出现在值之后，不能把排第一的本期值丢掉
        ("298期 绝杀一尾7 本站XX网 另一栏 绝杀一尾5", 7),
        ("298期 绝杀一尾7 作者:XX网 绝杀一尾5", 7),
        # 上期开奖字段不管辖后面的本期尾值
        ("298期 上期开奖 猴12 杀一尾7", 7),
        ("298期 对比上期，本期杀一尾7", 7),
    ],
)
def test_prior_period_word_only_applies_when_it_governs_the_value(
    text: str, expected: int | None
) -> None:
    """时间词只在直接管辖取值字段时剔除，避免「删掉首值换成后面的值」。"""
    assert _extract_tail_value(text) == expected


def test_tail_rejection_counter_is_observable() -> None:
    """真实抓取时要能分清「页面没数据」和「被期面守卫挡回」。"""
    from shawei.parsers.common import reset_tail_rejections, tail_rejection_counts

    reset_tail_rejections()
    assert tail_rejection_counts() == {}

    assert _extract_tail_value("298期 上期杀一尾5 开:12准") is None
    assert _extract_tail_value("298期 上期连中 杀一尾7 备用 杀一尾5 开:12准") is None

    counts = tail_rejection_counts()
    assert counts.get("窗口内只有上期值") == 1
    assert counts.get("上期值在前且无本期词") == 1

    # 正常取值不计数
    assert _extract_tail_value("298期 绝杀一尾7 开:12准") == 7
    assert tail_rejection_counts() == counts
    reset_tail_rejections()


def test_compact_pipeline_not_borrow_previous_period() -> None:
    decision = validate_documents(
        ["298期 上期杀一尾5 本期杀一尾7 开:12准"],
        "测试站",
        limit=0,
        pick="top",
        rule=_compact_rule(),
        target_period=298,
    )
    assert [record.as_line() for record in decision.records] == ["7尾 测试站"]


def test_only_previous_period_evidence_gives_no_value() -> None:
    decision = validate_documents(
        ["298期 上期杀一尾5 开:12准"],
        "测试站",
        limit=0,
        pick="top",
        rule=_compact_rule(),
        target_period=298,
    )
    assert [record.as_line() for record in decision.records] == []


def test_value_only_adjacent_to_previous_period_never_borrowed() -> None:
    """本期位置只有「7尾」而没有紧邻的杀尾字段时，宁可不给值也不借上期的 5。

    validate_documents 层表现为「无记录」，抓取层会把它转成该站失败（
    collect_site_records 在没有记录时抛 LookupError）。
    """
    decision = validate_documents(
        ["298期 上期杀一尾5 本期 7尾 开?"],
        "测试站",
        limit=0,
        pick="top",
        rule=_compact_rule(),
        target_period=298,
    )
    assert [record.as_line() for record in decision.records] == []


# ---------- 2. 方向文档域 ----------
def test_direction_scope_without_config_still_reports_conflict() -> None:
    rule = _compact_rule()
    with pytest.raises(LookupError, match="数据冲突"):
        validate_documents(
            ["298期 绝杀一尾7 开:12准", "298期 绝杀一尾5 开:34错"],
            "测试站",
            limit=0,
            pick="top",
            rule=rule,
            target_period=298,
        )


@pytest.mark.parametrize(
    ("scope", "expected"),
    [("top", "7尾 测试站"), ("bottom", "5尾 测试站")],
)
def test_direction_scope_warns_but_keeps_authoritative_document(
    scope: str, expected: str, capsys: pytest.CaptureFixture[str]
) -> None:
    decision = validate_documents(
        ["298期 绝杀一尾7 开:12准", "298期 绝杀一尾5 开:34错"],
        "测试站",
        limit=0,
        pick="top",
        rule=_compact_rule(direction_document_scope=scope),
        target_period=298,
    )

    assert [record.as_line() for record in decision.records] == [expected]
    assert "[文档域冲突]" in capsys.readouterr().err


def test_direction_scope_disjoint_warning_is_counted_for_summary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    validator.reset_run_warnings()
    validate_documents(
        ["298期 绝杀一尾7 开:12准", "298期 绝杀一尾5 开:34错"],
        "测试站",
        limit=0,
        pick="top",
        rule=_compact_rule(direction_document_scope="top"),
        target_period=298,
    )

    assert any("[文档域冲突]" in item for item in validator.run_warnings())
    validator.reset_run_warnings()
    assert validator.run_warnings() == ()


def test_duplicate_warnings_are_counted_once(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """重试/二次解析会重复调用，同一条告警只能计一次。"""
    validator.reset_run_warnings()
    for _ in range(2):
        validate_documents(
            ["298期 绝杀一尾7 开:12准", "298期 绝杀一尾5 开:34错"],
            "测试站",
            limit=0,
            pick="top",
            rule=_compact_rule(direction_document_scope="top"),
            target_period=298,
        )

    assert len(validator.run_warnings()) == 1
    validator.reset_run_warnings()


# ---------- 3. same_period 多值 ----------
def test_same_period_multi_value_warns_but_keeps_direction_pick(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rule = _compact_rule(same_period_record_selection=True)
    decision = validate_documents(
        ["298期 杀一尾7 开:12准 298期 杀一尾5 开:34准"],
        "测试站",
        limit=0,
        pick="bottom",
        rule=rule,
        target_period=298,
    )

    assert [record.as_line() for record in decision.records] == ["5尾 测试站"]
    selected = [
        candidate
        for candidate in decision.candidates
        if candidate.record.period == 298
    ]
    assert {(c.same_period_record_index, c.same_period_record_count) for c in selected} == {
        (1, 2),
        (2, 2),
    }
    captured = capsys.readouterr().err
    assert "同期多值" in captured
    assert "5、7" in captured or "7、5" in captured


def test_same_period_same_value_twice_does_not_warn(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rule = _compact_rule(same_period_record_selection=True)
    decision = validate_documents(
        ["298期 杀一尾7 开:12准 298期 杀一尾7 开:34准"],
        "测试站",
        limit=0,
        pick="bottom",
        rule=rule,
        target_period=298,
    )

    assert [record.as_line() for record in decision.records] == ["7尾 测试站"]
    assert "同期多值" not in capsys.readouterr().err


def test_single_document_same_period_multi_values_warns(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """普通站（非 same_period）同一文档同期多值也必须留痕。

    这条通道以前完全静默：正文值与推荐位值不同时按方向取边，取错无从发现。
    """
    decision = validate_documents(
        ["298期 杀一尾7 开:12准 298期 杀一尾5 开:34准"],
        "测试站",
        limit=0,
        pick="top",
        rule=_compact_rule(),
        target_period=298,
    )

    assert [record.as_line() for record in decision.records] == ["7尾 测试站"]
    assert "[块内多值]" in capsys.readouterr().err


# ---------- 4. 缓存闸门 ----------
@pytest.mark.parametrize(
    ("success_count", "total", "expected"),
    [(0, 10, False), (-1, 10, False), (1, 10, True), (10, 10, True), (11, 10, False), (0, 0, False)],
)
def test_should_update_cache_gate(success_count, total, expected) -> None:
    assert should_update_cache(success_count, total) is expected


# ---------- 5. section 停止词 ----------
def test_section_stop_keyword_cuts_after_data_rows() -> None:
    document = (
        "『绝杀一尾』"
        "298期绝杀一尾7开:12准"
        "『神奇四字』"
        "298期绝杀一尾5开:12准"
    )
    records = extract_absolute_kill_section_records(
        document,
        "测试站",
        section_keywords=("『绝杀一尾』",),
        section_stop_keywords=("『神奇四字』",),
        chunk_keywords=("绝杀一尾",),
        require_site_keyword=False,
    )

    assert [record.as_line() for record in records] == ["7尾 测试站"]


def test_section_stop_keyword_before_rows_falls_back_with_warning(
    capsys: pytest.CaptureFixture[str],
) -> None:
    document = "『绝杀一尾』『神奇四字』298期绝杀一尾7开:12准"
    records = extract_absolute_kill_section_records(
        document,
        "测试站",
        section_keywords=("『绝杀一尾』",),
        section_stop_keywords=("『神奇四字』",),
        chunk_keywords=("绝杀一尾",),
        require_site_keyword=False,
    )

    assert [record.as_line() for record in records] == ["7尾 测试站"]
    assert "停止词切分后无记录" in capsys.readouterr().err
