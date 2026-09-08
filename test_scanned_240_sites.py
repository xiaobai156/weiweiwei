import pytest

from shawei.config.constants import TWO_TAIL_SITE_URLS
from shawei.config.rules import effective_rule_for
from shawei.config.sites import load_sites
from shawei.persistence.cache_repository import is_valid_result_value
from shawei.validation.validator import validate_documents


SCANNED_SITES = {
    "舒舒服服": ("https://aszmkf.c3z3l-qrlqm-mwgccr.work:29411/article/lottery/6a082c7108adb5ed7357ef3b?url=lhw", True),
    "凉风有信": ("https://aszmkf.c3z3l-qrlqm-mwgccr.work:29411/article/lottery/6a083d1308adb5ed7357f036?url=lhw", True),
    "网开三面": ("https://knfoaep.ivqs8-1depw-yoirtw.xyz:29444/article/lottery/6a095a86291caff3edcb8a9d?url=lf", False),
    "拔地而起": ("https://knfoaep.ivqs8-1depw-yoirtw.xyz:29444/article/lottery/6a09527a291caff3edcb8a33?url=lf", True),
    "振奋人心": ("https://rwraojf.l54vq-9httr-cmdnip.work:29477/article/lottery/6a5271005e6c7637a3f55124?url=xdr", False),
    "再度归来": ("https://0130190827.673454.xyz/bbs/topic.php?id=20144", True),
    "猫咪尾巴": ("https://0130190827.673454.xyz/bbs/topic.php?id=20150", False),
    "马料发财": ("https://0130190827.673454.xyz/bbs/topic.php?id=20140", False),
    "童颜鹤发": ("https://67806780827.325346.xyz/bbs/topic.php?id=19812", False),
    "暖夏少年": ("https://67806780827.234535.xyz/bbs/topic.php?id=22163", True),
    "劲爆猛料": ("https://67806780827.234535.xyz/bbs/topic.php?id=19587", False),
    "一心为民": ("https://88888020827.983654.xyz/bbs/topic.php?id=20758", False),
    "喜欢中奖": ("https://88888020827.833567.xyz/bbs/topic.php?id=22608", True),
    "推陈出新": ("https://88888020827.833567.xyz/bbs/topic.php?id=20522", True),
    "江山如画": ("https://88888020827.833567.xyz/bbs/topic.php?id=20972", False),
    "百财王特": ("https://88888020827.833567.xyz/bbs/topic.php?id=19832", False),
    "怪咖小生": ("https://0130190827.657954.xyz/bbs/topic.php?id=20210", True),
}


def test_scanned_sites_have_bottom_dedicated_rules_and_value_contracts() -> None:
    configured = {site.name: site for site in load_sites()}
    for name, (url, two_tail) in SCANNED_SITES.items():
        assert configured[name].url == url
        assert configured[name].pick == "bottom"
        rule = effective_rule_for(url, name)
        assert rule.allowed_sources == ("dedicated",)
        assert rule.dedicated_parser
        assert (url in TWO_TAIL_SITE_URLS) is two_tail
        assert is_valid_result_value("1、2" if two_tail else "1", url)


def test_scanned_dynamic_article_rule_honors_field_and_bottom_boundary() -> None:
    name = "舒舒服服"
    url = SCANNED_SITES[name][0]
    rule = effective_rule_for(url, name)
    text = (
        "240期:舒舒服服[绝杀②尾]作者:舒舒服服 "
        "239期:舒舒服服 绝杀②尾[6.7]开:05准 "
        "240期:舒舒服服 绝杀②尾[8.1]开:00准"
    )
    decision = validate_documents([text], name, pick="bottom", rule=rule, target_period=240)
    assert [record.value() for record in decision.records] == ["8、1"]
    with pytest.raises(LookupError, match="绝对bottom边界是240期"):
        validate_documents([text], name, pick="bottom", rule=rule, target_period=239)
    wrong_field = text.replace("绝杀②尾", "杀肖")
    decision = validate_documents(
        [wrong_field], name, pick="bottom", rule=rule, target_period=240
    )
    assert decision.records == ()


def test_scanned_forum_rule_rejects_nonexistent_period() -> None:
    name = "猫咪尾巴"
    url = SCANNED_SITES[name][0]
    rule = effective_rule_for(url, name)
    text = (
        "240期:[猫咪尾巴★绝杀1尾]作者:猫咪尾巴 "
        "239期:『猫咪尾巴』绝杀1尾[9]开:05准 "
        "240期:『猫咪尾巴』绝杀1尾[7]开:00准"
    )
    decision = validate_documents([text], name, pick="bottom", rule=rule, target_period=240)
    assert [record.value() for record in decision.records] == ["7"]
    with pytest.raises(LookupError, match="绝对bottom边界是240期"):
        validate_documents([text], name, pick="bottom", rule=rule, target_period=241)
