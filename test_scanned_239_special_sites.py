import json
from pathlib import Path

from shawei.config.constants import TWO_TAIL_SITE_URLS
from shawei.config.rules import effective_rule_for
from shawei.persistence.cache_repository import is_valid_result_value


SPECIAL_SITES = {
    "天地良心": ("https://drxgkjt.uu1oc-eyjpt-uxyccu.xyz:29400/article/lottery/6a33e92ddfa16552b923d408?url=jyb", 240),
    "秋水伊人": ("https://nwrkkmv.rx287-rkrai-jsjccc.xyz:29499/article/lottery/6a55d62cf447e21b02daa632?url=ggz", 239),
    "微风习习": ("https://buzsxio.821n4-hgj04-edkrft.xyz:29455/article/lottery/6a7ee533ee4739fbe9ea270d?url=bxj", 239),
    "顺流而下": ("https://buzsxio.821n4-hgj04-edkrft.xyz:29455/article/lottery/6a73f86e2822d465035fbb61?url=bxj", 239),
    "春云满望": ("https://pgyzulb.iwnn7-gyyip-pnpfqv.work:29477/article/lottery/6a58e7d2f447e21b02db8190?url=bflc", 239),
    "金帝护卫": ("https://herymche.x6l2j-h6kfu-qdresg.work:29466/article/lottery/6a0452504ea5c20141013e9b?url=txbb", 240),
    "澳彩碼王": ("https://12388990827.794555.xyz/bbs/topic.php?id=21353", 240),
    "饱食暖衣": ("https://12388990827.794555.xyz/bbs/topic.php?id=20270", 240),
    "寻宝探码": ("https://12388990827.688756.xyz/bbs/topic.php?id=18520", 239),
    "财源滚滚": ("https://12388990827.688756.xyz/bbs/topic.php?id=19930", 239),
    "潇洒人生": ("https://0130190827.767566.xyz/bbs/topic.php?id=30780", 239),
    "夜空无痕": ("https://88888020827.897657.xyz/bbs/topic.php?id=20207", 239),
    "安身立命": ("https://88888020827.897657.xyz/bbs/topic.php?id=20215", 239),
    "海角天涯": ("https://88888020827.997595.xyz/bbs/topic.php?id=18490", 239),
}


def test_special_sites_have_single_tail_bottom_dedicated_rules() -> None:
    configured = {
        site["name"]: site
        for site in json.loads(Path("sites.json").read_text(encoding="utf-8-sig"))
    }
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
