# -*- coding: utf-8 -*-
"""扫描期（239/240 期）新增特殊站点的配置契约回归测试。

合并自 test_scanned_239_special_sites.py 与 test_scanned_240_sites.py：
两批站点都是同一轮审计扫描后加入的，契约相同（URL 绑定 + bottom + 专属解析 +
单/双尾取值合法 + 边界报错），因此放在一个文件里按批次分组维护。
"""
import json
from pathlib import Path

import pytest

from shawei.config.constants import TWO_TAIL_SITE_URLS
from shawei.config.rules import effective_rule_for
from shawei.persistence.cache_repository import is_valid_result_value
from shawei.validation.validator import validate_documents


# ---------- 239 期扫描批次（14 站，单尾） ----------
SPECIAL_SITES = {
    "天地良心": ("https://drxgkjt.uu1oc-eyjpt-uxyccu.xyz:29400/article/lottery/6a33e92ddfa16552b923d408?url=jyb", 240),
    "秋水伊人": ("https://nwrkkmv.rx287-rkrai-jsjccc.xyz:29499/article/lottery/6a55d62cf447e21b02daa632?url=ggz", 239),
    "微风习习": ("https://buzsxio.821n4-hgj04-edkrft.xyz:29455/article/lottery/6a7ee533ee4739fbe9ea270d?url=bxj", 239),
    "顺流而下": ("https://buzsxio.821n4-hgj04-edkrft.xyz:29455/article/lottery/6a73f86e2822d465035fbb61?url=bxj", 239),
    "春云满望": ("https://pgyzulb.iwnn7-gyyip-pnpfqv.work:29477/article/lottery/6a58e7d2f447e21b02db8190?url=bflc", 239),
    "金帝护卫": ("https://herymche.x6l2j-h6kfu-qdresg.work:29466/article/lottery/6a0452504ea5c20141013e9b?url=txbb", 240),
    "澳彩碼王": ("https://12388990827.794555.xyz/bbs/topic.php?id=19959", 240),
    "饱食暖衣": ("https://12388990827.794555.xyz/bbs/topic.php?id=20270", 240),
    "寻宝探码": ("https://12388990827.688756.xyz/bbs/topic.php?id=19155", 239),
    "财源滚滚": ("https://12388990827.688756.xyz/bbs/topic.php?id=19128", 239),
    "潇洒人生": ("https://0130190827.767566.xyz/bbs/topic.php?id=30780", 239),
    "夜空无痕": ("https://88888020827.897657.xyz/bbs/topic.php?id=20207", 239),
    "安身立命": ("https://88888020827.897657.xyz/bbs/topic.php?id=20215", 239),
    "海角天涯": ("https://88888020827.997595.xyz/bbs/topic.php?id=19471", 239),
}


# ---------- 240 期扫描批次（17 站，含双尾） ----------
SCANNED_SITES = {
    "舒舒服服": ("https://aszmkf.c3z3l-qrlqm-mwgccr.work:29411/article/lottery/6a082c7108adb5ed7357ef3b?url=lhw", True),
    "凉风有信": ("https://aszmkf.c3z3l-qrlqm-mwgccr.work:29411/article/lottery/6a083d1308adb5ed7357f036?url=lhw", True),
    "网开三面": ("https://knfoaep.ivqs8-1depw-yoirtw.xyz:29444/article/lottery/6a095a86291caff3edcb8a9d?url=lf", False),
    "拔地而起": ("https://knfoaep.ivqs8-1depw-yoirtw.xyz:29444/article/lottery/6a09527a291caff3edcb8a33?url=lf", True),
    "振奋人心": ("https://rwraojf.l54vq-9httr-cmdnip.work:29477/article/lottery/6a5271005e6c7637a3f55124?url=xdr", False),
    "再度归来": ("https://0130190827.673454.xyz/bbs/topic.php?id=20330", True),
    "猫咪尾巴": ("https://0130190827.673454.xyz/bbs/topic.php?id=20150", False),
    "马料发财": ("https://0130190827.673454.xyz/bbs/topic.php?id=20140", False),
    "童颜鹤发": ("https://67806780827.325346.xyz/bbs/topic.php?id=19581", False),
    "暖夏少年": ("https://67806780827.234535.xyz/bbs/topic.php?id=22163", True),
    "劲爆猛料": ("https://67806780827.234535.xyz/bbs/topic.php?id=19587", False),
    "一心为民": ("https://88888020827.983654.xyz/bbs/topic.php?id=20915", False),
    "喜欢中奖": ("https://88888020827.833567.xyz/bbs/topic.php?id=22608", True),
    "推陈出新": ("https://88888020827.833567.xyz/bbs/topic.php?id=20522", True),
    "江山如画": ("https://88888020827.833567.xyz/bbs/topic.php?id=20972", False),
    "百财王特": ("https://88888020827.833567.xyz/bbs/topic.php?id=19832", False),
    "怪咖小生": ("https://0130190827.657954.xyz/bbs/topic.php?id=20210", True),
}


def _configured_sites() -> dict[str, dict]:
    return {
        site["name"]: site
        for site in json.loads(Path("sites.json").read_text(encoding="utf-8-sig"))
    }


def test_special_sites_have_single_tail_bottom_dedicated_rules() -> None:
    configured = _configured_sites()
    for name, (url, _) in SPECIAL_SITES.items():
        site = configured[name]
        assert site["url"] == url
        assert site["pick"] == "bottom"
        rule = effective_rule_for(url, name)
        assert rule.allowed_sources == ("dedicated",)
        assert rule.dedicated_parser
        assert url not in TWO_TAIL_SITE_URLS
        assert is_valid_result_value("1", url)
        assert not is_valid_result_value("1、2", url)


def test_special_authorization_records_all_sites_and_live_periods() -> None:
    path = Path(__file__).with_name("new_site_special_exceptions.json")
    latest = json.loads(path.read_text(encoding="utf-8"))["additional_authorizations"][-1]
    assert set(latest["live_bottom_snapshot"]) == set(SPECIAL_SITES)
    assert {
        name: details["period"]
        for name, details in latest["live_bottom_snapshot"].items()
    } == {name: period for name, (_, period) in SPECIAL_SITES.items()}
    assert {site["name"] for site in latest["sites"]} == set(SPECIAL_SITES)


def test_scanned_sites_have_bottom_dedicated_rules_and_value_contracts() -> None:
    configured = _configured_sites()
    for name, (url, two_tail) in SCANNED_SITES.items():
        assert configured[name]["url"] == url
        assert configured[name]["pick"] == "bottom"
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
