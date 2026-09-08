from __future__ import annotations

from argparse import Namespace
from types import SimpleNamespace

from shawei.cli.daily import _write_outputs
from shawei.persistence.txt_writer import format_ranking
from shawei.persistence.txt_writer import format_single_period_success


def test_single_period_success_output_has_only_real_results_before_ranking() -> None:
    output = format_single_period_success(["1尾 示例站"], ["1"])

    assert output == [
        "1尾 示例站",
        "",
        "内容    次数    排名",
        "1尾     1       1",
    ]


def test_single_period_writer_does_not_put_hualin_in_success_txt(tmp_path) -> None:
    success_path = tmp_path / "227期-尾.txt"
    failure_path = tmp_path / "227期-尾-失败.txt"
    args = Namespace(success=str(success_path), fail=str(failure_path))
    result = SimpleNamespace(
        success_line="1尾 示例站",
        ranking_value="1",
        fail_line=None,
    )

    _write_outputs(227, args, [result])

    assert success_path.read_text(encoding="utf-8-sig").splitlines() == [
        "1尾 示例站",
        "",
        "内容    次数    排名",
        "1尾     1       1",
    ]
    assert not failure_path.exists()


def test_existing_ranking_formatter_does_not_add_hualin() -> None:
    assert format_ranking(["1尾 示例站"], ["1"]) == [
        "1尾 示例站",
        "",
        "内容    次数    排名",
        "1尾     1       1",
    ]


def test_ranking_uses_dense_rank_for_equal_counts() -> None:
    output = format_ranking([], ["1", "1", "2", "2", "3"])

    assert output == [
        "",
        "内容    次数    排名",
        "1尾     2       1",
        "2尾     2       1",
        "3尾     1       2",
    ]
