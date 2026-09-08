import pytest

from shawei.config.rules import effective_rule_for
from shawei.domain.models import Document
from shawei.fetch.profile import _qvuu_two_tail_target_values
from shawei.parsers.dedicated import extract_dedicated_records
from shawei.validation.validator import validate_documents


SHENSHAN_URL = "https://pwqviw.1tcpi-45qgo-qddfnk.work:16677/topic/273012.html"
JIANREN_URL = "https://lxbwvnfv.3gwtt-z9y8n-wsxdfy.xyz:16677/topic/458345.html"
HENGDAO_URL = "https://kpfhptru.s8hvq-ssvup-eladiw.xyz:16622/topic/223705.html"
WEIYI_PARSER = "qvuu_weiyi_huoshi_two_tail"
KAIJIANG_URL = "https://156.225.88.144:12098/#234432"
WANXIANG_URL = "https://mm.676626m.com:1888/bbs/8023"
RENZENG_URL = "https://mm.676626m.com:1888/bbs/8030"
NALAWANZHI_URL = "https://sfch0f.ky3r5-0b4c9-yudwqy.work/topic/240474.html"
SAODI_URL = "https://rh2fgz.a96ub-s6g0d-mfbdwp.work/topic/225941.html"


def test_shenshan_uses_only_the_published_topic_body_parser() -> None:
    rule = effective_rule_for(SHENSHAN_URL, "深山穷林")

    assert rule.allowed_sources == ("dedicated",)
    assert rule.dedicated_parser == "topic_published_body_tail"


def test_saodi_topic_has_extended_render_timeout() -> None:
    rule = effective_rule_for(SAODI_URL, "扫地焚香")

    assert rule.render_timeout == 30


def test_jianren_prefers_rendered_body_text() -> None:
    rule = effective_rule_for(JIANREN_URL, "坚韧不拔")

    assert rule.allowed_sources == ("dedicated",)
    assert rule.dedicated_parser == "jianren_topic_main_tail"
    assert rule.prefer_rendered_body_text is True


def test_nalawanzhi_bottom_uses_the_last_contiguous_history_block() -> None:
    rows = "\n".join(
        f"{period}期绝杀一尾《{top}》开狗08准"
        for period, top in zip(range(243, 214, -1), [7] * 29)
    )
    bottom_rows = "\n".join(
        f"{period}期绝杀一尾《{tail}》开狗08准"
        for period, tail in zip(range(215, 244), [3] * 29)
    )
    decision = validate_documents(
        [Document(NALAWANZHI_URL, rows + "\n" + bottom_rows, "browser")],
        "纳喇满职",
        pick="bottom",
        rule=effective_rule_for(NALAWANZHI_URL, "纳喇满职"),
        target_period=243,
    )

    assert [record.as_line() for record in decision.records] == ["3尾 纳喇满职"]


def test_hengdao_scopes_top_to_the_rendered_lead_block() -> None:
    rule = effective_rule_for(HENGDAO_URL, "横刀跃马")

    assert rule.allowed_sources == ("lead_compact",)
    assert rule.prefer_rendered_body_text is True
    assert rule.direction_document_scope == "top"
    assert rule.lead_span == 900


def _hengdao_documents() -> list[Document]:
    main_body = (
        "234期:澳彩横刀跃马(绝杀一尾)→站长推荐\n"
        "234期绝杀一尾《0》开0000准\n"
        "233期绝杀一尾《7》开鼠07错\n"
        + "广告" * 500
        + "\n243期绝杀一尾《9》开狗08准\n"
        + "234期绝杀一尾《6》开蛇13准"
    )
    decoded_fragment = (
        "243期绝杀一尾《9》开狗08准\n"
        "242期绝杀一尾《6》开猴34准\n"
        "234期绝杀一尾《6》开蛇13准"
    )
    return [
        Document(HENGDAO_URL, main_body, "browser", order=0),
        Document(HENGDAO_URL, decoded_fragment, "page", order=1),
    ]


def test_hengdao_top_234_uses_only_the_authoritative_lead_row() -> None:
    decision = validate_documents(
        _hengdao_documents(),
        "横刀跃马",
        pick="top",
        rule=effective_rule_for(HENGDAO_URL, "横刀跃马"),
        target_period=234,
    )

    assert [record.as_line() for record in decision.records] == ["0尾 横刀跃马"]


@pytest.mark.parametrize(
    ("pick", "period", "boundary"),
    [("top", 233, "绝对top边界是234期"), ("bottom", 234, "绝对bottom边界是233期")],
)
def test_hengdao_rejects_wrong_period_or_direction(
    pick: str, period: int, boundary: str
) -> None:
    with pytest.raises(LookupError, match=boundary):
        validate_documents(
            _hengdao_documents(),
            "横刀跃马",
            pick=pick,
            rule=effective_rule_for(HENGDAO_URL, "横刀跃马"),
            target_period=period,
        )


def test_hengdao_rejects_wrong_field() -> None:
    decision = validate_documents(
        [Document(HENGDAO_URL, "234期绝杀六肖《0》开0000准", "browser", order=0)],
        "横刀跃马",
        pick="top",
        rule=effective_rule_for(HENGDAO_URL, "横刀跃马"),
        target_period=234,
    )

    assert decision.records == ()


def test_weiyi_huoshi_top_uses_current_cycle_first_period_row() -> None:
    document = (
        "238期:[精杀二尾]◆6.7尾开00准 "
        "237期:[精杀二尾]◆1.0尾开羊12准 "
        "238期:[精杀二尾]◆7.8尾开猴46准"
    )

    assert _qvuu_two_tail_target_values(document, WEIYI_PARSER, 238) == (6, 7)


def test_weiyi_huoshi_invalid_first_period_row_does_not_fall_back() -> None:
    document = (
        "238期:[精杀二尾]◆?.?尾开00准 "
        "237期:[精杀二尾]◆1.0尾开羊12准 "
        "238期:[精杀二尾]◆7.8尾开猴46准"
    )

    with pytest.raises(LookupError, match="没有找到238期有效二尾数据"):
        _qvuu_two_tail_target_values(document, WEIYI_PARSER, 238)


def test_weiyi_huoshi_rejects_unknown_parser() -> None:
    with pytest.raises(LookupError, match="未知Qvuu二尾格式解析器"):
        _qvuu_two_tail_target_values("238期:[精杀二尾]◆6.7尾", "unknown", 238)


def test_weiyi_huoshi_rejects_missing_target_period() -> None:
    with pytest.raises(LookupError, match="没有找到238期有效二尾数据"):
        _qvuu_two_tail_target_values(
            "237期:[精杀二尾]◆1.0尾开羊12准", WEIYI_PARSER, 238
        )


def _kaijiang_pending_document() -> Document:
    table = """
    <div id="yxym">
      <div class="list-title">开奖发财【综合杀料】11447.COM</div>
      <table>
        <tr><td>期数</td><td>杀尾</td><td>杀肖</td><td>杀合</td><td>杀波</td><td>开奖</td></tr>
        <tr><td>237期</td><td>3尾</td><td>鼠</td><td>1</td><td>红</td><td>开:羊12</td></tr>
        <tr><td>238期</td><td>?尾</td><td>?</td><td>?</td><td>?</td><td>开:赚99</td></tr>
      </table>
    </div>
    """
    return Document(KAIJIANG_URL, table, "browser")


@pytest.mark.parametrize(
    "document",
    [
        "<html><table><tr><td>238期</td><td>3尾</td></tr></table></html>",
        """
        <div id="yxym">
          <div class="list-title">开奖发财【综合杀料】11447.COM</div>
          <table><tr><td>期数</td><td>错误字段</td></tr></table>
        </div>
        """,
    ],
)
def test_kaijiang_requires_exact_target_table_and_headers(document: str) -> None:
    assert (
        extract_dedicated_records(
            document,
            "开奖发财",
            "kaijiangfacai_combined_kill_table",
            target_period=238,
            pick="bottom",
        )
        == []
    )


def test_kaijiang_pending_238_is_not_a_published_bottom_record() -> None:
    with pytest.raises(LookupError, match="绝对bottom边界是237期，不是指定238期"):
        validate_documents(
            [_kaijiang_pending_document()],
            "开奖发财",
            pick="bottom",
            rule=effective_rule_for(KAIJIANG_URL, "开奖发财"),
            target_period=238,
        )


def test_kaijiang_pending_238_does_not_block_published_237_bottom() -> None:
    decision = validate_documents(
        [_kaijiang_pending_document()],
        "开奖发财",
        pick="bottom",
        rule=effective_rule_for(KAIJIANG_URL, "开奖发财"),
        target_period=237,
    )

    assert [record.value() for record in decision.records] == ["3"]


def test_kaijiang_other_invalid_tail_still_blocks_bottom() -> None:
    pending = _kaijiang_pending_document()
    invalid = Document(
        pending.source_url,
        pending.content.replace("<td>?尾</td>", "<td>错尾</td>"),
        pending.source_type,
    )

    with pytest.raises(LookupError, match="绝对bottom边界是238期，不是指定237期"):
        validate_documents(
            [invalid],
            "开奖发财",
            pick="bottom",
            rule=effective_rule_for(KAIJIANG_URL, "开奖发财"),
            target_period=237,
        )


@pytest.mark.parametrize("url", [WANXIANG_URL, RENZENG_URL])
def test_slow_mm_browser_sites_have_thirty_second_timeout(url: str) -> None:
    rule = effective_rule_for(url, "万象回春" if url == WANXIANG_URL else "人增寿算")

    assert rule.prefer_rendered is True
    assert rule.render_timeout == 30


def test_kaijiang_uses_rendered_table_instead_of_stale_http() -> None:
    rule = effective_rule_for(KAIJIANG_URL, "开奖发财")

    assert rule.prefer_rendered is True
    assert rule.render_timeout == 20
