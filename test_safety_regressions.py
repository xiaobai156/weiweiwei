from __future__ import annotations

import pytest

from shawei.fetch import document_discovery
from shawei.fetch.http_client import FETCH_CACHE_LOCK, FETCH_CHILDREN
from shawei.parsers import registry
from shawei.parsers.common import extract_table_records, extract_tail_number, extract_tail_value
from shawei.services.crawl_site import (
    _dynamic_target_blocks,
    _validate_dynamic_render_documents,
)


LIUXUAN_URL = "https://lx11.www87127b.com:8443/#87127"


def test_single_tail_parser_rejects_draw_multi_digit_and_multi_tail_values() -> None:
    assert extract_tail_number("3尾") == 3
    assert extract_tail_number("[3]") == 3
    assert extract_tail_number("23尾") is None
    assert extract_tail_number("2、3尾") is None
    assert extract_tail_number("1尾 8尾") is None
    assert extract_tail_value("251期杀掉一尾开:23准") is None
    assert extract_tail_value("251期绝杀一尾 23尾 开:01准") is None
    assert extract_tail_value("251期绝杀一尾 2、3尾 开:01准") is None
    assert extract_tail_value("251期绝杀一尾[5]开猴23准") == 5


def test_table_parser_does_not_reuse_tail_column_in_next_table() -> None:
    html = """
    <table>
      <tr><th>期数</th><th>杀一尾</th><th>开奖结果</th></tr>
      <tr><td>250期</td><td>5尾</td><td>开猴23准</td></tr>
    </table>
    <table>
      <tr><th>期数</th><th>推荐号码</th><th>开奖结果</th></tr>
      <tr><td>251期</td><td>8</td><td>开鼠01准</td></tr>
    </table>
    """
    records = extract_table_records(
        html,
        "审计站",
        table_headers=("杀一尾",),
        table_required_headers=("期数", "杀一尾", "开奖结果"),
        require_site_keyword=False,
    )
    assert [(record.period, record.tail) for record in records] == [(250, 5)]


def test_static_article_does_not_borrow_value_from_next_period() -> None:
    text = "251期 审计站 绝杀一尾[?] 250期 审计站 绝杀一尾[5] 开猴23准"
    records = registry.parse_source(
        "dedicated",
        text,
        "审计站",
        parser_name="article_static_single_tail",
        chunk_keywords=("绝杀一尾",),
        exclude_keywords=(),
        max_chunk_span=240,
        require_draw_signal=True,
        require_site_keyword=True,
        target_period=251,
        pick="top",
        anchor_span=1500,
        allow_same_period_records=False,
    )
    assert [(record.period, record.tail) for record in records] == [(250, 5)]


def test_static_article_does_not_borrow_value_from_other_field() -> None:
    text = "251期 审计站 绝杀一尾[?] 杀一头[5] 开猴23准"
    records = registry.parse_source(
        "dedicated",
        text,
        "审计站",
        parser_name="article_static_single_tail",
        chunk_keywords=("绝杀一尾",),
        exclude_keywords=(),
        max_chunk_span=240,
        require_draw_signal=True,
        require_site_keyword=True,
        target_period=251,
        pick="top",
        anchor_span=1500,
        allow_same_period_records=False,
    )
    assert records == []


def test_dynamic_render_requires_record_identity_not_navigation_href() -> None:
    html = """
    <main>
      <div class="related">
        <a href="/article/admin/abc">目标文章</a>
        <div>作者甲 251期绝杀一尾[9]开猴23准</div>
      </div>
    </main>
    """
    assert _dynamic_target_blocks(html, "abc") == []


def test_dynamic_render_preserves_dom_text_order_inside_target_record() -> None:
    html = """
    <main>
      <div data-article-id="abc">
        作者甲
        <span>251期</span><span>绝杀一尾[5]开猴23准</span>
        <span>250期</span><span>绝杀一尾[6]开鼠01准</span>
      </div>
    </main>
    """
    blocks = _dynamic_target_blocks(html, "abc")
    assert len(blocks) == 1
    block = blocks[0]
    assert block.index("251期") < block.index("[5]") < block.index("250期") < block.index("[6]")
    url = "https://example.test/article/admin/abc?url=x"
    assert _validate_dynamic_render_documents(url, [html], "作者甲") == blocks


def test_dynamic_render_plain_text_id_is_not_identity_evidence() -> None:
    url = "https://example.test/article/admin/abc?url=x"
    with pytest.raises(LookupError, match="目标记录ID abc"):
        _validate_dynamic_render_documents(
            url,
            ["abc 作者甲 251期绝杀一尾[5]开猴23准"],
            "作者甲",
        )


def test_liuxuan_registers_all_child_fetches_for_root_cache_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loader_url = "https://lx11.www87127b.com:8443/yjjy/wenzhang.js"
    detail_url = "https://lx11.www87127b.com:8443/915577.html"
    zhjs_url = "https://lx11.www87127b.com:8443/cj/zhjs.js"
    documents = {
        LIUXUAN_URL: '<script src="/yjjy/wenzhang.js"></script>',
        loader_url: "loader",
        detail_url: '<title>六玄网论坛</title><div id="zhjs"><script src="/cj/zhjs.js"></script></div>',
        zhjs_url: "澳彩六玄网[综合绝杀] 澳彩最准开奖:87127.com",
    }

    monkeypatch.setattr(document_discovery, "fetch_text", lambda url, _timeout: documents[url])
    monkeypatch.setattr(
        document_discovery,
        "decode_document_writeln_html",
        lambda text: '<iframe src="/915577.html"></iframe>' if text == "loader" else text,
    )
    with FETCH_CACHE_LOCK:
        FETCH_CHILDREN.pop(LIUXUAN_URL, None)

    result = document_discovery.collect_liuxuan_documents(LIUXUAN_URL, timeout=8)

    assert len(result) == 5
    with FETCH_CACHE_LOCK:
        assert FETCH_CHILDREN.get(LIUXUAN_URL) == {loader_url, detail_url, zhjs_url}
        FETCH_CHILDREN.pop(LIUXUAN_URL, None)
