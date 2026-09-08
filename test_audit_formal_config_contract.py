from __future__ import annotations

import json

from shawei.config.constants import TWO_TAIL_SITE_URLS
from shawei.config.paths import SITES_JSON_PATH
from shawei.config.rules import effective_rule_for
from shawei.config.sites import load_sites


def test_every_active_site_has_one_effective_url_bound_rule() -> None:
    sites = load_sites()

    assert len({site.name for site in sites}) == len(sites)
    for site in sites:
        rule = effective_rule_for(site.url, site.name)
        assert rule.site_url == site.url
        assert rule.allowed_sources
        if "dedicated" in rule.allowed_sources:
            assert rule.dedicated_parser


def test_two_tail_authorization_matches_active_configured_identities() -> None:
    sites = load_sites()
    authorized = {(site.name, site.url) for site in sites if site.url in TWO_TAIL_SITE_URLS}

    assert {url for _, url in authorized} == set(TWO_TAIL_SITE_URLS)
    assert {name for name, _ in authorized} == {
        "强烈招牌",
        "华丽恶梦",
        "专注凯子",
        "唯一火势",
        "如履薄冰",
        "跑马图",
        "赏心悦目",
        "夏雨雨人",
        "数据诗篇",
        "小小乾坤",
        "热血风云",
        "港澳彩票绝杀",
        "舒舒服服",
        "凉风有信",
        "拔地而起",
        "再度归来",
        "暖夏少年",
        "喜欢中奖",
        "推陈出新",
        "怪咖小生",
        "星槎渡海",
    }


def test_formal_json_has_only_supported_top_bottom_directions() -> None:
    payload = json.loads(SITES_JSON_PATH.read_text(encoding="utf-8-sig"))

    assert {item["pick"] for item in payload} <= {"top", "bottom"}
