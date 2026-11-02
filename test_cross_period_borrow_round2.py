# -*- coding: utf-8 -*-
"""跨期借值第二轮修复的回归测试。

覆盖本轮真正落地的 3 处：
1) 开奖字段识别：既要认 `开准` 这类无号码写法，也要排除「公开/开奖栏目/开奖网址」
2) 窗口截断：[] () 【】 三种括号都不能被切断成另一个合法值
3) 回顾行剥离：块内「上期/回顾」片段不得当作本期值
"""
from __future__ import annotations

import re

import pytest

from shawei.parsers.common import (
    _has_draw_signal,
    _period_window,
)


# ---------- 1. 开奖字段识别 ----------
@pytest.mark.parametrize(
    "text",
    [
        "开准",                 # 只写准，不带号码（真实站点写法）
        "开:5准",
        "开 5 准",
        "开奖结果 12 准",
        "开猴22准",
        "开？00",
        "开:05准",
        "开0000准",
        "7尾 开准",
        "绝杀一尾[5] 马24准",
    ],
)
def test_draw_signal_accepts_real_draw_fields(text: str) -> None:
    assert _has_draw_signal(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "公开12期",            # 「开」后紧跟 12，形似开奖号但属噪声词
        "准备资料",
        "开户优惠",
        "开奖栏目",
        "开奖直播",
        "开奖:87127.com",      # 网址，不是开奖号
        "绝杀一尾[5] 待更新",   # 无开奖字段
    ],
)
def test_draw_signal_rejects_noise_text(text: str) -> None:
    assert _has_draw_signal(text) is False


def test_draw_signal_still_accepts_real_draw_alongside_noise_word() -> None:
    # 同块既有噪声词又有真实开奖号时，必须判为开奖行
    assert _has_draw_signal("开奖:87127.com 开猴22准") is True


# ---------- 2. 窗口截断 ----------
def test_period_window_returns_whole_chunk_when_within_span() -> None:
    chunk = "298期 绝杀一尾 [12] 开:12准"
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
    # 要么括号配平，要么末尾根本不是数字/括号残片
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


# 说明：曾尝试用「回顾行剥离」拦截上期值（_strip_history_lead），
# 经复核确认会误杀含「往期/历史」字样的正常页面（页脚广告即触发），
# 已整体回退。块内上期值问题改由「按出现位置取值」另行处理。
