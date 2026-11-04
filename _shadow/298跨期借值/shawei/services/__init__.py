"""Application services."""

from __future__ import annotations

from . import crawl_site as crawl_site


def _exact_dynamic_identity(value: str, target_id: str) -> bool:
    return value.strip() == target_id.strip()


# Browser fallback may only trust an exact record identity. Composite DOM ids
# such as "related-<id>" are navigation/layout ids, not the target article.
crawl_site._attribute_matches_target = _exact_dynamic_identity
crawl_site._DYNAMIC_EXPLICIT_RECORD_ID_ATTRIBUTES.add("id")
