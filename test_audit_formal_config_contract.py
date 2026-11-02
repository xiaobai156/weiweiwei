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
    sealed = {
        (item["name"], item["url"])
        for item in json.loads(SITES_JSON_PATH.read_text(encoding="utf-8-sig"))
        if item.get("archived") and item["url"] in TWO_TAIL_SITE_URLS
    }

    assert {url for _, url in authorized} | {url for _, url in sealed} == set(
        TWO_TAIL_SITE_URLS
    )
    assert {name for name, _ in authorized} | {name for name, _ in sealed} == {
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


def test_discuz_main_post_parser_reads_revealed_locked_tail() -> None:
    from shawei.parsers.topic import extract_discuz_main_post_records

    document = '''<link rel="canonical" href="https://example.com/thread-272-1-1.html">
    <h1><span id="thread_subject">【272期】【张天师㊣新澳门】杀一尾</span></h1>
    <div id="post_1">
      <div id="favatar1"><div class="authi"><a href="space-uid-1.html">★张天师★</a></div></div>
      <table><tbody><tr><td id="postmessage_1">欢迎跟踪<br>
    271期: ★★★张天师★★★绝杀一尾【4尾】开:35准<br>
    272期: ★★★张天师★★★绝杀一尾【2尾】开:00准</td></tr></tbody></table>
    </div>'''
    records = extract_discuz_main_post_records(
        document,
        "张天师",
        ("张天师", "绝杀一尾"),
        (),
        True,
        272,
        "https://example.com/thread-272-1-1.html",
    )

    assert [(record.period, record.value()) for record in records] == [(271, "4"), (272, "2")]
