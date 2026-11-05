# -*- coding: utf-8 -*-
"""跨期借值回归测试（三轮修复合并为一个文件）。

覆盖：
1) _period_window 截断不造出假值（[] () 【】 三种括号都不许切出半个数字）
2) _has_draw_signal 只认开奖字段形状，排除「公开/开奖栏目/开奖网址」等噪声词
3) _extract_tail_value 按「出现位置」取值，不按模式优先级（第三轮修复）
4) 跨年期号切段归一（365→001）
"""
from __future__ import annotations

import re

import pytest

from shawei.domain.models import Record
from shawei.parsers.common import (
    _extract_tail_value,
    _has_draw_signal,
    _period_window,
)
from shawei.parsers.topic import (
    _annual_delta,
    _select_contiguous_record_segment,
    _topic_main_select_contiguous_segment,
)


# ---------- 1. 窗口截断 ----------
def test_period_window_never_truncates_mid_number() -> None:
    # 非法值 [12] 若切在 [1 与 2 之间，会变成合法值 [1]。
    chunk = "298期 绝杀一尾 [12] 开:12准"
    window = _period_window(chunk, 240)
    assert window == chunk  # 未超跨度，必须原样返回

    # 强制一个会切断数字的跨度：切点落进数字时必须回退到分隔处。
    long_chunk = "298期 绝杀一尾 [12] 开:12准 " + "导航" * 200
    truncated = _period_window(long_chunk, 240)
    assert not truncated.endswith("1"), "不能在数字中间切断造出假值"
    assert truncated.count("[") == truncated.count("]")


def test_period_window_keeps_full_value_when_short() -> None:
    chunk = "297期 绝杀一尾 [4] 开:00准"
    assert _period_window(chunk, 240) == chunk


@pytest.mark.parametrize(
    "chunk,span",
    [
        # 让括号正好落在 span 边界附近，制造「未闭合括号 + 半个数字」
        ("绝杀一尾" + "导航" * 77 + "[12] 开:12准", 240),
        ("绝杀一尾" + "导航" * 77 + "(12) 开:12准", 240),
        ("绝杀一尾" + "导航" * 77 + "【12】 开:12准", 240),
    ],
)
def test_period_window_never_leaves_half_number(chunk: str, span: int) -> None:
    """截断后不允许留下「未闭合括号 + 半个数字」这种可被当成合法值的残片。"""
    window = _period_window(chunk, span)
    balanced = all(
        window.count(open_ch) == window.count(close_ch)
        for open_ch, close_ch in (("[", "]"), ("(", ")"), ("【", "】"))
    )
    assert balanced or not re.search(r"[\d\[\]()【】]\s*$", window), (
        f"截断后留下半个数字/括号残片: {window[-40:]!r}"
    )


def test_period_window_does_not_end_with_digit_when_truncated() -> None:
    # 截断点落在数字中间会造出另一个合法值，必须回退
    chunk = "298期 绝杀一尾 12" + "导航" * 200
    window = _period_window(chunk, 240)
    assert not window.endswith("12"), "不能在数字中间切断造出假值"
    assert len(window) < len(chunk), "本用例必须真正触发截断"


# ---------- 2. 开奖信号 ----------
@pytest.mark.parametrize(
    "text",
    [
        "开奖栏目 公开 准备",       # 只有散字，不是开奖字段
        "绝杀一尾[5] 待更新",        # 无开奖字段
        "公开12期",                 # 「开」后紧跟 12，形似开奖号但属噪声词
        "准备资料",
        "开户优惠",
        "开奖栏目",
        "开奖直播",
        "开奖:87127.com",           # 网址，不是开奖号
    ],
)
def test_draw_signal_rejects_non_draw_text(text: str) -> None:
    assert _has_draw_signal(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "298期绝杀一尾[5]开猴22准",
        "绝杀一尾[5]开:?00准",
        "绝杀一尾[5]开0000准",
        "绝杀一尾[5]开 ?? 准",
        "绝杀一尾[5] 马24准",
        "绝杀一尾[5]开:?00准",
        "绝杀一尾[5]开 ?? 准",
        "开准",                     # 只写准，不带号码（真实站点写法）
        "开:5准",
        "开 5 准",
        "开奖结果 12 准",
        "开猴22准",
        "开？00",
        "开:05准",
        "7尾 开准",
    ],
)
def test_draw_signal_accepts_real_draw_fields(text: str) -> None:
    assert _has_draw_signal(text) is True


def test_draw_signal_still_accepts_real_draw_alongside_noise_word() -> None:
    # 同块既有噪声词又有真实开奖号时，必须判为开奖行
    assert _has_draw_signal("开奖:87127.com 开猴22准") is True


# ---------- 3. 取值按出现位置（第三轮修复） ----------
def test_tail_value_prefers_first_occurrence_not_pattern_priority() -> None:
    """本期弱写法在前、上期强写法在后时，必须取本期值。"""
    text = "本期杀:7尾: 0000 准 上期绝杀一尾5 开:12准"
    assert _extract_tail_value(text) == 7


def test_tail_value_respects_document_order_when_history_first() -> None:
    """上期片段确实排在本期之前时，按位置取到的就是它（保持文档顺序语义）。"""
    text = "上期绝杀一尾5 开:12准 本期杀:7尾: 0000 准"
    assert _extract_tail_value(text) == 5


def test_tail_value_single_occurrence_unchanged() -> None:
    assert _extract_tail_value("298期 绝杀一尾[7] 开:12准") == 7


def test_tail_value_still_rejects_multi_tail_field() -> None:
    """单尾站点不得从双尾字段里挑一个值。"""
    assert _extract_tail_value("绝杀一尾 2、3尾 开:12准") is None


# ---------- 4. 跨年切段 ----------
def test_annual_delta_treats_year_wrap_as_adjacent() -> None:
    assert _annual_delta(365, 1) == 1      # 365 → 001 跨年递增
    assert _annual_delta(1, 365) == -1     # 001 → 365 跨年递减
    assert _annual_delta(298, 297) == -1
    assert _annual_delta(298, 299) == 1
    assert _annual_delta(5, 5) == 0


def test_segment_selection_does_not_pick_last_year_on_year_wrap() -> None:
    # 递减历史列表跨年绕回：2 → 1 → 365 → 364 是同一段连续递减
    records = [
        Record(tail=8, period=2, site_name="跨年站"),
        Record(tail=6, period=1, site_name="跨年站"),
        Record(tail=5, period=365, site_name="跨年站"),
        Record(tail=4, period=364, site_name="跨年站"),
    ]
    segment = _select_contiguous_record_segment(records, "bottom")
    assert [r.period for r in segment] == [2, 1, 365, 364]
    assert segment[-1].tail == 4

    # 指定目标期时，必须返回包含目标期的那一段
    target = _select_contiguous_record_segment(records, "bottom", target_period=2)
    assert any(r.period == 2 for r in target)


def test_segment_selection_skips_unrelated_last_block() -> None:
    # 末尾另起一段无关期号时，指定目标期必须选回目标期所在段
    records = [
        Record(tail=8, period=2, site_name="跨年站"),
        Record(tail=6, period=1, site_name="跨年站"),
        Record(tail=9, period=88, site_name="无关块"),
    ]
    target = _select_contiguous_record_segment(records, "bottom", target_period=1)
    assert [r.period for r in target] == [2, 1]


def test_topic_main_segment_shares_year_wrap_rule() -> None:
    rows = [(2, "8"), (1, "6"), (365, "5"), (364, "4")]
    segment = _topic_main_select_contiguous_segment(rows, "bottom")
    assert [period for period, _ in segment] == [2, 1, 365, 364]
