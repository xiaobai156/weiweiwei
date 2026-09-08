import pytest

from shawei.config.rules import effective_rule_for
from shawei.domain.models import StrictRule
from shawei.parsers.dedicated import extract_dedicated_records
from shawei.validation.validator import validate_documents


SITES = {
    "曾道人每期": {
        "url": "https://4.48kk49.com:1888/Article/ar_content/id/199/tid/4.html",
        "value": "3",
        "title": "曾道人每期绝杀一尾【已公开】",
        "keywords": ("绝杀一尾", "曾道人每期绝杀一尾"),
    },
    "管家婆精准绝杀一尾": {
        "url": "https://4.48kk49.com:1888/Article/ar_content/id/173/tid/5.html",
        "value": "5",
        "title": "管家婆‖≡『精准绝杀一尾』≡‖100%准",
        "keywords": ("绝杀一尾", "管家婆精准绝杀一尾"),
    },
}


def _page(title: str, value: str) -> str:
    rows = "".join(
        f"<p>{period}期 绝杀一尾 : 【{tail}尾】开 {draw} 准</p>"
        for period, tail, draw in (
            (225, value, "??"),
            (224, "8", "09"),
            (223, "6", "23"),
        )
    )
    return (
        "<html><body>"
        f"<h2>225期: {title}</h2>"
        f'<div class="content"><div class="lower">{rows}</div>'
        "<div>上一篇：225期: 邻文章</div></div>"
        "</body></html>"
    )


def _rule(name: str) -> StrictRule:
    return effective_rule_for(SITES[name]["url"], name)


@pytest.mark.parametrize("name", list(SITES))
def test_new_sites_have_url_bound_static_article_rules_and_config(name: str):
    import json
    from pathlib import Path

    rule = _rule(name)
    configured = {
        (item["name"], item["url"], item["pick"])
        for item in json.loads(Path("sites.json").read_text(encoding="utf-8"))
        if not item.get("archived")
    }
    assert rule.allowed_sources == ("dedicated",)
    assert rule.dedicated_parser == "article_static_single_tail"
    assert rule.chunk_keywords == SITES[name]["keywords"]
    assert (name, SITES[name]["url"], "top") in configured


@pytest.mark.parametrize("name", list(SITES))
def test_new_sites_parse_the_real_225_shape_and_history(name: str):
    rule = _rule(name)
    records = extract_dedicated_records(
        _page(SITES[name]["title"], SITES[name]["value"]),
        name,
        rule.dedicated_parser,
        chunk_keywords=rule.chunk_keywords,
        target_period=225,
        pick="top",
        require_site_keyword=rule.require_site_keyword,
    )
    assert [(record.period, record.value()) for record in records] == [
        (225, SITES[name]["value"]),
        (224, "8"),
        (223, "6"),
    ]


@pytest.mark.parametrize("name", list(SITES))
def test_new_sites_enforce_225_top_boundary_and_reject_224(name: str):
    rule = _rule(name)
    decision = validate_documents(
        [_page(SITES[name]["title"], SITES[name]["value"])],
        name,
        pick="top",
        rule=rule,
        target_period=225,
    )
    assert [record.value() for record in decision.records] == [SITES[name]["value"]]

    with pytest.raises(LookupError, match="绝对top边界是225期，不是指定224期"):
        validate_documents(
            [_page(SITES[name]["title"], SITES[name]["value"])],
            name,
            pick="top",
            rule=rule,
            target_period=224,
        )


@pytest.mark.parametrize("name", list(SITES))
def test_new_sites_reject_wrong_article_identity(name: str):
    rule = _rule(name)
    wrong_title = _page(SITES[name]["title"], SITES[name]["value"]).replace(
        SITES[name]["title"], "冒名文章"
    )
    records = extract_dedicated_records(
        wrong_title,
        name,
        rule.dedicated_parser,
        chunk_keywords=rule.chunk_keywords,
        target_period=225,
        pick="top",
        require_site_keyword=rule.require_site_keyword,
    )
    assert records == []


def test_new_site_same_period_conflict_is_not_resolved_by_top_selection():
    name = "曾道人每期"
    rule = _rule(name)
    original = _page(SITES[name]["title"], SITES[name]["value"])
    conflicting = original.replace("【3尾】", "【4尾】", 1)
    with pytest.raises(LookupError, match="225期存在多个候选且数据冲突"):
        validate_documents(
            [original, conflicting],
            name,
            pick="top",
            rule=rule,
            target_period=225,
        )
