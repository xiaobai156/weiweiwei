# -*- coding: utf-8 -*-
"""跨期借值第三轮修复的回归测试：取值按「出现位置」而非模式优先级。

背景：原 _extract_tail_value 遍历 TAIL_PATTERNS，遇到第一个能匹配的模式就返回。
「绝杀一尾」是强模式（排在前），「杀:7尾」是弱模式（排在后），于是

    本期杀:7尾: 0000 准 上期绝杀一尾5 开:12准

会先命中「绝杀一尾5」，把上期的 5 当本期值。这种借值发生在单块内部、
不产生同期冲突，validator 的边界与冲突校验都看不见。

修复后按匹配出现位置从前往后取：真实站点一律把本期写在块首、
上期/回顾写在后面，位置序等价于时间序。
"""
from __future__ import annotations

import pytest

from shawei.parsers.common import _extract_tail_value
from shawei.parsers.topic import _annual_delta


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


@pytest.mark.parametrize(
    ("previous", "current", "expected"),
    [
        (365, 1, 1),      # 跨年递增：数值大幅变小，实际是下一期
        (1, 365, -1),     # 跨年递减：数值大幅变大，实际是上一期
        (298, 297, -1),
        (298, 299, 1),
        (5, 5, 0),
    ],
)
def test_annual_delta_normalises_year_wrap(
    previous: int, current: int, expected: int
) -> None:
    assert _annual_delta(previous, current) == expected
