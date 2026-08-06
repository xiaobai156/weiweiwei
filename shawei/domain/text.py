from __future__ import annotations

import html
import re


_PICK_ALIASES = {
    "top": "top",
    "顶部": "top",
    "上": "top",
    "bottom": "bottom",
    "尾部": "bottom",
    "底部": "bottom",
    "下": "bottom",
    "buttom": "bottom",
}


def normalize_text(text: str) -> str:
    text = html.unescape(text or "")
    text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    replacements = {
        "\xa0": " ",
        "\u3000": " ",
        "⒈": "1",
        "①": "1",
        "⑴": "1",
        "❶": "1",
        "絕": "绝",
        "殺": "杀",
        "開": "开",
        "綜": "综",
        "區": "区",
        "綠": "绿",
        "紅": "红",
        "藍": "蓝",
        "雙": "双",
        "單": "单",
        "準": "准",
        "碼": "码",
        "頭": "头",
        "【": "[",
        "】": "]",
        "《": "[",
        "》": "]",
        "（": "(",
        "）": ")",
        "：": ":",
        "？": "?",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    compact = text.replace(" ", "")
    return any(keyword in text or keyword.replace(" ", "") in compact for keyword in keywords)


def contains_none(text: str, keywords: tuple[str, ...]) -> bool:
    return not any(keyword in text for keyword in keywords)


def canonical_pick(pick: str | None) -> str:
    value = normalize_text(str(pick or "")).lower()
    try:
        return _PICK_ALIASES[value]
    except KeyError as exc:
        raise ValueError(f"pick方向无效: {pick}") from exc


def is_bottom_pick(pick: str) -> bool:
    return canonical_pick(pick) == "bottom"


def boundary_pick_label(pick: str) -> str:
    return "bottom/尾部/下" if canonical_pick(pick) == "bottom" else "top/顶部/上"
