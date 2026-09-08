import pytest

from shawei.config.constants import TWO_TAIL_SITE_URLS
from shawei.config.rules import effective_rule_for
from shawei.parsers.dedicated import extract_dedicated_records
from shawei.persistence.cache_repository import is_valid_result_value
from shawei.validation.validator import validate_documents


SITE_NAME = "港澳彩票绝杀"
SITE_URL = "https://aa.373785d.com:1888/"
PARSER = "aa_macau_two_tail_block"


def _row(period: int, value: str, draw: str = "猴23") -> str:
    first, second = value.split("、")
    return (
        "<tr><td>"
        f"{period}期<font>绝杀二尾</font>"
        f"<font>【{first}尾{second}尾】</font>"
        f"开<font>{draw}</font>准"
        "</td></tr>"
    )


def _page() -> str:
    macau = "".join(
        _row(period, value, "？00" if period == 224 else "猴23")
        for period, value in (
            (224, "0、5"),
            (223, "0、5"),
            (221, "0、8"),
            (220, "5、6"),
            (219, "2、9"),
            (218, "1、4"),
            (217, "3、7"),
            (216, "0、4"),
        )
    )
    hong_kong = _row(224, "9、9", "？00")
    return (
        "<html><body>"
        "<div id='dxzt14'>"
        "<li id='dxzt141' class='hover'>澳门绝杀二尾</li>"
        "<li id='dxzt142'>香港绝杀二尾</li>"
        "</div>"
        "<div id='unrelated'><p>225期绝杀二尾【9尾9尾】开？00准</p></div>"
        f"<div id='con_dxzt14_1'><table><tbody>{macau}</tbody></table></div>"
        f"<div id='con_dxzt14_2'><table><tbody>{hong_kong}</tbody></table></div>"
        "</body></html>"
    )


def _rule():
    return effective_rule_for(SITE_URL, SITE_NAME)


def _records(target_period: int | None = None):
    rule = _rule()
    return extract_dedicated_records(
        _page(),
        SITE_NAME,
        rule.dedicated_parser,
        chunk_keywords=rule.chunk_keywords,
        target_period=target_period,
        pick="top",
        require_site_keyword=rule.require_site_keyword,
    )


def test_macau_site_is_url_bound_double_tail_with_dedicated_rule():
    rule = _rule()
    assert SITE_URL in TWO_TAIL_SITE_URLS
    assert rule.allowed_sources == ("dedicated",)
    assert rule.dedicated_parser == PARSER
    assert rule.chunk_keywords == ("澳门绝杀二尾",)
    assert is_valid_result_value("0、5", SITE_URL)
    assert not is_valid_result_value("0", SITE_URL)
    assert not is_valid_result_value("0、5、6", SITE_URL)


def test_parser_uses_only_the_macau_block_and_returns_history():
    records = _records(224)
    assert [(record.period, record.value()) for record in records] == [
        (224, "0、5"),
        (223, "0、5"),
        (221, "0、8"),
        (220, "5、6"),
        (219, "2、9"),
        (218, "1、4"),
        (217, "3、7"),
        (216, "0、4"),
    ]


def test_top_224_is_valid_and_225_or_223_is_out_of_boundary():
    rule = _rule()
    decision = validate_documents(
        [_page()], SITE_NAME, pick="top", rule=rule, target_period=224
    )
    assert [record.value() for record in decision.records] == ["0、5"]

    with pytest.raises(LookupError, match="绝对top边界是224期，不是指定225期"):
        validate_documents(
            [_page()], SITE_NAME, pick="top", rule=rule, target_period=225
        )
    with pytest.raises(LookupError, match="绝对top边界是224期，不是指定223期"):
        validate_documents(
            [_page()], SITE_NAME, pick="top", rule=rule, target_period=223
        )


def test_hong_kong_value_and_unrelated_225_row_cannot_override_macau_boundary():
    records = _records(224)
    assert records[0].tail_values == (0, 5)
    assert all(record.value() != "9、9" for record in records)
    assert all(record.period != 225 for record in records)
