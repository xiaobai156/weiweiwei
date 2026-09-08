from __future__ import annotations

import pytest

from shawei.domain.models import Document, Record, StrictRule
from shawei.parsers import registry
from shawei.validation.validator import validate_documents


AUTHORIZED_TWO_TAIL_URL = (
    "https://qvuuqqs.8imf7-hteuh-ylwuqv.xyz/#/users/1203"
)
UNAUTHORIZED_TWO_TAIL_URL = "https://unapproved.example/two-tail"


def _qvuu_two_tail_text() -> str:
    return "123期精杀二尾专区 1.2尾开猴23准"


def _special_single_tail_rule(**overrides) -> StrictRule:
    values = {
        "allowed_sources": ("dedicated",),
        "dedicated_parser": "topic_body_single_tail",
        "chunk_keywords": ("精准杀尾",),
        "require_site_keyword": True,
    }
    values.update(overrides)
    return StrictRule(**values)


def _special_single_tail_text(*rows: str) -> str:
    return " ".join(
        (
            "224期:审计站[精准杀尾]站长推荐 作者:审计站",
            *rows,
        )
    )


def test_two_tail_validation_uses_document_url_not_site_name() -> None:
    rule = StrictRule(
        allowed_sources=("dedicated",),
        dedicated_parser="qvuu_qiangli_zhaopai_two_tail",
        chunk_keywords=("二尾",),
        require_site_keyword=False,
    )

    with pytest.raises(LookupError, match="双尾授权URL"):
        validate_documents(
            [
                Document(
                    UNAUTHORIZED_TWO_TAIL_URL,
                    _qvuu_two_tail_text(),
                    "page",
                )
            ],
            "强烈招牌",
            rule=rule,
            target_period=123,
        )

    decision = validate_documents(
        [
            Document(
                AUTHORIZED_TWO_TAIL_URL,
                _qvuu_two_tail_text(),
                "page",
            )
        ],
        "非授权站名",
        rule=rule,
    )
    assert [record.value() for record in decision.records] == ["1、2"]


def test_authorized_two_tail_url_rejects_single_tail_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        registry,
        "parse_source",
        lambda source, document, site_name, **kwargs: [
            Record(tail=7, period=123, site_name=site_name)
        ],
    )
    rule = StrictRule(allowed_sources=("dedicated",), site_url=AUTHORIZED_TWO_TAIL_URL)

    with pytest.raises(LookupError, match="必须是两个0-9尾数"):
        validate_documents(
            [Document(AUTHORIZED_TWO_TAIL_URL, "ignored", "page")],
            "强烈招牌",
            rule=rule,
            target_period=123,
        )


def test_effective_rule_rejects_a_document_from_another_url() -> None:
    from shawei.config.rules import effective_rule_for

    rule = effective_rule_for(AUTHORIZED_TWO_TAIL_URL, "强烈招牌")
    with pytest.raises(LookupError, match="URL"):
        validate_documents(
            [
                Document(
                    UNAUTHORIZED_TWO_TAIL_URL,
                    _qvuu_two_tail_text(),
                    "page",
                )
            ],
            "强烈招牌",
            rule=rule,
            target_period=123,
        )


def test_placeholder_at_absolute_boundary_keeps_prediction_value() -> None:
    text = _special_single_tail_text(
        "224期:[精准杀尾][5]开0000准",
        "223期:[精准杀尾][6]开猴23准",
    )

    decision = validate_documents(
        [Document("https://audit.example/topic/1", text, "page")],
        "审计站",
        pick="top",
        rule=_special_single_tail_rule(),
        target_period=224,
    )
    assert [record.value() for record in decision.records] == ["5"]


@pytest.mark.parametrize(("pick", "expected"), [("top", "5"), ("bottom", "6")])
def test_same_authority_same_period_values_are_selected_by_direction(
    pick: str,
    expected: str,
) -> None:
    text = _special_single_tail_text(
        "224期:[精准杀尾][5]开猴23准",
        "224期:[精准杀尾][6]开猴23准",
    )

    decision = validate_documents(
        [Document("https://audit.example/topic/2", text, "page")],
        "审计站",
        pick=pick,
        rule=_special_single_tail_rule(),
        target_period=224,
    )

    assert [record.value() for record in decision.records] == [expected]


def test_dedicated_parser_failure_does_not_fall_back_to_generic_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_parse_source(source: str, document: str, site_name: str, **kwargs):
        calls.append(source)
        if source == "compact":
            return [Record(tail=7, period=1, site_name=site_name)]
        return []

    monkeypatch.setattr(registry, "parse_source", fake_parse_source)
    rule = StrictRule(
        allowed_sources=("dedicated", "compact"),
        dedicated_parser="missing_dedicated_parser",
    )

    decision = validate_documents(
        [Document("https://audit.example/topic/3", "ignored", "page")],
        "审计站",
        rule=rule,
        target_period=1,
    )

    assert calls == ["dedicated"]
    assert decision.records == ()


def test_same_period_records_with_different_article_ids_remain_distinct() -> None:
    text = _special_single_tail_text("224期:[精准杀尾][5]开猴23准")
    rule = _special_single_tail_rule(same_period_record_selection=True)
    decision = validate_documents(
        [
            Document(
                "https://audit.example/topic/4",
                text,
                "page",
                record_id="article-a",
                document_id="document-a",
            ),
            Document(
                "https://audit.example/topic/4",
                text,
                "page",
                record_id="article-b",
                document_id="document-b",
            ),
        ],
        "审计站",
        pick="bottom",
        rule=rule,
        target_period=224,
    )

    assert [record.value() for record in decision.records] == ["5"]
    assert decision.records[0].same_period_record_index == 2
    assert decision.records[0].same_period_record_count == 2


def test_unrelated_document_order_cannot_define_target_top_boundary() -> None:
    unrelated = _special_single_tail_text(
        "210期:[精准杀尾][1]开猴23准"
    )
    target = _special_single_tail_text(
        "224期:[精准杀尾][5]开猴23准",
        "223期:[精准杀尾][6]开猴23准",
    )

    decision = validate_documents(
        [
            Document(
                "https://audit.example/secondary",
                unrelated,
                "page",
                document_id="secondary",
                order=0,
            ),
            Document(
                "https://audit.example/authoritative",
                target,
                "page",
                document_id="authoritative",
                order=1,
            ),
        ],
        "审计站",
        pick="top",
        rule=_special_single_tail_rule(),
        target_period=224,
    )

    assert [record.value() for record in decision.records] == ["5"]


def test_unrelated_document_order_cannot_define_target_bottom_boundary() -> None:
    target = _special_single_tail_text(
        "223期:[精准杀尾][6]开猴23准",
        "224期:[精准杀尾][5]开猴23准",
    )
    unrelated = _special_single_tail_text(
        "210期:[精准杀尾][1]开猴23准"
    )

    decision = validate_documents(
        [
            Document(
                "https://audit.example/authoritative",
                target,
                "page",
                document_id="authoritative",
                order=0,
            ),
            Document(
                "https://audit.example/secondary",
                unrelated,
                "page",
                document_id="secondary",
                order=1,
            ),
        ],
        "审计站",
        pick="bottom",
        rule=_special_single_tail_rule(),
        target_period=224,
    )

    assert [record.value() for record in decision.records] == ["5"]
