from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

import shawei_consecutive_duplicate_checker as checker
from shawei.services import consecutive_duplicates as service

PERIOD = 236
WINDOW = 10
PERIODS = tuple(range(PERIOD, PERIOD - WINDOW, -1))
SITES = [
    service.Site("站点甲", "https://site-a.example", "top"),
    service.Site("站点乙", "https://site-b.example", "bottom"),
]


def _cache_payload() -> dict:
    return {
        "schema": 2,
        "period": PERIOD,
        "window": WINDOW,
        "config_fingerprint": "fixture-fingerprint",
        "site_count": len(SITES),
        "vector_count": len(SITES),
        "fail_count": 0,
        "fail_lines": [],
        "sites": [
            {
                "name": site.name,
                "url": site.url,
                "pick": site.pick,
                "periods": list(PERIODS),
                "values": ["1"] * WINDOW if index == 0 else ["2"] * WINDOW,
                "extended": 0,
            }
            for index, site in enumerate(SITES)
        ],
    }


def _write_cache(path, payload: dict | None = None) -> bytes:
    path.write_text(
        json.dumps(payload or _cache_payload(), ensure_ascii=False),
        encoding="utf-8",
    )
    return path.read_bytes()


def _use_fixture_sites(monkeypatch) -> None:
    monkeypatch.setattr(service, "configured_sites", lambda: list(SITES))
    monkeypatch.setattr(
        service, "configuration_fingerprint", lambda _sites: "fixture-fingerprint"
    )


def _vector(name: str, periods: tuple[int, ...], values: tuple[str, ...]):
    return service.DataVector(service.Site(name, f"https://{name}.example", "top"), periods, values, 0)


def test_cli_is_cache_only_and_has_no_live_or_write_switches(monkeypatch):
    calls: list[dict] = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return 0

    monkeypatch.setattr(checker._service, "run", fake_run)

    assert checker.main(["--period", str(PERIOD)]) == 0

    assert checker.main(
        [
            "--period",
            str(PERIOD),
            "--recent-cache",
            "cache.json",
            "--output",
            "result.txt",
            "--cache-only",
        ]
    ) == 0
    assert calls[-1] == {
        "period": PERIOD,
        "output": "result.txt",
        "recent_cache": "cache.json",
        "cache_only": True,
    }

    with pytest.raises(SystemExit):
        checker.main(["--period", str(PERIOD), "--window", "5"])
    with pytest.raises(SystemExit):
        checker.main(["--period", str(PERIOD), "--consecutive", "3"])
    with pytest.raises(SystemExit):
        checker.main(["--period", str(PERIOD), "--fail-output", "failure.txt"])


def test_configured_sites_and_cache_item_validation_keep_their_contract(monkeypatch):
    monkeypatch.setattr(
        service,
        "load_sites",
        lambda: [SimpleNamespace(name="站点", url="https://site.example", pick="bottom")],
    )
    assert service.configured_sites() == [
        service.Site("站点", "https://site.example", "bottom")
    ]
    assert service._cache_item_to_vector({}) is None
    assert service._cache_item_to_vector(
        {"name": "", "url": "https://site.example", "periods": [1], "values": ["1"]}
    ) is None
    assert service._cache_item_to_vector(
        {"name": "站点", "url": "https://site.example", "periods": [1], "values": []}
    ) is None


def test_cache_loader_rejects_missing_malformed_and_incomplete_documents(tmp_path, monkeypatch):
    monkeypatch.setattr(
        service, "configuration_fingerprint", lambda _sites: "fixture-fingerprint"
    )
    missing = tmp_path / "missing.json"
    assert service.load_recent_cache(missing, PERIOD, WINDOW) == []

    malformed = tmp_path / "malformed.json"
    malformed.write_text("not json", encoding="utf-8")
    assert service.load_recent_cache(malformed, PERIOD, WINDOW) == []

    for index, payload in enumerate(
        [
            [],
            {**_cache_payload(), "schema": 1},
            {"period": PERIOD - 1, "window": WINDOW},
            {"period": PERIOD, "window": WINDOW, "fail_count": 0, "site_count": 0, "vector_count": 0, "sites": {}},
            {
                **_cache_payload(),
                "sites": _cache_payload()["sites"]
                + [
                    {
                        "name": "额外站点",
                        "url": "https://extra.example",
                        "pick": "top",
                        "periods": list(PERIODS),
                        "values": ["3"] * WINDOW,
                        "extended": 0,
                    }
                ],
            },
        ]
    ):
        path = tmp_path / f"invalid-{index}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert service.load_recent_cache(path, PERIOD, WINDOW, SITES) == []


def test_report_run_reads_cache_without_writing_or_fetching(tmp_path, monkeypatch):
    _use_fixture_sites(monkeypatch)
    cache_path = tmp_path / "recent_10_cache.json"
    before = _write_cache(cache_path)
    output_path = tmp_path / "result.txt"

    assert not any(
        hasattr(service, name)
        for name in ("crawl_site", "find_latest_period", "build_data_vector", "build_all_vectors", "write_recent_cache")
    )
    assert service.run(
        period=PERIOD,
        recent_cache=str(cache_path),
        output=str(output_path),
    ) == 0

    assert cache_path.read_bytes() == before
    assert "没有发现任何疑似或重复站点对！" in output_path.read_text(encoding="utf-8-sig")


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update(fail_count=1),
        lambda payload: payload.update(vector_count=1),
        lambda payload: payload["sites"][0]["values"].__setitem__(0, "10"),
        lambda payload: payload["sites"][0]["periods"].__setitem__(0, PERIOD - 1),
        lambda payload: payload["sites"][0].update(name="冒名站点"),
    ],
)
def test_incomplete_or_mismatched_cache_is_rejected_without_output(tmp_path, monkeypatch, mutation):
    _use_fixture_sites(monkeypatch)
    payload = copy.deepcopy(_cache_payload())
    mutation(payload)
    cache_path = tmp_path / "recent_10_cache.json"
    before = _write_cache(cache_path, payload)
    output_path = tmp_path / "result.txt"

    assert service.run(
        period=PERIOD,
        recent_cache=str(cache_path),
        output=str(output_path),
    ) == 1
    assert cache_path.read_bytes() == before
    assert not output_path.exists()


def test_threshold_and_period_continuity_remain_unchanged():
    six_period_match = service.find_consecutive_overlap(
        _vector("甲", PERIODS, ("1", "1", "1", "1", "1", "1", "3", "4", "5", "6")),
        _vector("乙", PERIODS, ("1", "1", "1", "1", "1", "1", "8", "7", "6", "5")),
    )
    assert six_period_match is not None
    assert six_period_match.level == "duplicate"
    assert six_period_match.matched_periods == PERIODS[:6]

    five_period_match = service.find_consecutive_overlap(
        _vector("甲", PERIODS, ("1", "1", "1", "1", "1", "2", "3", "4", "5", "6")),
        _vector("乙", PERIODS, ("1", "1", "1", "1", "1", "9", "8", "7", "6", "5")),
    )
    assert five_period_match is not None
    assert five_period_match.level == "suspect"
    assert len(five_period_match.matched_periods) == 5

    gapped = service.find_consecutive_overlap(
        _vector("甲", (PERIOD, PERIOD - 2, PERIOD - 3), ("1", "1", "1")),
        _vector("乙", (PERIOD, PERIOD - 2, PERIOD - 3), ("1", "1", "1")),
    )
    assert gapped is None


def test_output_preserves_duplicate_report_format():
    match = service.find_consecutive_overlap(
        _vector("甲", PERIODS, ("1", "1", "1", "1", "1", "1", "3", "4", "5", "6")),
        _vector("乙", PERIODS, ("1", "1", "1", "1", "1", "1", "8", "7", "6", "5")),
    )
    assert match is not None

    lines, failures = service.format_output(
        [match], ["失败 站点丙 原因: 缓存不完整"], PERIOD
    )
    report = "\n".join(lines)
    assert failures == ["失败 站点丙 原因: 缓存不完整"]
    assert "重复对" in report
    assert "匹配期号: 236期 -> 231期（6期）" in report
    assert "人工审核: 1 个站点未参与完整检测" in report
