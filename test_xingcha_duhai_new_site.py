import pytest

from shawei.domain.models import Document, StrictRule
from shawei.parsers.dedicated import extract_dedicated_records
from shawei.validation.validator import validate_documents


URL = "https://jtrmhar.cwdc3-r5vqn-qzqasa.work:17455/topic/741190.html"
RULE = StrictRule(
    allowed_sources=("dedicated",),
    dedicated_parser="xingcha_topic_two_tail",
    chunk_keywords=("精杀二尾专区",),
    prefer_rendered=True,
    require_site_keyword=True,
    render_timeout=30,
    site_url=URL,
)


def _document(rows: str, author: str = "星槎渡海") -> Document:
    html = f"""
    <div class="container">
      <div>{author} 发表于 08月26日 15:57:28</div>
      <div class="topic-content">{rows}</div>
    </div>
    """
    return Document(URL, html, "browser")


def test_xingcha_bottom_selects_240_two_tail() -> None:
    document = _document(
        "<p>238期：精杀二尾专区◆7.8尾开17错</p>"
        "<p>239期：精杀二尾专区◆2.3尾开05准</p>"
        "<p>240期：精杀二尾专区◆4.6尾开00准</p>"
    )
    decision = validate_documents(
        [document], "星槎渡海", pick="bottom", rule=RULE, target_period=240
    )
    assert [record.value() for record in decision.records] == ["4、6"]
    with pytest.raises(LookupError, match="绝对bottom边界是240期"):
        validate_documents(
            [document], "星槎渡海", pick="bottom", rule=RULE, target_period=239
        )
    with pytest.raises(LookupError, match="绝对bottom边界是240期"):
        validate_documents(
            [document], "星槎渡海", pick="bottom", rule=RULE, target_period=241
        )


def test_xingcha_rejects_wrong_author_field_and_conflict() -> None:
    row = "<p>240期：精杀二尾专区◆4.6尾开00准</p>"
    assert extract_dedicated_records(
        _document(row, "其他作者").content,
        "星槎渡海",
        "xingcha_topic_two_tail",
        target_period=240,
        pick="bottom",
    ) == []
    assert extract_dedicated_records(
        _document(row.replace("精杀二尾专区", "绝杀三肖")).content,
        "星槎渡海",
        "xingcha_topic_two_tail",
        target_period=240,
        pick="bottom",
    ) == []
    conflict = _document(row + "<p>240期：精杀二尾专区◆1.9尾开00准</p>")
    with pytest.raises(LookupError, match="数据冲突"):
        validate_documents(
            [conflict], "星槎渡海", pick="bottom", rule=RULE, target_period=240
        )
