from __future__ import annotations

from shawei.domain.models import Record
from shawei.parsers.safety_guards import enforce_parsed_records


def test_unrelated_multidigit_other_field_does_not_invalidate_valid_tail() -> None:
    record = Record(
        tail=5,
        period=251,
        site_name="审计站",
        source_snippet="251期绝杀一尾[5] 杀码23 开猴23准",
    )
    assert enforce_parsed_records(
        [record],
        source="dedicated",
        parser_name="legacy_single_tail",
        document=record.source_snippet,
        site_name="审计站",
    ) == [record]
