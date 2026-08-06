from __future__ import annotations

import datetime
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from shawei.config.paths import FAIL_OUTPUT_DIR, OUTPUT_DIR, RECENT_CACHE_PATH
from shawei.config.sites import load_sites
from shawei.domain.text import canonical_pick, is_bottom_pick
from shawei.parsers.common import is_valid_tail_record, record_value
from shawei.persistence.atomic_file import atomic_write_text
from shawei.persistence.cache_repository import is_valid_result_value
from shawei.persistence.health_repository import update_site_health
from shawei.persistence.txt_writer import format_failure_records
from shawei.services import crawl_site


TARGET_PERIOD = 152
WINDOW_SIZE = 10
SUSPECT_MIN_CONSECUTIVE = 3
DUPLICATE_MIN_CONSECUTIVE = 6
CONSECUTIVE_REQUIRED = DUPLICATE_MIN_CONSECUTIVE
DEFAULT_TIMEOUT = 20
DEFAULT_WORKERS = 8


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


@dataclass
class SiteResult:
    index: int
    vector: DataVector | None
    fail_line: str | None
    messages: list[str] = field(default_factory=list)


def configured_sites() -> list[Site]:
    return [Site(site.name, site.url, site.pick) for site in load_sites()]


def find_latest_period(sites: list[Site]) -> int:
    def fetch(site: Site) -> int:
        try:
            with crawl_site.site_lock_for(site.url):
                records = crawl_site.collect_site_records(
                    site.url, site.name, pick=site.pick, timeout=10
                )
            if records:
                candidate = records[-1] if is_bottom_pick(site.pick) else records[0]
                return crawl_site.select_current_record(
                    records, candidate.period, site.pick
                )[0].period
        except Exception:
            pass
        return 0

    periods: list[int] = []
    workers = max(1, min(DEFAULT_WORKERS, len(sites) or 1))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for future in as_completed([executor.submit(fetch, site) for site in sites]):
            value = future.result()
            if value > 0:
                periods.append(value)
    if not periods:
        raise RuntimeError("所有站点均未能提供最新期号")
    counts = Counter(periods)
    consensus = sorted(
        (period for period, count in counts.items() if count >= 2), reverse=True
    )
    if not consensus:
        raise RuntimeError(f"自动期号没有至少2站一致的共识: {dict(counts.most_common(5))}")
    return consensus[0]


def _vector_to_cache_item(vector: DataVector) -> dict:
    return {
        "name": vector.site.name,
        "url": vector.site.url,
        "pick": canonical_pick(vector.site.pick),
        "periods": list(vector.periods),
        "values": list(vector.values),
        "extended": vector.extended,
    }


def _cache_item_to_vector(item: dict) -> DataVector | None:
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


def write_recent_cache(
    path: Path,
    period: int,
    window: int,
    site_results: list[SiteResult],
    fail_lines: list[str],
) -> bool:
    if not site_results:
        return False
    vectors = [result.vector for result in site_results if result.vector is not None]
    if fail_lines or len(vectors) != len(site_results):
        return False
    expected = set(range(period, period - window, -1))
    if any(
        set(vector.periods) != expected or len(vector.values) != window
        for vector in vectors
    ):
        return False
    archived: list[dict] = []
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8-sig"))
            previous_sites = previous.get("sites", []) if isinstance(previous, dict) else []
            archived = [
                dict(item)
                for item in previous_sites
                if isinstance(item, dict) and item.get("archived")
            ]
        except (OSError, json.JSONDecodeError):
            archived = []
    payload = {
        "schema": 1,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "period": period,
        "window": window,
        "site_count": len(site_results),
        "vector_count": len(vectors),
        "fail_count": len(fail_lines),
        "fail_lines": list(fail_lines),
        "sites": [_vector_to_cache_item(vector) for vector in vectors] + archived,
    }
    atomic_write_text(
        path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return True


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
    if payload.get("period") != period or payload.get("window") != window:
        return []
    if payload.get("fail_count") != 0 or payload.get("site_count") != payload.get(
        "vector_count"
    ):
        return []
    items = payload.get("sites")
    if not isinstance(items, list):
        return []
    active = [item for item in items if isinstance(item, dict) and not item.get("archived")]
    if payload.get("site_count") != len(active):
        return []
    expected = set(range(period, period - window, -1))
    vectors: list[DataVector] = []
    for item in active:
        vector = _cache_item_to_vector(item)
        if (
            vector is None
            or len(vector.periods) != window
            or len(set(vector.periods)) != window
            or set(vector.periods) != expected
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
        cached = sorted((item.site.name, item.site.url, item.site.pick) for item in vectors)
        current = sorted(
            (item.name, item.url, canonical_pick(item.pick))
            for item in configured
        )
        if cached != current:
            return []
    return vectors


def build_data_vector(
    name: str, url: str, pick: str, timeout: int = DEFAULT_TIMEOUT
) -> DataVector | None:
    expected = list(range(TARGET_PERIOD, TARGET_PERIOD - WINDOW_SIZE, -1))
    values: list[str] = []
    try:
        with crawl_site.site_lock_for(url):
            for period in expected:
                records = crawl_site.collect_site_records(
                    url, name, pick=pick, timeout=timeout, target_period=period
                )
                record, _ = crawl_site.select_current_record(records, period, pick)
                if not is_valid_tail_record(record) and not record.value_text:
                    raise LookupError(f"{period}期字段不是有效尾数据")
                values.append(record_value(record))
    except Exception as exc:
        raise RuntimeError(f"抓取/解析失败: {type(exc).__name__}: {exc}") from exc
    return DataVector(
        Site(name, url, pick),
        tuple(expected),
        tuple(values),
        0,
    )


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


def build_all_vectors(
    sites: list[Site], timeout: int, workers: int
) -> list[SiteResult]:
    total = len(sites)

    def build(index: int, site: Site) -> SiteResult:
        try:
            vector = build_data_vector(site.name, site.url, site.pick, timeout)
        except Exception as exc:
            return SiteResult(
                index,
                None,
                f"失败 {site.name} {site.url} 原因: 构建数据向量失败({exc})",
            )
        if vector is None:
            return SiteResult(
                index, None, f"失败 {site.name} {site.url} 原因: 近{WINDOW_SIZE}期无可用数据"
            )
        return SiteResult(index, vector, None)

    indexed = list(enumerate(sites, start=1))
    worker_count = max(1, min(workers, total or 1))
    if worker_count == 1:
        return [build(index, site) for index, site in indexed]
    results: list[SiteResult] = []
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(build, index, site) for index, site in indexed]
        for future in as_completed(futures):
            results.append(future.result())
    return results


def group_matches(matches: list[ConsecutiveMatch]) -> list[list[Site]]:
    all_sites: dict[str, Site] = {}
    graph: dict[str, set[str]] = defaultdict(set)
    for match in matches:
        all_sites[match.site_a.url] = match.site_a
        all_sites[match.site_b.url] = match.site_b
        graph[match.site_a.url].add(match.site_b.url)
        graph[match.site_b.url].add(match.site_a.url)
    groups: list[list[Site]] = []
    seen: set[str] = set()
    for start in all_sites:
        if start in seen:
            continue
        stack = [start]
        component: list[Site] = []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            component.append(all_sites[current])
            stack.extend(graph[current] - seen)
        if len(component) >= 2:
            groups.append(component)
    return groups


def format_output(
    matches: list[ConsecutiveMatch], fail_lines: list[str]
) -> tuple[list[str], list[str]]:
    duplicate_matches = [match for match in matches if match.level == "duplicate"]
    suspect_matches = [match for match in matches if match.level == "suspect"]
    lines = [
        f"检测窗口: 从{TARGET_PERIOD}期往前{WINDOW_SIZE}期（每站必须完整覆盖）",
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
    window: int = WINDOW_SIZE,
    consecutive: int = CONSECUTIVE_REQUIRED,
    timeout: int = DEFAULT_TIMEOUT,
    workers: int = DEFAULT_WORKERS,
    output: str | None = None,
    fail_output: str | None = None,
    recent_cache: str | None = None,
    use_recent_cache: bool = True,
    write_cache: bool = False,
    cache_only: bool = False,
) -> int:
    global TARGET_PERIOD, WINDOW_SIZE, CONSECUTIVE_REQUIRED, DUPLICATE_MIN_CONSECUTIVE
    if consecutive > window:
        return 2
    # Consecutive duplicate checks are an admission/reporting consumer of the
    # daily cache. They must never become a second live crawler or cache writer.
    if not use_recent_cache or write_cache:
        return 2
    sites = configured_sites()
    cache_path = Path(recent_cache) if recent_cache else RECENT_CACHE_PATH
    if not cache_path.is_absolute():
        cache_path = RECENT_CACHE_PATH.parent / cache_path

    if period == 0:
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8-sig"))
            period = int(payload["period"])
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return 1
    TARGET_PERIOD = period
    WINDOW_SIZE = window
    CONSECUTIVE_REQUIRED = consecutive
    DUPLICATE_MIN_CONSECUTIVE = consecutive

    cached = load_recent_cache(cache_path, period, window, sites) if use_recent_cache else []
    if cached:
        cached_urls = {vector.site.url for vector in cached}
        if any(site.url not in cached_urls for site in sites):
            return 1
        index_by_url = {site.url: index for index, site in enumerate(sites, start=1)}
        site_results = [
            SiteResult(index_by_url[vector.site.url], vector, None) for vector in cached
        ]
        vectors = cached
        fail_lines: list[str] = []
    else:
        return 1

    if cache_only:
        return 2

    matches = [
        match
        for left in range(len(vectors))
        for right in range(left + 1, len(vectors))
        if (match := find_consecutive_overlap(vectors[left], vectors[right])) is not None
    ]
    output_lines, _ = format_output(matches, fail_lines)
    result_path = Path(output) if output else OUTPUT_DIR / f"{period}期连续重复检测.txt"
    if not result_path.is_absolute():
        result_path = OUTPUT_DIR / result_path
    atomic_write_text(result_path, "\n".join(output_lines) + "\n", encoding="utf-8-sig")
    if fail_lines:
        failure_path = (
            Path(fail_output)
            if fail_output
            else FAIL_OUTPUT_DIR / f"{period}期连续重复检测_失败.txt"
        )
        if not failure_path.is_absolute():
            failure_path = FAIL_OUTPUT_DIR / failure_path
        atomic_write_text(
            failure_path, format_failure_records(fail_lines), encoding="utf-8-sig"
        )
    update_site_health(
        {index: site for index, site in enumerate(sites, start=1)}, site_results
    )
    return 0
