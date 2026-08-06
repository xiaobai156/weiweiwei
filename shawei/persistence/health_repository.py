from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

from shawei.config.paths import SITE_HEALTH_PATH
from shawei.domain.text import canonical_pick, normalize_text
from shawei.persistence.atomic_file import atomic_write_text
from shawei.persistence.txt_writer import classify_failure_text


def _health_key(data: dict[str, Any], site) -> str:
    """Keep health entries separate when multiple configured sites share a URL."""
    base_key = site.url
    base_entry = data.get(base_key)
    if not isinstance(base_entry, dict):
        return base_key

    current_name = normalize_text(str(base_entry.get("name", "")))
    site_name = normalize_text(str(site.name))
    if not current_name or current_name == site_name:
        return base_key
    return f"{base_key}#name={site.name}"


def update_site_health(sites_by_index, results, path: Path = SITE_HEALTH_PATH) -> None:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        data: dict[str, Any] = (
            json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
        )
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    for result in results:
        site = sites_by_index.get(result.index)
        if site is None:
            continue
        key = _health_key(data, site)
        entry: dict[str, Any] | None = data.get(key)
        if not isinstance(entry, dict):
            entry = {"success_count": 0, "fail_count": 0}
        entry.update({
            "name": site.name,
            "url": site.url,
            "pick": canonical_pick(site.pick),
        })
        if getattr(result, "fail_line", None):
            entry["fail_count"] = int(entry.get("fail_count") or 0) + 1
            entry["last_failure"] = now
            entry["last_error"] = result.fail_line
            entry["last_error_category"] = classify_failure_text(result.fail_line)
        else:
            entry["success_count"] = int(entry.get("success_count") or 0) + 1
            entry["last_success"] = now
            entry["last_error_category"] = ""
        data[key] = entry

    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")
