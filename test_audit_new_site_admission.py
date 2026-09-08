from __future__ import annotations

import pytest

from shawei.domain.models import Record
from shawei.services import duplicate_check


def _record(period: int, value: int, *, tails: tuple[int, ...] = ()) -> Record:
    return Record(
        tail=value,
        period=period,
        site_name="候选站",
        tail_values=tails,
    )


def _prepare(
    monkeypatch,
    candidate_records: list[Record],
    existing_values: dict[int, str] | None = None,
):
    calls: list[int | None] = []
    existing = duplicate_check.Site("现有站", "https://existing.test/topic/1.html")
    monkeypatch.setattr(duplicate_check, "configured_sites", lambda: [])
    monkeypatch.setattr(
        duplicate_check,
        "load_recent_cache_vectors",
        lambda **_kwargs: (
            236,
            10,
            [(existing, existing_values or {period: "9" for period in range(236, 226, -1)})],
        ),
    )

    def collect(_url, _name, *, pick, timeout, target_period=None):
        del pick, timeout
        calls.append(target_period)
        if target_period in {236, 235}:
            return [
                record
                for record in candidate_records
                if record.period == target_period
            ]
        if target_period is None:
            return list(candidate_records)
        pytest.fail(f"历史判重不应逐期重新抓取: {target_period}")

    monkeypatch.setattr(duplicate_check.crawl_site, "collect_site_records", collect)
    return calls


def test_admission_compares_only_available_history_without_refetching_each_period(
    monkeypatch,
) -> None:
    calls = _prepare(
        monkeypatch,
        [_record(236, 5), _record(235, 4), _record(233, 3)],
    )

    result = duplicate_check.evaluate_new_site_admission(
        "候选站",
        "https://candidate.test/topic/2.html",
        "top",
        236,
    )

    assert result.accepted is True
    assert result.fingerprint == ("5", "4", "3")
    assert calls == [236, None]


def test_admission_rejects_conflicting_same_period_history(monkeypatch) -> None:
    _prepare(
        monkeypatch,
        [_record(236, 5), _record(236, 6), _record(235, 4)],
    )

    result = duplicate_check.evaluate_new_site_admission(
        "候选站",
        "https://candidate.test/topic/2.html",
        "top",
        236,
    )

    assert result.accepted is False
    assert "236期" in result.reason
    assert "唯一" in result.reason or "冲突" in result.reason


def test_unapproved_url_cannot_admit_two_tail_records(monkeypatch) -> None:
    calls = _prepare(
        monkeypatch,
        [_record(236, 1, tails=(1, 2)), _record(235, 3, tails=(3, 4))],
    )

    result = duplicate_check.evaluate_new_site_admission(
        "候选站",
        "https://candidate.test/topic/2.html",
        "top",
        236,
    )

    assert result.accepted is False
    assert "最新期或上一期" in result.reason
    assert calls == [236, 235]


def test_missing_periods_do_not_join_separate_matches(monkeypatch) -> None:
    calls = _prepare(
        monkeypatch,
        [_record(236, 5), _record(234, 5), _record(232, 5)],
        {period: "5" for period in range(236, 226, -1)},
    )

    result = duplicate_check.evaluate_new_site_admission(
        "候选站",
        "https://candidate.test/topic/2.html",
        "top",
        236,
    )

    assert result.accepted is True
    assert result.duplicates == ()
    assert result.suspicions == ()
    assert calls == [236, None]


def test_history_fetch_failure_is_a_rejected_admission(monkeypatch) -> None:
    monkeypatch.setattr(duplicate_check, "configured_sites", lambda: [])
    monkeypatch.setattr(
        duplicate_check,
        "load_recent_cache_vectors",
        lambda **_kwargs: (236, 10, []),
    )

    def collect(_url, _name, *, pick, timeout, target_period=None):
        del pick, timeout
        if target_period == 236:
            return [_record(236, 5)]
        raise RuntimeError("history unavailable")

    monkeypatch.setattr(duplicate_check.crawl_site, "collect_site_records", collect)

    result = duplicate_check.evaluate_new_site_admission(
        "候选站",
        "https://candidate.test/topic/2.html",
        "top",
        236,
    )

    assert result.accepted is False
    assert "历史数据抓取/解析失败" in result.reason


def test_admission_rejects_base_period_conflict_between_targeted_and_history_modes(
    monkeypatch,
) -> None:
    monkeypatch.setattr(duplicate_check, "configured_sites", lambda: [])
    monkeypatch.setattr(
        duplicate_check,
        "load_recent_cache_vectors",
        lambda **_kwargs: (236, 10, []),
    )

    def collect(_url, _name, *, pick, timeout, target_period=None):
        del pick, timeout
        if target_period == 236:
            return [_record(236, 5)]
        if target_period is None:
            return [_record(236, 6)]
        return []

    monkeypatch.setattr(duplicate_check.crawl_site, "collect_site_records", collect)

    result = duplicate_check.evaluate_new_site_admission(
        "候选站",
        "https://candidate.test/topic/2.html",
        "top",
        236,
    )

    assert result.accepted is False
    assert "同期冲突" in result.reason
