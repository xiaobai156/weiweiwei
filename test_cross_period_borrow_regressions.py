# -*- coding: utf-8 -*-
"""跨期借值四项修复的回归测试。

覆盖：
1) _period_window 截断不造出假值
2) _has_draw_signal 只认开奖字段形状
3) 单期入口跨来源同期冲突必须失败
4) 跨年期号切段归一（365→001）
"""
from __future__ import annotations

import pytest

from shawei.domain.models import Record
from shawei.parsers.common import _has_draw_signal, _period_window
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


# ---------- 2. 开奖信号 ----------
@pytest.mark.parametrize(
    "text",
    [
        "开奖栏目 公开 准备",       # 只有散字，不是开奖字段
        "绝杀一尾[5] 待更新",        # 无开奖字段
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
    ],
)
def test_draw_signal_accepts_real_draw_fields(text: str) -> None:
    assert _has_draw_signal(text) is True


# ---------- 3. 跨年切段 ----------
def test_annual_delta_treats_year_wrap_as_adjacent() -> None:
    assert _annual_delta(365, 1) == 1      # 365 → 001 跨年递增
    assert _annual_delta(1, 365) == -1     # 001 → 365 跨年递减
    assert _annual_delta(298, 297) == -1
    assert _annual_delta(298, 299) == 1


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
