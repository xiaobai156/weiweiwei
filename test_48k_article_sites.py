import re

import pytest

from shawei.config.constants import TWO_TAIL_SITE_URLS
from shawei.config.rules import effective_rule_for
from shawei.domain.models import StrictRule
from shawei.parsers.dedicated import extract_dedicated_records
from shawei.persistence.cache_repository import is_valid_result_value
from shawei.validation.validator import validate_documents


SITES = {
    "白杨金牌": (
        "https://4.48kk49.com:1888/Article/ar_content/id/1556/tid/82.html",
        "top",
        "8",
        "single",
        ("稳杀一尾",),
        "★白杨★金牌【稳杀一尾】",
        "白杨金牌稳杀一尾",
    ),
    "径宅姐": (
        "https://4.48kk49.com:1888/Article/ar_content/id/1544/tid/82.html",
        "top",
        "1",
        "single",
        ("稳杀一尾",),
        "径宅姐公开了【稳杀一尾】",
        "稳杀一尾",
    ),
    "清肝明目": (
        "https://4.48kk49.com:1888/Article/ar_content/id/1543/tid/82.html",
        "top",
        "9",
        "single",
        ("绝杀一尾", "㊣绝杀一尾"),
        "清肝明目㊣绝杀一尾",
        "㊣绝杀一尾",
    ),
    "小小乾坤": (
        "https://4.48kk49.com:1888/Article/ar_content/id/1469/tid/82.html",
        "top",
        "8、0",
        "two",
        ("准杀二尾",),
        "小小乾坤省钱【准杀二尾】",
        "小小乾坤准杀二尾",
    ),
    "热血风云": (
        "https://4.48kk49.com:1888/Article/ar_content/id/1452/tid/82.html",
        "top",
        "9、5",
        "two",
        ("绝杀二尾",),
        "热血风云再现【绝杀二尾】",
        "热血风云绝杀二尾",
    ),
    "小屈大伸": (
        "https://4.48kk49.com:1888/Article/ar_content/id/1449/tid/82.html",
        "top",
        "9",
        "single",
        ("绝杀一尾", "原创一尾"),
        "小屈大伸原创【绝杀一尾】",
        "小屈大伸原创一尾",
    ),
    "我是静静": (
        "https://4.48kk49.com:1888/Article/ar_content/id/1434/tid/82.html",
        "top",
        "8",
        "single",
        ("绝杀一尾", "我是静静绝杀一尾"),
        "我是静静|㊣区【绝杀一尾】",
        "我是静静绝杀一尾",
    ),
}


def _page(name: str, title: str, row_keyword: str, values: list[tuple[int, str]]) -> str:
    def tail_markup(value: str) -> str:
        return ",".join(f"{part}尾" for part in value.split("、"))

    rows = "".join(
        f"<p>{period}期 {row_keyword} : 【{tail_markup(value)}】开 {draw} 准</p>"
        for period, value in values
        for draw in (("??",) if period == 225 else ("猴23",))
    )
    return (
        "<html><body>"
        f"<h2>225期: {title}</h2>"
        '<div class="content"><p class="time">历史记录</p>'
        f'<div class="lower">{rows}</div>'
        "<div>上一篇：225期: 邻文章</div></div>"
        "</body></html>"
    )


FIXTURES = {
    name: _page(
        name,
        title,
        row_keyword,
        [(225, value), (224, "4"), (223, "2")]
        if kind == "single"
        else [(225, value), (224, "7、5"), (223, "6、4")],
    )
    for name, (_url, _pick, value, kind, _keywords, title, row_keyword) in SITES.items()
}
FIXTURES["我是静静"] = _page(
    "我是静静",
    SITES["我是静静"][5],
    SITES["我是静静"][6],
    [(225, "8")],
)


def _rule(name: str) -> StrictRule:
    url = SITES[name][0]
    return effective_rule_for(url, name)


def _records(name: str):
    rule = _rule(name)
    return extract_dedicated_records(
        FIXTURES[name],
        name,
        rule.dedicated_parser,
        chunk_keywords=rule.chunk_keywords,
        target_period=225,
        pick="top",
        require_site_keyword=rule.require_site_keyword,
    )


def test_all_seven_sites_have_explicit_article_rules_and_config_entries() -> None:
    import json
    from pathlib import Path

    configured = {
        (item["name"], item["url"], item["pick"])
        for item in json.loads(Path("sites.json").read_text(encoding="utf-8"))
        if not item.get("archived")
    }
    for name, (url, pick, _value, _kind, keywords, _title, _row_keyword) in SITES.items():
        rule = _rule(name)
        assert rule.allowed_sources == ("dedicated",)
        assert rule.chunk_keywords == keywords
        assert (name, url, pick) in configured


def test_single_and_two_tail_contracts_are_url_bound() -> None:
    two_tail_names = {"小小乾坤", "热血风云"}
    two_tail_urls = {SITES[name][0] for name in two_tail_names}
    assert two_tail_urls <= TWO_TAIL_SITE_URLS
    assert is_valid_result_value("8、0", SITES["小小乾坤"][0])
    assert is_valid_result_value("9、5", SITES["热血风云"][0])
    assert not is_valid_result_value("8、0", SITES["白杨金牌"][0])


@pytest.mark.parametrize("name", list(SITES))
def test_article_parser_returns_the_expected_225_value(name: str) -> None:
    records = _records(name)
    assert records
    assert records[0].period == 225
    assert records[0].value() == SITES[name][2]
    assert records[0].draw_text == "开"


@pytest.mark.parametrize("name", list(SITES))
def test_top_boundary_rejects_224_even_when_the_row_exists(name: str) -> None:
    rule = _rule(name)
    with pytest.raises(LookupError, match="绝对top边界是225期"):
        validate_documents(
            [FIXTURES[name]],
            name,
            pick="top",
            rule=rule,
            target_period=224,
        )


def test_article_identity_is_bound_to_the_h2_title() -> None:
    text = FIXTURES["白杨金牌"].replace("225期: ★白杨★金牌", "225期: 冒名文章")
    rule = _rule("白杨金牌")
    records = extract_dedicated_records(
        text,
        "白杨金牌",
        rule.dedicated_parser,
        chunk_keywords=rule.chunk_keywords,
        target_period=225,
        pick="top",
        require_site_keyword=rule.require_site_keyword,
    )
    assert records == []


def test_rendered_plain_text_accepts_decorated_article_identity() -> None:
    plain = re.sub(r"<[^>]+>", " ", FIXTURES["白杨金牌"])
    plain = plain.replace("白杨金牌稳杀一尾", "稳杀一尾")
    rule = _rule("白杨金牌")
    records = extract_dedicated_records(
        plain,
        "白杨金牌",
        rule.dedicated_parser,
        chunk_keywords=rule.chunk_keywords,
        target_period=225,
        pick="top",
        require_site_keyword=rule.require_site_keyword,
    )
    assert records[0].value() == "8"


def test_same_period_conflicting_documents_fail() -> None:
    original = FIXTURES["白杨金牌"]
    conflicting = original.replace("【8尾】", "【7尾】", 1)
    rule = _rule("白杨金牌")
    with pytest.raises(LookupError, match="225期存在多个候选且数据冲突"):
        validate_documents(
            [original, conflicting],
            "白杨金牌",
            pick="top",
            rule=rule,
            target_period=225,
        )
