from shawei.domain.models import Record
from shawei.parsers import safety_guards


def test_enforce_parsed_records_builds_period_evidence_once(monkeypatch) -> None:
    calls = 0
    original = safety_guards._period_evidence_by_period

    def counted(document: str):
        nonlocal calls
        calls += 1
        return original(document)

    monkeypatch.setattr(safety_guards, "_period_evidence_by_period", counted)
    records = [
        Record(tail=7, period=255, site_name="测试站"),
        Record(tail=7, period=255, site_name="测试站"),
    ]

    safety_guards.enforce_parsed_records(
        records,
        source="dedicated",
        parser_name="ordinary_parser",
        document="255期 绝杀一尾 7尾 开准",
        site_name="测试站",
    )

    assert calls == 1
