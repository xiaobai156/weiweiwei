from __future__ import annotations

from dataclasses import fields

import shawei_failed_site_validator as validator
from shawei.config.rules import effective_rule_for


def test_failed_validator_keeps_only_identity_and_uses_formal_effective_rules() -> None:
    assert [field.name for field in fields(validator.ValidationSite)] == [
        "name",
        "url",
        "pick",
        "period",
    ]
    assert len(validator.TARGETED_FAILED_SITE_CHECKLIST) == 21

    for site in validator.TARGETED_FAILED_SITE_CHECKLIST:
        assert validator.rule_for(site) == effective_rule_for(site.url, site.name)


def test_failed_validator_has_no_unused_legacy_checklist() -> None:
    assert not hasattr(validator, "FAILED_SITE_CHECKLIST")
