from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from shawei.config.paths import OUTPUT_DIR, RECENT_CACHE_PATH
from shawei.config.sites import load_sites
from shawei.domain.text import canonical_pick
from shawei.persistence.atomic_file import atomic_write_text
from shawei.persistence.cache_repository import (
    _cache_identity,
    configuration_fingerprint,
    is_valid_result_value,
)

WINDOW_SIZE = 10
SUSPECT_MIN_CONSECUTIVE = 3
DUPLICATE_MIN_CONSECUTIVE = 6


@dataclass(frozen=True)
class Site:
    name: str
    url: str
    pick: str


@dataclass(frozen=True)
class DataVector:
    site: Site
    periods: tuple[int, ...]
    values: tuple[str, ...]
    extended: int


@dataclass(frozen=True)
class ConsecutiveMatch:
    site_a: Site
    site_b: Site
    level: str
    start_period: int
    end_period: int
    matched_periods: tuple[int, ...]
    matched_values: tuple[str, ...]


def configured_sites() -> list[Site]:
    return [Site(site.name, site.url, site.pick) for site in load_sites()]


def _cache_item_to_vector(item: dict) -> DataVector | None:
    if item.get("failed_periods") or item.get("failure_reasons"):
        return None
    try:
        name = str(item["name"])
        url = str(item["url"])
        pick = canonical_pick(str(item.get("pick") or "top"))
        periods = tuple(int(period) for period in item["periods"])
        values = tuple(str(value) for value in item["values"])
        extended = int(item.get("extended") or max(0, WINDOW_SIZE - len(periods)))
    except (KeyError, TypeError, ValueError):
        return None
    if not name or not url or len(periods) != len(values):
        return None
    return DataVector(Site(name, url, pick), periods, values, extended)


def load_recent_cache(
    path: Path,
    period: int,
    window: int,
    configured: list[Site] | None = None,
) -> list[DataVector]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    if payload.get("schema") != 2:
        return []
    if configured is None:
        configured = configured_sites()
    try:
        expected_fingerprint = configuration_fingerprint(configured)
    except Exception:
        return []
    if payload.get("config_fingerprint") != expected_fingerprint:
        return []
    if payload.get("period") != period or payload.get("window") != window:
        return []
    if payload.get("fail_count") != 0 or payload.get("site_count") != payload.get(
        "vector_count"
    ):
        return []
    items = payload.get("sites")
    if not isinstance(items, list):
        return []
    seen_identities: set[tuple[str, str, str]] = set()
    for item in items:
        if not isinstance(item, dict):
            return []
        identity = _cache_identity(item.get("name"), item.get("url"), item.get("pick"))
        if identity is None or identity in seen_identities:
            return []
        seen_identities.add(identity)
    active = [item for item in items if isinstance(item, dict) and not item.get("archived")]
    if payload.get("site_count") != len(active):
        return []
    expected = tuple(range(period, period - window, -1))
    vectors: list[DataVector] = []
    for item in active:
        vector = _cache_item_to_vector(item)
        if (
            vector is None
            or len(vector.periods) != window
            or len(set(vector.periods)) != window
            or vector.periods != expected
            or any(
                not is_valid_result_value(value, vector.site.url)
                for value in vector.values
            )
        ):
            return []
        vectors.append(vector)
    if payload.get("vector_count") != len(vectors):
        return []
    if configured is not None:
        cached = [(item.site.name, item.site.url, item.site.pick) for item in vectors]
        current = [
            (item.name, item.url, canonical_pick(item.pick))
            for item in configured
        ]
        if cached != current:
            return []
    return vectors


def find_consecutive_overlap(
    vector_a: DataVector, vector_b: DataVector
) -> ConsecutiveMatch | None:
    lookup_a = dict(zip(vector_a.periods, vector_a.values))
    lookup_b = dict(zip(vector_b.periods, vector_b.values))
    overlap = sorted(set(vector_a.periods) & set(vector_b.periods), reverse=True)
    best_periods: list[int] = []
    best_values: list[str] = []
    current_periods: list[int] = []
    current_values: list[str] = []

    def flush() -> None:
        nonlocal best_periods, best_values, current_periods, current_values
        if len(current_periods) > len(best_periods):
            best_periods, best_values = current_periods, current_values
        current_periods, current_values = [], []

    previous: int | None = None
    for period in overlap:
        same = lookup_a[period] == lookup_b[period]
        consecutive = previous is None or previous - period == 1
        if same and consecutive:
            current_periods.append(period)
            current_values.append(lookup_a[period])
        elif same:
            flush()
            current_periods, current_values = [period], [lookup_a[period]]
        else:
            flush()
        previous = period
    flush()
    if len(best_periods) < SUSPECT_MIN_CONSECUTIVE:
        return None
    level = "duplicate" if len(best_periods) >= DUPLICATE_MIN_CONSECUTIVE else "suspect"
    return ConsecutiveMatch(
        vector_a.site,
        vector_b.site,
        level,
        best_periods[0],
        best_periods[-1],
        tuple(best_periods),
        tuple(best_values),
    )


def format_output(
    matches: list[ConsecutiveMatch], fail_lines: list[str], period: int
) -> tuple[list[str], list[str]]:
    duplicate_matches = [match for match in matches if match.level == "duplicate"]
    suspect_matches = [match for match in matches if match.level == "suspect"]
    lines = [
        f"检测窗口: 从{period}期往前{WINDOW_SIZE}期（每站必须完整覆盖）",
        f"疑似判定: 双方共同期数中连续{SUSPECT_MIN_CONSECUTIVE}-{DUPLICATE_MIN_CONSECUTIVE - 1}期相同",
        f"重复判定: 双方共同期数中连续{DUPLICATE_MIN_CONSECUTIVE}期或以上相同",
        "",
    ]
    if not matches:
        lines.extend(("没有发现任何疑似或重复站点对！", ""))
    else:
        lines.extend(
            (
                f"共发现 {len(duplicate_matches)} 对重复站点，{len(suspect_matches)} 对疑似重复站点：",
                "",
            )
        )
        for index, match in enumerate(
            sorted(matches, key=lambda item: (-item.start_period, item.site_a.name)),
            start=1,
        ):
            label = "重复对" if match.level == "duplicate" else "疑似重复对"
            lines.extend(
                (
                    f"--- {label} {index} ---",
                    f"  A: {match.site_a.name} ({match.site_a.url})",
                    f"  B: {match.site_b.name} ({match.site_b.url})",
                    f"  匹配期号: {match.start_period}期 -> {match.end_period}期（{len(match.matched_periods)}期）",
                    "  尾数: " + " -> ".join(f"{value}尾" for value in match.matched_values),
                    "",
                )
            )
    if fail_lines:
        lines.append(f"人工审核: {len(fail_lines)} 个站点未参与完整检测")
        lines.extend(f"  {line}" for line in fail_lines)
        lines.append("")
    return lines, fail_lines


def run(
    period: int = 0,
    output: str | None = None,
    recent_cache: str | None = None,
    cache_only: bool = False,
) -> int:
    sites = configured_sites()
    cache_path = Path(recent_cache) if recent_cache else RECENT_CACHE_PATH
    if not cache_path.is_absolute():
        cache_path = RECENT_CACHE_PATH.parent / cache_path

    if period == 0:
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8-sig"))
            period = int(payload["period"])
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            print(f"正式近10期缓存无效或期数不可读: {cache_path}", file=sys.stderr)
            return 1
    cached = load_recent_cache(cache_path, period, WINDOW_SIZE, sites)
    if not cached:
        print(
            f"正式近10期缓存无效或不完整，连续重复检测未完成: {cache_path}",
            file=sys.stderr,
        )
        return 1
    vectors = cached
    fail_lines: list[str] = []

    if cache_only:
        return 0

    matches = [
        match
        for left in range(len(vectors))
        for right in range(left + 1, len(vectors))
        if (match := find_consecutive_overlap(vectors[left], vectors[right])) is not None
    ]
    output_lines, _ = format_output(matches, fail_lines, period)
    result_path = Path(output) if output else OUTPUT_DIR / f"{period}期连续重复检测.txt"
    if not result_path.is_absolute():
        result_path = OUTPUT_DIR / result_path
    atomic_write_text(result_path, "\n".join(output_lines) + "\n", encoding="utf-8-sig")
    return 0
