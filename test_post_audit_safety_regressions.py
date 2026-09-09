from __future__ import annotations

import pytest

from shawei.domain.models import Record
from shawei.parsers import registry, topic
from shawei.parsers.safe_static_article import extract_safe_static_article_body_records
from shawei.parsers.safety_guards import enforce_parsed_records


def test_dedicated_multidigit_tail_cannot_be_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_parser(document: str, site_name: str, **kwargs):
        return [
            Record(
                tail=3,
                period=251,
                site_name=site_name,
                source_snippet="251期绝杀一尾[23]开猴23准",
            )
        ]

    monkeypatch.setitem(registry.SOURCE_PARSERS, "dedicated", fake_parser)
    with pytest.raises(LookupError, match="多位值"):
        registry.parse_source(
            "dedicated",
            "251期绝杀一尾[23]开猴23准",
            "审计站",
            parser_name="legacy_single_tail",
        )


def test_topic_style_multidigit_tail_is_rejected_even_for_custom_shape() -> None:
    record = Record(
        tail=3,
        period=251,
        site_name="审计站",
        source_snippet="251期笑歌戏舞 杀[23]尾 开猴23准",
    )
    with pytest.raises(LookupError, match="多位值"):
        enforce_parsed_records(
            [record],
            source="dedicated",
            parser_name="xiaoge_topic_main_tail",
            document=record.source_snippet,
            site_name="审计站",
        )


def test_all_topic_dom_text_uses_original_source_order() -> None:
    assert topic._dynamic_node_text is topic._dynamic_node_text_in_order
    parser = topic._DynamicHtmlParser()
    parser.feed(
        '<div>251期<span>绝杀一尾[5]</span>250期<span>绝杀一尾[6]</span></div>'
    )
    parser.close()
    text = topic._dynamic_node_text(parser.root.children[0])
    assert text.index("251期") < text.index("[5]") < text.index("250期") < text.index("[6]")


@pytest.mark.parametrize("foreign_field", ["推荐", "杀码", "杀头", "杀半波"])
def test_static_article_never_borrows_unknown_or_other_field_value(
    foreign_field: str,
) -> None:
    text = f"251期 审计站 绝杀一尾 {foreign_field}[5] 开猴23准"
    records = extract_safe_static_article_body_records(
        text,
        "审计站",
        ("绝杀一尾",),
        exclude_keywords=(),
        require_draw_signal=True,
        require_site_keyword=True,
    )
    assert records == []


def test_static_article_accepts_only_immediate_target_value() -> None:
    records = extract_safe_static_article_body_records(
        "251期 审计站 绝杀一尾[5] 开猴23准",
        "审计站",
        ("绝杀一尾",),
        exclude_keywords=(),
        require_draw_signal=True,
        require_site_keyword=True,
    )
    assert [(record.period, record.tail) for record in records] == [(251, 5)]


def test_generic_parser_rejects_cross_field_value(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_parser(document: str, site_name: str, **kwargs):
        return [
            Record(
                tail=5,
                period=251,
                site_name=site_name,
                source_snippet="251期绝杀一尾 推荐[5] 开猴23准",
            )
        ]

    monkeypatch.setitem(registry.SOURCE_PARSERS, "compact", fake_parser)
    with pytest.raises(LookupError, match="不直接相邻"):
        registry.parse_source(
            "compact",
            "251期绝杀一尾 推荐[5] 开猴23准",
            "审计站",
        )


def test_generic_parser_keeps_direct_single_tail_value(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = Record(
        tail=5,
        period=251,
        site_name="审计站",
        source_snippet="251期绝杀一尾[5]开猴23准",
    )

    monkeypatch.setitem(
        registry.SOURCE_PARSERS,
        "compact",
        lambda document, site_name, **kwargs: [expected],
    )
    assert registry.parse_source(
        "compact",
        expected.source_snippet,
        "审计站",
    ) == [expected]
