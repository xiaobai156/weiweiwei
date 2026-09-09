from __future__ import annotations

import pytest

from shawei.domain.models import Record
from shawei.parsers import registry
from shawei.parsers.safe_table import extract_strict_table_records
from shawei.services import crawl_site


def _dedicated_record(text: str, tail: int) -> Record:
    return Record(
        tail=tail,
        period=251,
        site_name="审计站",
        source_snippet=text,
    )


def test_dedicated_long_gap_multidigit_value_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = "251期绝杀一尾◆◇〓【23】开猴23准"
    monkeypatch.setitem(
        registry.SOURCE_PARSERS,
        "dedicated",
        lambda document, site_name, **kwargs: [_dedicated_record(text, 3)],
    )
    with pytest.raises(LookupError, match="多位值"):
        registry.parse_source(
            "dedicated", text, "审计站", parser_name="lainan_yixin_parenthesized"
        )


def test_dedicated_cannot_borrow_other_field_single_digit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = "251期绝杀一尾 推荐资料【5】开猴23准"
    monkeypatch.setitem(
        registry.SOURCE_PARSERS,
        "dedicated",
        lambda document, site_name, **kwargs: [_dedicated_record(text, 5)],
    )
    with pytest.raises(LookupError, match="其他字段|说明文字"):
        registry.parse_source(
            "dedicated", text, "审计站", parser_name="lainan_yixin_parenthesized"
        )


@pytest.mark.parametrize(
    "text",
    (
        "251期绝杀一尾【2、3】开猴23准",
        "251期绝杀一尾 2,3 开猴23准",
        "251期绝杀一尾 2 3 开猴23准",
    ),
)
def test_single_tail_field_cannot_hide_second_value(
    text: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        registry.SOURCE_PARSERS,
        "dedicated",
        lambda document, site_name, **kwargs: [_dedicated_record(text, 2)],
    )
    with pytest.raises(LookupError, match="多个值"):
        registry.parse_source(
            "dedicated", text, "审计站", parser_name="topic_published_body_tail"
        )


def test_valid_tail_is_not_invalidated_by_later_other_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = "251期绝杀一尾【5】 杀码23 开猴23准"
    record = _dedicated_record(text, 5)
    monkeypatch.setitem(
        registry.SOURCE_PARSERS,
        "dedicated",
        lambda document, site_name, **kwargs: [record],
    )
    assert registry.parse_source(
        "dedicated", text, "审计站", parser_name="topic_published_body_tail"
    ) == [record]


def test_same_table_new_header_clears_previous_tail_column() -> None:
    html = """
    <table>
      <tr><th>期数</th><th>杀一尾</th><th>开奖结果</th></tr>
      <tr><td>250期</td><td>5</td><td>开猴23准</td></tr>
      <tr><th>期数</th><th>推荐号码</th><th>开奖结果</th></tr>
      <tr><td>251期</td><td>8</td><td>开鼠01准</td></tr>
    </table>
    """
    records = extract_strict_table_records(
        html,
        "审计站",
        table_headers=("杀一尾",),
        table_required_headers=("期数", "杀一尾", "开奖结果"),
        require_site_keyword=False,
    )
    assert [(record.period, record.tail) for record in records] == [(250, 5)]


def test_nested_table_has_independent_column_scope() -> None:
    html = """
    <table>
      <tr><th>期数</th><th>杀一尾</th><th>开奖结果</th></tr>
      <tr><td>250期</td><td>5</td><td>开猴23准</td></tr>
      <tr><td colspan="3">
        <table>
          <tr><th>期数</th><th>推荐号码</th><th>开奖结果</th></tr>
          <tr><td>251期</td><td>8</td><td>开鼠01准</td></tr>
        </table>
      </td></tr>
    </table>
    """
    records = extract_strict_table_records(
        html,
        "审计站",
        table_headers=("杀一尾",),
        table_required_headers=("期数", "杀一尾", "开奖结果"),
        require_site_keyword=False,
    )
    assert [(record.period, record.tail) for record in records] == [(250, 5)]


def test_dynamic_record_identity_requires_exact_attribute_value() -> None:
    assert crawl_site._attribute_matches_target("abc", "abc")
    assert not crawl_site._attribute_matches_target("related-abc", "abc")
    assert "id" in crawl_site._DYNAMIC_EXPLICIT_RECORD_ID_ATTRIBUTES

    related = """
    <main><div id="related-abc">作者甲 251期绝杀一尾[9]开猴23准</div></main>
    """
    exact = """
    <main><div id="abc">作者甲 251期绝杀一尾[9]开猴23准</div></main>
    """
    assert crawl_site._dynamic_target_blocks(related, "abc") == []
    assert crawl_site._dynamic_target_blocks(exact, "abc")
