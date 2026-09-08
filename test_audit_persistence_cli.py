from __future__ import annotations

import json
import hashlib
import threading
from argparse import Namespace
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from shawei.domain.models import CurrentRunResult, SiteConfig, StrictRule
from shawei.persistence import cache_repository
from shawei.persistence import health_repository
from shawei.persistence.atomic_file import atomic_write_text, file_lock
from shawei.persistence import txt_writer
from shawei.cli import daily
from shawei.services import batch_crawl
from shawei.services import duplicate_check
from shawei.services import consecutive_duplicates
from shawei.services import multi_period


@pytest.fixture(autouse=True)
def _stub_effective_rules_for_isolated_cache_fixtures(monkeypatch) -> None:
    monkeypatch.setattr(
        cache_repository,
        "effective_rule_for",
        lambda _url, _name: StrictRule(),
        raising=False,
    )


def _with_fingerprint(payload: dict, sites) -> dict:
    payload["config_fingerprint"] = cache_repository.configuration_fingerprint(sites)
    return payload


def test_outgoing_failed_period_is_dropped_during_normal_window_roll() -> None:
    state = cache_repository._valid_old_failure_state(
        {
            "failed_periods": [227],
            "failure_reasons": {"227": "旧窗口失败"},
        },
        list(range(237, 227, -1)),
    )

    assert state == ([], {})


def test_cache_identity_rejects_missing_fields_and_invalid_direction() -> None:
    assert cache_repository._cache_identity("", "https://identity.example", "top") is None
    assert (
        cache_repository._cache_identity(
            "方向错误站", "https://identity.example", "sideways"
        )
        is None
    )


@pytest.mark.parametrize(
    "item",
    [
        None,
        {"periods": "200", "values": ["1"]},
        {"periods": [200], "values": []},
        {"periods": ["错误期数"], "values": ["1"]},
        {"periods": [200], "values": ["错误尾数"]},
    ],
)
def test_old_cache_value_reader_rejects_malformed_vectors(item) -> None:
    assert (
        cache_repository._valid_old_values(
            item, "https://malformed-vector.example", [200]
        )
        is None
    )


@pytest.mark.parametrize("mutation", ["failure_reasons_only", "period_order"])
def test_admission_reader_rejects_structurally_invalid_site_vectors(
    tmp_path, monkeypatch, mutation: str
) -> None:
    period = 236
    site = duplicate_check.Site(
        "结构校验站", "https://cache-structure.example/list", "top"
    )
    periods = list(range(period, period - 10, -1))
    item = {
        "name": site.name,
        "url": site.url,
        "pick": site.pick,
        "periods": periods,
        "values": ["1"] * 10,
    }
    if mutation == "failure_reasons_only":
        item["failure_reasons"] = {str(period): "缺少 failed_periods"}
    else:
        item["periods"] = list(reversed(periods))
    payload = _with_fingerprint(
        {
            "schema": 2,
            "period": period,
            "window": 10,
            "site_count": 1,
            "vector_count": 1,
            "fail_count": 0,
            "fail_lines": [],
            "sites": [item],
        },
        [site],
    )
    path = tmp_path / "recent_10_cache.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(duplicate_check, "configured_sites", lambda: [site])

    with pytest.raises(LookupError, match="缓存"):
        duplicate_check.load_recent_cache_vectors(path, allow_incomplete=True)


def test_cache_roll_keeps_same_url_histories_separate_by_identity(tmp_path) -> None:
    cache_path = tmp_path / "recent_10_cache.json"
    url = "https://same-url.example/list"
    sites = [
        SimpleNamespace(name="大江东", url=url, pick="top"),
        SimpleNamespace(name="杀庄小子", url=url, pick="bottom"),
        SimpleNamespace(name="想次方", url=url, pick="top"),
    ]
    cache_path.write_text(
        json.dumps(
            _with_fingerprint({
                "schema": 2,
                "period": 200,
                "window": 10,
                "site_count": 3,
                "vector_count": 3,
                "fail_count": 0,
                "fail_lines": [],
                "sites": [
                    {
                        "name": "大江东",
                        "url": url,
                        "pick": "top",
                        "periods": list(range(200, 190, -1)),
                        "values": ["1"] * 10,
                    },
                    {
                        "name": "杀庄小子",
                        "url": url,
                        "pick": "bottom",
                        "periods": list(range(200, 190, -1)),
                        "values": ["2"] * 10,
                    },
                    {
                        "name": "想次方",
                        "url": url,
                        "pick": "top",
                        "periods": list(range(200, 190, -1)),
                        "values": ["3"] * 10,
                    },
                ],
            }, sites),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    results = cast(list[CurrentRunResult], [
        SimpleNamespace(index=1, success_line="4尾 大江东", ranking_value="4", fail_line=None),
        SimpleNamespace(index=2, success_line="5尾 杀庄小子", ranking_value="5", fail_line=None),
        SimpleNamespace(index=3, success_line="6尾 想次方", ranking_value="6", fail_line=None),
    ])

    assert cache_repository.update_recent_cache_from_current_results(
        cache_path, 201, sites, results
    ) is True

    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload["config_fingerprint"] == cache_repository.configuration_fingerprint(sites)
    by_identity = {
        (item["name"], item["url"], item["pick"]): item for item in payload["sites"]
    }
    assert by_identity[("大江东", url, "top")]["values"][:2] == ["4", "1"]
    assert by_identity[("杀庄小子", url, "bottom")]["values"][:2] == ["5", "2"]
    assert by_identity[("想次方", url, "top")]["values"][:2] == ["6", "3"]


@pytest.mark.parametrize("indexes", [(1, 1), (1, 2), (0,)])
def test_cache_roll_rejects_duplicate_or_out_of_range_result_indexes(
    tmp_path, indexes: tuple[int, ...]
) -> None:
    period = 200
    site = SimpleNamespace(
        name="结果索引站", url="https://result-index.example/list", pick="top"
    )
    payload = _with_fingerprint(
        {
            "schema": 2,
            "period": period,
            "window": 10,
            "site_count": 1,
            "vector_count": 1,
            "fail_count": 0,
            "fail_lines": [],
            "sites": [
                {
                    "name": site.name,
                    "url": site.url,
                    "pick": site.pick,
                    "periods": list(range(period, period - 10, -1)),
                    "values": ["1"] * 10,
                }
            ],
        },
        [site],
    )
    path = tmp_path / "recent_10_cache.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    results = cast(list[CurrentRunResult], [
        SimpleNamespace(
            index=index,
            success_line=f"{value}尾 结果索引站",
            ranking_value=str(value),
            fail_line=None,
        )
        for value, index in enumerate(indexes, start=2)
    ])
    before = path.read_bytes()

    assert (
        cache_repository.update_recent_cache_from_current_results(
            path, period + 1, [site], results
        )
        is False
    )
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    ("success_line", "ranking_value", "fail_line"),
    [
        ("2尾 其他站", "2", None),
        ("3尾 结果一致站", "2", None),
        ("2尾 结果一致站", "2", "失败 结果一致站 原因: 矛盾"),
        (None, "2", None),
        (None, None, None),
    ],
)
def test_cache_roll_rejects_internally_inconsistent_current_result(
    tmp_path, success_line: str | None, ranking_value: str | None, fail_line: str | None
) -> None:
    period = 200
    site = SimpleNamespace(
        name="结果一致站", url="https://result-contract.example/list", pick="top"
    )
    payload = _with_fingerprint(
        {
            "schema": 2,
            "period": period,
            "window": 10,
            "site_count": 1,
            "vector_count": 1,
            "fail_count": 0,
            "fail_lines": [],
            "sites": [
                {
                    "name": site.name,
                    "url": site.url,
                    "pick": site.pick,
                    "periods": list(range(period, period - 10, -1)),
                    "values": ["1"] * 10,
                }
            ],
        },
        [site],
    )
    path = tmp_path / "recent_10_cache.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = cast(CurrentRunResult, SimpleNamespace(
        index=1,
        success_line=success_line,
        ranking_value=ranking_value,
        fail_line=fail_line,
    ))
    before = path.read_bytes()

    assert (
        cache_repository.update_recent_cache_from_current_results(
            path, period + 1, [site], [result]
        )
        is False
    )
    assert path.read_bytes() == before


def test_cache_roll_accepts_the_formal_two_tail_success_line(tmp_path) -> None:
    period = 200
    url = next(iter(cache_repository.TWO_TAIL_SITE_URLS))
    site = SimpleNamespace(name="双尾结果站", url=url, pick="top")
    payload = _with_fingerprint(
        {
            "schema": 2,
            "period": period,
            "window": 10,
            "site_count": 1,
            "vector_count": 1,
            "fail_count": 0,
            "fail_lines": [],
            "sites": [
                {
                    "name": site.name,
                    "url": site.url,
                    "pick": site.pick,
                    "periods": list(range(period, period - 10, -1)),
                    "values": ["0、5"] * 10,
                }
            ],
        },
        [site],
    )
    path = tmp_path / "recent_10_cache.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = cast(CurrentRunResult, SimpleNamespace(
        index=1,
        success_line="1尾 2尾 双尾结果站",
        ranking_value="1、2",
        fail_line=None,
    ))

    assert cache_repository.update_recent_cache_from_current_results(
        path, period + 1, [site], [result]
    )
    updated = json.loads(path.read_text(encoding="utf-8"))
    assert updated["sites"][0]["values"][:2] == ["1、2", "0、5"]


@pytest.mark.parametrize(
    ("periods", "values"),
    [
        ([200, 199], ["1"]),
        ([200, 200, 199], ["1", "2", "3"]),
        ([200, 199], ["10", "2"]),
        ([199, 200], ["1", "2"]),
    ],
)
def test_cache_roll_does_not_promote_corrupt_old_vectors(
    tmp_path, periods: list[int], values: list[str]
) -> None:
    cache_path = tmp_path / "recent_10_cache.json"
    url = "https://corrupt-old-vector.example/list"
    site = SimpleNamespace(name="旧向量站", url=url, pick="top")
    cache_path.write_text(
        json.dumps(
            _with_fingerprint({
                "schema": 2,
                "period": 200,
                "window": 3,
                "site_count": 1,
                "vector_count": 1,
                "fail_count": 0,
                "fail_lines": [],
                "sites": [
                    {
                        "name": site.name,
                        "url": url,
                        "pick": "top",
                        "periods": periods,
                        "values": values,
                    }
                ],
            }, [site]),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    result = cast(CurrentRunResult, SimpleNamespace(
        index=1,
        success_line="4尾 旧向量站",
        ranking_value="4",
        fail_line=None,
    ))

    before = cache_path.read_bytes()
    assert cache_repository.update_recent_cache_from_current_results(
        cache_path, 201, [site], [result]
    ) is False
    assert cache_path.read_bytes() == before


def test_atomic_writer_serializes_writers_for_one_path(tmp_path) -> None:
    path = tmp_path / "artifact.txt"
    finished = threading.Event()

    def write() -> None:
        atomic_write_text(path, "new")
        finished.set()

    with file_lock(path):
        thread = threading.Thread(target=write)
        thread.start()
        assert not finished.wait(0.1)

    thread.join(timeout=2)
    assert finished.is_set()
    assert path.read_text(encoding="utf-8") == "new"


def test_file_lock_does_not_create_sidecar_file(tmp_path) -> None:
    path = tmp_path / "artifact.txt"

    with file_lock(path):
        assert not list(tmp_path.glob("*.lock"))

    atomic_write_text(path, "content")
    assert not list(tmp_path.glob("*.lock"))


def test_duplicate_report_does_not_write_realtime_health(tmp_path, monkeypatch) -> None:
    period = 201
    window = 10
    site = consecutive_duplicates.Site(
        "缓存站", "https://cached-report.example/list", "top"
    )
    cache_path = tmp_path / "recent_10_cache.json"
    cache_path.write_text(
        json.dumps(
            _with_fingerprint({
                "schema": 2,
                "period": period,
                "window": window,
                "site_count": 1,
                "vector_count": 1,
                "fail_count": 0,
                "fail_lines": [],
                "sites": [
                    {
                        "name": site.name,
                        "url": site.url,
                        "pick": site.pick,
                        "periods": list(range(period, period - window, -1)),
                        "values": [str(value % 10) for value in range(window)],
                        "extended": 0,
                    }
                ],
            }, [site])
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(consecutive_duplicates, "configured_sites", lambda: [site])
    monkeypatch.setattr(
        consecutive_duplicates,
        "update_site_health",
        lambda *args, **kwargs: pytest.fail("cache-only duplicate report must not update health"),
        raising=False,
    )

    assert consecutive_duplicates.run(
        period=period,
        recent_cache=str(cache_path),
        output=str(tmp_path / "duplicates.txt"),
    ) == 0


def test_duplicate_loader_rejects_site_failure_state_even_with_clean_totals(tmp_path) -> None:
    period = 201
    window = 3
    site = consecutive_duplicates.Site(
        "失败状态站", "https://failed-state.example/list", "top"
    )
    cache_path = tmp_path / "recent_10_cache.json"
    cache_path.write_text(
        json.dumps(
            {
                "schema": 2,
                "period": period,
                "window": window,
                "site_count": 1,
                "vector_count": 1,
                "fail_count": 0,
                "fail_lines": [],
                "sites": [
                    {
                        "name": site.name,
                        "url": site.url,
                        "pick": site.pick,
                        "periods": [period, period - 1, period - 2],
                        "values": ["1", "2", "3"],
                        "failed_periods": [period - 1],
                        "failure_reasons": {str(period - 1): "旧期失败"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert consecutive_duplicates.load_recent_cache(
        cache_path, period, window, [site]
    ) == []


def test_duplicate_loader_rejects_cache_periods_in_wrong_order(tmp_path) -> None:
    period = 201
    window = 3
    site = consecutive_duplicates.Site(
        "乱序站", "https://out-of-order.example/list", "top"
    )
    cache_path = tmp_path / "recent_10_cache.json"
    cache_path.write_text(
        json.dumps(
            {
                "schema": 2,
                "period": period,
                "window": window,
                "site_count": 1,
                "vector_count": 1,
                "fail_count": 0,
                "fail_lines": [],
                "sites": [
                    {
                        "name": site.name,
                        "url": site.url,
                        "pick": site.pick,
                        "periods": [period - 2, period - 1, period],
                        "values": ["1", "2", "3"],
                        "extended": 0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert consecutive_duplicates.load_recent_cache(
        cache_path, period, window, [site]
    ) == []


def test_cache_roll_does_not_promote_failed_period_without_reason(tmp_path) -> None:
    period = 201
    url = "https://failed-history.example/list"
    site = SimpleNamespace(name="失败历史站", url=url, pick="top")
    cache_path = tmp_path / "recent_10_cache.json"
    cache_path.write_text(
        json.dumps(
            _with_fingerprint({
                "schema": 2,
                "period": period - 1,
                "window": 3,
                "site_count": 1,
                "vector_count": 1,
                "fail_count": 0,
                "fail_lines": [],
                "sites": [
                    {
                        "name": site.name,
                        "url": url,
                        "pick": "top",
                        "periods": [200, 199],
                        "values": ["1", "2"],
                        "failed_periods": [199],
                    }
                ],
            }, [site])
        ),
        encoding="utf-8",
    )
    result = cast(CurrentRunResult, SimpleNamespace(
        index=1,
        success_line="4尾 失败历史站",
        ranking_value="4",
        fail_line=None,
    ))

    before = cache_path.read_bytes()
    assert cache_repository.update_recent_cache_from_current_results(
        cache_path, period, [site], [result]
    ) is False
    assert cache_path.read_bytes() == before


def test_cache_roll_does_not_promote_invalid_failed_period_state(tmp_path) -> None:
    period = 201
    url = "https://invalid-failure-state.example/list"
    site = SimpleNamespace(name="非法失败状态站", url=url, pick="top")
    path = tmp_path / "recent_10_cache.json"
    path.write_text(
        json.dumps(
            _with_fingerprint(
                {
                    "schema": 2,
                    "period": period - 1,
                    "window": 3,
                    "site_count": 1,
                    "vector_count": 1,
                    "fail_count": 0,
                    "fail_lines": [],
                    "sites": [
                        {
                            "name": site.name,
                            "url": url,
                            "pick": "top",
                            "periods": [200, 199],
                            "values": ["1", "2"],
                            "failed_periods": [-1],
                        }
                    ],
                },
                [site],
            )
        ),
        encoding="utf-8",
    )
    result = cast(CurrentRunResult, SimpleNamespace(
        index=1,
        success_line="4尾 非法失败状态站",
        ranking_value="4",
        fail_line=None,
    ))

    before = path.read_bytes()
    assert cache_repository.update_recent_cache_from_current_results(
        path, period, [site], [result]
    ) is False
    assert path.read_bytes() == before


def test_cache_roll_preserves_archived_same_url_different_identity(tmp_path) -> None:
    url = "https://same-url-with-archive.example/list"
    site = SimpleNamespace(name="活跃站", url=url, pick="top")
    cache_path = tmp_path / "recent_10_cache.json"
    archived = {
        "name": "归档站",
        "url": url,
        "pick": "bottom",
        "periods": [200],
        "values": ["9"],
        "archived": True,
    }
    cache_path.write_text(
        json.dumps(
            _with_fingerprint({
                "schema": 2,
                "period": 200,
                "window": 10,
                "site_count": 1,
                "vector_count": 1,
                "fail_count": 0,
                "fail_lines": [],
                "sites": [
                    {
                        "name": site.name,
                        "url": url,
                        "pick": "top",
                        "periods": list(range(200, 190, -1)),
                        "values": ["1"] * 10,
                    },
                    archived,
                ],
            }, [site]),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    result = cast(CurrentRunResult, SimpleNamespace(
        index=1,
        success_line="4尾 活跃站",
        ranking_value="4",
        fail_line=None,
    ))

    assert cache_repository.update_recent_cache_from_current_results(
        cache_path, 201, [site], [result]
    ) is True

    items = json.loads(cache_path.read_text(encoding="utf-8"))["sites"]
    assert {item["name"] for item in items} == {"活跃站", "归档站"}
    assert next(item for item in items if item["name"] == "归档站") == archived


def test_cache_roll_rejects_non_ten_period_window(tmp_path) -> None:
    site = SimpleNamespace(
        name="错误窗口站",
        url="https://wrong-window.example/list",
        pick="top",
    )
    path = tmp_path / "recent_10_cache.json"
    path.write_text(
        json.dumps(
            _with_fingerprint(
                {
                    "schema": 2,
                    "period": 200,
                    "window": 2,
                    "site_count": 1,
                    "vector_count": 1,
                    "fail_count": 0,
                    "fail_lines": [],
                    "sites": [
                        {
                            "name": site.name,
                            "url": site.url,
                            "pick": site.pick,
                            "periods": [200, 199],
                            "values": ["1", "2"],
                        }
                    ],
                },
                [site],
            )
        ),
        encoding="utf-8",
    )
    result = cast(CurrentRunResult, SimpleNamespace(
        index=1,
        success_line="3尾 错误窗口站",
        ranking_value="3",
        fail_line=None,
    ))

    before = path.read_bytes()
    assert cache_repository.update_recent_cache_from_current_results(
        path, 201, [site], [result]
    ) is False
    assert path.read_bytes() == before


def test_single_period_attempts_cache_roll_after_any_finalized_live_results(
    tmp_path, monkeypatch
) -> None:
    sites = [
        SimpleNamespace(name="成功站", url="https://success.example", pick="top"),
        SimpleNamespace(name="失败站", url="https://failure.example", pick="top"),
    ]
    results = [
        SimpleNamespace(
            index=1,
            success_line="4尾 成功站",
            ranking_value="4",
            fail_line=None,
        ),
        SimpleNamespace(
            index=2,
            success_line=None,
            ranking_value=None,
            fail_line="失败 失败站 https://failure.example 原因: 指定期缺失",
        ),
    ]
    cache_calls: list[tuple[int, int]] = []
    monkeypatch.setattr(daily.site_config, "load_sites", lambda: sites)
    monkeypatch.setattr(daily, "_crawl", lambda *args, **kwargs: results)
    monkeypatch.setattr(
        daily,
        "_write_outputs",
        lambda *args, **kwargs: (
            tmp_path / "success.txt",
            tmp_path / "failure.txt",
            True,
            ["4尾 成功站"],
            ["失败 失败站 https://failure.example 原因: 指定期缺失"],
        ),
    )
    monkeypatch.setattr(daily.health_repository, "update_site_health", lambda *args: None)
    monkeypatch.setattr(
        daily,
        "_update_cache_after_realtime_outputs",
        lambda period, configured_sites, finalized: (
            cache_calls.append((period, len(finalized))) or True
        ),
    )

    assert daily.main(["--period", "201"]) == 0
    assert cache_calls == [(201, 2)]


@pytest.mark.parametrize("indexes", [(1,), (1, 1), (1, 3)])
def test_single_period_rejects_incomplete_or_ambiguous_batch_results_before_writes(
    monkeypatch, indexes: tuple[int, ...]
) -> None:
    sites = [
        SimpleNamespace(name="甲站", url="https://a.example", pick="top"),
        SimpleNamespace(name="乙站", url="https://b.example", pick="bottom"),
    ]
    results = [
        SimpleNamespace(
            index=index,
            success_line=None,
            ranking_value=None,
            fail_line=f"失败 索引{index}",
        )
        for index in indexes
    ]
    monkeypatch.setattr(daily.site_config, "load_sites", lambda: sites)
    monkeypatch.setattr(daily, "_crawl", lambda *args, **kwargs: results)
    monkeypatch.setattr(
        daily,
        "_write_outputs",
        lambda *args, **kwargs: pytest.fail("无效批量结果不得覆盖正式TXT"),
    )
    monkeypatch.setattr(
        daily.health_repository,
        "update_site_health",
        lambda *args, **kwargs: pytest.fail("无效批量结果不得更新健康状态"),
    )
    monkeypatch.setattr(
        daily,
        "_update_cache_after_realtime_outputs",
        lambda *args, **kwargs: pytest.fail("无效批量结果不得更新缓存"),
    )

    assert daily.main(["--period", "201"]) == 1


@pytest.mark.parametrize(
    ("success_line", "ranking_value", "fail_line"),
    [
        ("2尾 其他站", "2", None),
        ("3尾 结果契约站", "2", None),
        ("2尾 结果契约站", "2", "失败 结果契约站 原因: 矛盾"),
        (None, "2", None),
        (None, None, None),
    ],
)
def test_single_period_rejects_invalid_result_content_before_writes(
    monkeypatch, success_line: str | None, ranking_value: str | None, fail_line: str | None
) -> None:
    site = SimpleNamespace(
        name="结果契约站", url="https://result-content.example", pick="top"
    )
    result = SimpleNamespace(
        index=1,
        success_line=success_line,
        ranking_value=ranking_value,
        fail_line=fail_line,
    )
    monkeypatch.setattr(daily.site_config, "load_sites", lambda: [site])
    monkeypatch.setattr(daily, "_crawl", lambda *args, **kwargs: [result])
    monkeypatch.setattr(
        daily,
        "_write_outputs",
        lambda *args, **kwargs: pytest.fail("无效结果内容不得覆盖正式TXT"),
    )
    monkeypatch.setattr(
        daily.health_repository,
        "update_site_health",
        lambda *args, **kwargs: pytest.fail("无效结果内容不得更新健康状态"),
    )

    assert daily.main(["--period", "201"]) == 1


def test_empty_failure_output_deletion_uses_the_same_path_lock(tmp_path) -> None:
    path = tmp_path / "failure.txt"
    path.write_text("old", encoding="utf-8")
    finished = threading.Event()

    def remove() -> None:
        txt_writer.write_optional_fail_file(path, [])
        finished.set()

    with file_lock(path):
        thread = threading.Thread(target=remove)
        thread.start()
        assert not finished.wait(0.1)

    thread.join(timeout=2)
    assert finished.is_set()
    assert not path.exists()


def test_health_read_modify_write_is_inside_the_artifact_lock(tmp_path, monkeypatch) -> None:
    path = tmp_path / "health.json"
    entered: list[object] = []

    @contextmanager
    def fake_lock(locked_path):
        entered.append(locked_path)
        yield

    monkeypatch.setattr(health_repository, "file_lock", fake_lock, raising=False)
    monkeypatch.setattr(
        health_repository,
        "_atomic_write_text_unlocked",
        lambda target, text, encoding: target.write_text(text, encoding=encoding),
        raising=False,
    )
    site = SimpleNamespace(name="健康站", url="https://health.example", pick="top")
    result = SimpleNamespace(index=1, fail_line=None)

    health_repository.update_site_health({1: site}, [result], path=path)

    assert entered == [path]


@pytest.mark.parametrize("contents", ["not-json", "[]"])
def test_health_does_not_overwrite_existing_corrupt_json(tmp_path, contents: str) -> None:
    path = tmp_path / "health.json"
    path.write_text(contents, encoding="utf-8")
    before = hashlib.sha256(path.read_bytes()).digest()
    site = SimpleNamespace(name="损坏健康站", url="https://broken-health.example", pick="top")
    result = SimpleNamespace(index=1, fail_line=None)

    with pytest.raises(ValueError):
        health_repository.update_site_health({1: site}, [result], path=path)

    assert hashlib.sha256(path.read_bytes()).digest() == before


def test_failed_result_value_is_not_written_to_success_ranking(tmp_path) -> None:
    success_path = tmp_path / "success.txt"
    failure_path = tmp_path / "failure.txt"
    args = Namespace(success=str(success_path), fail=str(failure_path))
    result = SimpleNamespace(
        success_line=None,
        ranking_value="9",
        fail_line="失败 站点 https://failed.example 原因: 指定期缺失",
    )

    daily._write_outputs(201, args, [result])

    assert "9尾" not in success_path.read_text(encoding="utf-8-sig")


def test_duplicate_check_bat_has_no_cache_write_mode() -> None:
    bat = Path(__file__).with_name("爬虫-每天杀尾 - 检测重复.bat")
    text = bat.read_text(encoding="utf-8-sig")

    assert "--write-cache" not in text
    assert "--use-recent-cache" not in text


def test_configuration_fingerprint_is_order_sensitive_and_rule_sensitive(monkeypatch) -> None:
    sites = [
        SimpleNamespace(name="甲", url="https://甲.example", pick="top"),
        SimpleNamespace(name="乙", url="https://乙.example", pick="bottom"),
    ]
    rules = {site.name: StrictRule() for site in sites}
    monkeypatch.setattr(
        cache_repository,
        "effective_rule_for",
        lambda _url, name: rules[name],
        raising=False,
    )

    first = cache_repository.configuration_fingerprint(sites)
    reordered = cache_repository.configuration_fingerprint(list(reversed(sites)))
    rules["乙"] = StrictRule(dedicated_parser="changed")

    assert first != reordered
    assert first != cache_repository.configuration_fingerprint(sites)


def test_cache_roll_rejects_reordered_old_active_snapshot_without_writing(tmp_path) -> None:
    url_a = "https://ordered-cache-a.example"
    url_b = "https://ordered-cache-b.example"
    sites = [
        SimpleNamespace(name="顺序甲", url=url_a, pick="top"),
        SimpleNamespace(name="顺序乙", url=url_b, pick="bottom"),
    ]
    old_items = [
        {
            "name": sites[1].name,
            "url": sites[1].url,
            "pick": sites[1].pick,
            "periods": [200],
            "values": ["1"],
        },
        {
            "name": sites[0].name,
            "url": sites[0].url,
            "pick": sites[0].pick,
            "periods": [200],
            "values": ["2"],
        },
    ]
    path = tmp_path / "recent_10_cache.json"
    path.write_text(
        json.dumps(
            _with_fingerprint(
                {
                    "schema": 2,
                    "period": 200,
                    "window": 2,
                    "site_count": 2,
                    "vector_count": 2,
                    "fail_count": 0,
                    "fail_lines": [],
                    "sites": old_items,
                },
                sites,
            )
        ),
        encoding="utf-8",
    )
    before = path.read_bytes()
    results = cast(list[CurrentRunResult], [
        SimpleNamespace(index=1, success_line="3尾 顺序甲", ranking_value="3", fail_line=None),
        SimpleNamespace(index=2, success_line="4尾 顺序乙", ranking_value="4", fail_line=None),
    ])

    assert cache_repository.update_recent_cache_from_current_results(
        path, 201, sites, results
    ) is False
    assert path.read_bytes() == before


def test_consecutive_cache_reader_rejects_reordered_active_snapshot(tmp_path, monkeypatch) -> None:
    period = 201
    window = 3
    sites = [
        consecutive_duplicates.Site("连续顺序甲", "https://consecutive-order-a.example", "top"),
        consecutive_duplicates.Site("连续顺序乙", "https://consecutive-order-b.example", "bottom"),
    ]
    items = [
        {
            "name": site.name,
            "url": site.url,
            "pick": site.pick,
            "periods": [period, period - 1, period - 2],
            "values": ["1", "2", "3"],
        }
        for site in reversed(sites)
    ]
    payload = _with_fingerprint(
        {
            "schema": 2,
            "period": period,
            "window": window,
            "site_count": 2,
            "vector_count": 2,
            "fail_count": 0,
            "fail_lines": [],
            "sites": items,
        },
        sites,
    )
    path = tmp_path / "recent_10_cache.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        consecutive_duplicates,
        "configuration_fingerprint",
        lambda _sites: payload["config_fingerprint"],
    )

    assert consecutive_duplicates.load_recent_cache(path, period, window, sites) == []


def test_admission_cache_reader_rejects_reordered_active_snapshot(tmp_path, monkeypatch) -> None:
    period = 201
    sites = [
        duplicate_check.Site("判重顺序甲", "https://admission-order-a.example", "top"),
        duplicate_check.Site("判重顺序乙", "https://admission-order-b.example", "bottom"),
    ]
    items = [
        {
            "name": site.name,
            "url": site.url,
            "pick": site.pick,
            "periods": list(range(period, period - 10, -1)),
            "values": ["1"] * 10,
        }
        for site in reversed(sites)
    ]
    payload = {
        "schema": 2,
        "config_fingerprint": "expected-fingerprint",
        "period": period,
        "window": 10,
        "site_count": 2,
        "vector_count": 2,
        "fail_count": 0,
        "fail_lines": [],
        "sites": items,
    }
    path = tmp_path / "recent_10_cache.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(duplicate_check, "configured_sites", lambda: sites)
    monkeypatch.setattr(
        duplicate_check,
        "configuration_fingerprint",
        lambda _sites: "expected-fingerprint",
    )

    with pytest.raises(LookupError, match="快照"):
        duplicate_check.load_recent_cache_vectors(path)


def test_admission_cache_reader_rejects_wrong_schema(tmp_path, monkeypatch) -> None:
    period = 201
    site = duplicate_check.Site(
        "旧结构站", "https://old-schema.example", "top"
    )
    payload = {
        "schema": 1,
        "config_fingerprint": "expected-fingerprint",
        "period": period,
        "window": 10,
        "site_count": 1,
        "vector_count": 1,
        "fail_count": 0,
        "fail_lines": [],
        "sites": [
            {
                "name": site.name,
                "url": site.url,
                "pick": site.pick,
                "periods": list(range(period, period - 10, -1)),
                "values": ["1"] * 10,
            }
        ],
    }
    path = tmp_path / "recent_10_cache.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(duplicate_check, "configured_sites", lambda: [site])
    monkeypatch.setattr(
        duplicate_check,
        "configuration_fingerprint",
        lambda _sites: "expected-fingerprint",
    )

    with pytest.raises(LookupError, match="schema"):
        duplicate_check.load_recent_cache_vectors(path)


@pytest.mark.parametrize("stored_fingerprint", [None, "wrong-fingerprint"])
def test_cache_roll_rejects_missing_or_mismatched_configuration_fingerprint(
    tmp_path, monkeypatch, stored_fingerprint: str | None
) -> None:
    url = "https://fingerprint-roll.example/list"
    cache_path = tmp_path / "recent_10_cache.json"
    payload = {
        "schema": 2,
        "period": 200,
        "window": 2,
        "site_count": 1,
        "vector_count": 1,
        "fail_count": 0,
        "fail_lines": [],
        "sites": [
            {
                "name": "指纹站",
                "url": url,
                "pick": "top",
                "periods": [200],
                "values": ["1"],
            }
        ],
    }
    if stored_fingerprint is not None:
        payload["config_fingerprint"] = stored_fingerprint
    cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    site = SimpleNamespace(name="指纹站", url=url, pick="top")
    result = cast(CurrentRunResult, SimpleNamespace(
        index=1, success_line="2尾 指纹站", ranking_value="2", fail_line=None
    ))
    monkeypatch.setattr(
        cache_repository,
        "effective_rule_for",
        lambda _url, _name: StrictRule(),
        raising=False,
    )

    assert cache_repository.update_recent_cache_from_current_results(
        cache_path, 201, [site], [result]
    ) is False


@pytest.mark.parametrize("stored_fingerprint", [None, "wrong-fingerprint"])
def test_consecutive_cache_reader_rejects_missing_or_mismatched_fingerprint(
    tmp_path, monkeypatch, stored_fingerprint: str | None
) -> None:
    period = 201
    site = consecutive_duplicates.Site(
        "连续指纹站", "https://consecutive-fingerprint.example/list", "top"
    )
    payload = {
        "schema": 2,
        "period": period,
        "window": 3,
        "site_count": 1,
        "vector_count": 1,
        "fail_count": 0,
        "fail_lines": [],
        "sites": [
            {
                "name": site.name,
                "url": site.url,
                "pick": site.pick,
                "periods": [period, period - 1, period - 2],
                "values": ["1", "2", "3"],
            }
        ],
    }
    if stored_fingerprint is not None:
        payload["config_fingerprint"] = stored_fingerprint
    cache_path = tmp_path / "recent_10_cache.json"
    cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(
        consecutive_duplicates,
        "configuration_fingerprint",
        lambda _sites: "expected-fingerprint",
        raising=False,
    )

    assert consecutive_duplicates.load_recent_cache(
        cache_path, period, 3, [site]
    ) == []


@pytest.mark.parametrize("stored_fingerprint", [None, "wrong-fingerprint"])
def test_admission_cache_reader_rejects_missing_or_mismatched_fingerprint(
    tmp_path, monkeypatch, stored_fingerprint: str | None
) -> None:
    period = 201
    site = duplicate_check.Site(
        "新增指纹站", "https://admission-fingerprint.example/list", "top"
    )
    periods = list(range(period, period - 10, -1))
    payload = {
        "schema": 2,
        "period": period,
        "window": 10,
        "site_count": 1,
        "vector_count": 1,
        "fail_count": 0,
        "fail_lines": [],
        "sites": [
            {
                "name": site.name,
                "url": site.url,
                "pick": site.pick,
                "periods": periods,
                "values": ["1"] * 10,
            }
        ],
    }
    if stored_fingerprint is not None:
        payload["config_fingerprint"] = stored_fingerprint
    cache_path = tmp_path / "recent_10_cache.json"
    cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(duplicate_check, "configured_sites", lambda: [site])
    monkeypatch.setattr(
        duplicate_check,
        "configuration_fingerprint",
        lambda _sites: "expected-fingerprint",
        raising=False,
    )

    with pytest.raises(LookupError, match="指纹"):
        duplicate_check.load_recent_cache_vectors(cache_path)


def test_consecutive_cache_only_valid_cache_is_read_only_success(tmp_path, monkeypatch) -> None:
    period = 201
    window = 10
    site = consecutive_duplicates.Site(
        "只读缓存站", "https://cache-only.example/list", "top"
    )
    payload = _with_fingerprint(
        {
            "schema": 2,
            "period": period,
            "window": window,
            "site_count": 1,
            "vector_count": 1,
            "fail_count": 0,
            "fail_lines": [],
            "sites": [
                {
                    "name": site.name,
                    "url": site.url,
                    "pick": site.pick,
                    "periods": list(range(period, period - window, -1)),
                    "values": ["1"] * window,
                }
            ],
        },
        [site],
    )
    cache_path = tmp_path / "recent_10_cache.json"
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    before = cache_path.read_bytes()
    output_path = tmp_path / "duplicates.txt"
    monkeypatch.setattr(consecutive_duplicates, "configured_sites", lambda: [site])

    assert consecutive_duplicates.run(
        period=period,
        recent_cache=str(cache_path),
        output=str(output_path),
        cache_only=True,
    ) == 0
    assert cache_path.read_bytes() == before
    assert not output_path.exists()


def test_consecutive_cache_only_invalid_cache_returns_one(
    tmp_path, monkeypatch, capsys
) -> None:
    period = 201
    site = consecutive_duplicates.Site(
        "无效缓存站", "https://invalid-cache-only.example/list", "top"
    )
    payload = _with_fingerprint(
        {
            "schema": 2,
            "period": period,
            "window": 10,
            "site_count": 1,
            "vector_count": 1,
            "fail_count": 1,
            "fail_lines": ["失败 无效缓存站 原因: 旧期失败"],
            "sites": [
                {
                    "name": site.name,
                    "url": site.url,
                    "pick": site.pick,
                    "periods": list(range(period, period - 10, -1)),
                    "values": ["1"] * 10,
                }
            ],
        },
        [site],
    )
    cache_path = tmp_path / "recent_10_cache.json"
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(consecutive_duplicates, "configured_sites", lambda: [site])

    assert consecutive_duplicates.run(
        period=period,
        recent_cache=str(cache_path),
        cache_only=True,
    ) == 1
    assert "正式近10期缓存无效或不完整" in capsys.readouterr().err


def test_batch_future_exception_uses_complete_failure_contract(monkeypatch) -> None:
    site = SiteConfig(name="批量失败站", url="https://batch-failure.example", pick="bottom")

    def fail(*_args, **_kwargs):
        raise RuntimeError("worker exploded")

    monkeypatch.setattr(batch_crawl, "crawl_current_site", fail)

    results = batch_crawl.crawl_indexed_sites(
        [(1, site)], 1, 201, 1, workers=1
    )

    assert results[0].fail_line == (
        "失败 批量失败站 https://batch-failure.example 方向: bottom "
        "期数: 201 阶段: 批量编排 原因: RuntimeError: worker exploded"
    )


def test_multi_period_parses_complete_and_legacy_failure_lines(tmp_path) -> None:
    path = tmp_path / "failure.txt"
    path.write_text(
        "\n".join(
            [
                "失败 含 空格站 https://full-failure.example 方向: bottom 期数: 201 "
                "阶段: 批量编排 原因: RuntimeError: worker exploded",
                "失败 旧格式站 https://legacy-failure.example 原因: 指定期缺失",
            ]
        ),
        encoding="utf-8",
    )

    assert multi_period.parse_fail_file(path) == {
        "含 空格站": "RuntimeError: worker exploded",
        "旧格式站": "指定期缺失",
    }


def test_multi_period_ignores_malformed_failure_lines(tmp_path) -> None:
    path = tmp_path / "failure.txt"
    path.write_text(
        "\n".join(
            [
                "普通文本",
                "失败 缺少原因 https://missing-reason.example",
                "失败 元数据错误 https://bad-metadata.example 方向: top 期数: x 阶段: 解析 原因: 错误",
                "失败 单字段 原因: 错误",
            ]
        ),
        encoding="utf-8",
    )

    assert multi_period.parse_fail_file(path) == {}


def test_multi_period_summary_reads_resolved_period_outputs(tmp_path, monkeypatch) -> None:
    site = SimpleNamespace(
        name="多期成功站", url="https://multi-success.example", pick="top"
    )
    success_path = tmp_path / "success.txt"
    failure_path = tmp_path / "failure.txt"
    success_path.write_text("1尾 多期成功站\n", encoding="utf-8")
    failure_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(duplicate_check, "configured_sites", lambda: [site])
    monkeypatch.setattr(
        txt_writer,
        "default_current_output_names",
        lambda _period: ("success.txt", "failure.txt"),
    )
    monkeypatch.setattr(txt_writer, "resolve_success_path", lambda _name: success_path)
    monkeypatch.setattr(txt_writer, "resolve_failure_path", lambda _name: failure_path)

    report_path = multi_period.build_summary([201], tmp_path / "summary.txt")

    report = report_path.read_text(encoding="utf-8-sig")
    assert "全部失败目录数: 0" in report
    assert "无全部失败目录" in report


def test_multi_period_summary_ignores_stale_outputs_after_subprocess_failure(
    tmp_path, monkeypatch
) -> None:
    site = SimpleNamespace(
        name="旧文件站", url="https://stale-period.example", pick="bottom"
    )
    stale_success = tmp_path / "success.txt"
    stale_failure = tmp_path / "failure.txt"
    stale_success.write_text("1尾 旧文件站\n", encoding="utf-8")
    stale_failure.write_text("", encoding="utf-8")
    monkeypatch.setattr(duplicate_check, "configured_sites", lambda: [site])
    monkeypatch.setattr(
        txt_writer,
        "default_current_output_names",
        lambda _period: ("success.txt", "failure.txt"),
    )
    monkeypatch.setattr(txt_writer, "resolve_success_path", lambda _name: stale_success)
    monkeypatch.setattr(txt_writer, "resolve_failure_path", lambda _name: stale_failure)

    report_path = multi_period.build_summary(
        [201], tmp_path / "summary.txt", run_codes={201: 1}
    )

    report = report_path.read_text(encoding="utf-8-sig")
    assert "全部失败目录数: 1" in report
    assert "201期: 单期子进程退出码1，本轮输出无效" in report


def test_health_without_success_or_failure_is_recorded_as_failure(tmp_path) -> None:
    path = tmp_path / "health.json"
    site = SimpleNamespace(name="无结果健康站", url="https://no-result.example", pick="top")
    result = SimpleNamespace(index=1, success_line=None, fail_line=None)

    health_repository.update_site_health({1: site}, [result], path=path)

    entry = json.loads(path.read_text(encoding="utf-8-sig"))[site.url]
    assert entry["success_count"] == 0
    assert entry["fail_count"] == 1
    assert entry["last_error"] == "本次未生成有效结果"


@pytest.mark.parametrize("archived_flags", [(False, False), (False, True)])
def test_cache_roll_rejects_duplicate_old_identity_without_writing(
    tmp_path, archived_flags: tuple[bool, bool]
) -> None:
    url = "https://duplicate-old-identity.example/list"
    site = SimpleNamespace(name="重复旧身份站", url=url, pick="top")
    items = [
        {
            "name": site.name,
            "url": url,
            "pick": "top",
            "periods": [200],
            "values": ["1"],
            **({"archived": True} if archived else {}),
        }
        for archived in archived_flags
    ]
    path = tmp_path / "recent_10_cache.json"
    path.write_text(
        json.dumps(
            _with_fingerprint(
                {
                    "schema": 2,
                    "period": 200,
                    "window": 2,
                    "site_count": 1,
                    "vector_count": 1,
                    "fail_count": 0,
                    "fail_lines": [],
                    "sites": items,
                },
                [site],
            )
        ),
        encoding="utf-8",
    )
    before = path.read_bytes()
    result = cast(CurrentRunResult, SimpleNamespace(
        index=1, success_line="2尾 重复旧身份站", ranking_value="2", fail_line=None
    ))

    assert cache_repository.update_recent_cache_from_current_results(
        path, 201, [site], [result]
    ) is False
    assert path.read_bytes() == before


def test_consecutive_cache_reader_rejects_duplicate_active_archived_identity(
    tmp_path, monkeypatch
) -> None:
    period = 201
    window = 3
    site = consecutive_duplicates.Site(
        "连续重复身份站", "https://consecutive-duplicate-identity.example", "top"
    )
    item = {
        "name": site.name,
        "url": site.url,
        "pick": site.pick,
        "periods": [period, period - 1, period - 2],
        "values": ["1", "2", "3"],
    }
    payload = _with_fingerprint(
        {
            "schema": 2,
            "period": period,
            "window": window,
            "site_count": 1,
            "vector_count": 1,
            "fail_count": 0,
            "fail_lines": [],
            "sites": [item, {**item, "archived": True}],
        },
        [site],
    )
    path = tmp_path / "recent_10_cache.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(consecutive_duplicates, "configuration_fingerprint", lambda _sites: payload["config_fingerprint"])

    assert consecutive_duplicates.load_recent_cache(path, period, window, [site]) == []


def test_admission_cache_reader_rejects_duplicate_active_archived_identity(
    tmp_path, monkeypatch
) -> None:
    period = 201
    site = duplicate_check.Site(
        "判重重复身份站", "https://admission-duplicate-identity.example", "top"
    )
    item = {
        "name": site.name,
        "url": site.url,
        "pick": site.pick,
        "periods": list(range(period, period - 10, -1)),
        "values": ["1"] * 10,
    }
    payload = {
        "schema": 2,
        "config_fingerprint": "expected-fingerprint",
        "period": period,
        "window": 10,
        "site_count": 1,
        "vector_count": 1,
        "fail_count": 0,
        "fail_lines": [],
        "sites": [item, {**item, "archived": True}],
    }
    path = tmp_path / "recent_10_cache.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(duplicate_check, "configured_sites", lambda: [site])
    monkeypatch.setattr(duplicate_check, "configuration_fingerprint", lambda _sites: "expected-fingerprint")

    with pytest.raises(LookupError, match="重复"):
        duplicate_check.load_recent_cache_vectors(path)
