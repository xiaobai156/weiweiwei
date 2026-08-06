from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from shawei.config.paths import RECENT_CACHE_PATH
from shawei.config.sites import load_sites
from shawei.domain.models import Record
from shawei.domain.text import canonical_pick, normalize_text
from shawei.parsers.common import is_two_tail_site_url, is_valid_tail_record, record_value
from shawei.persistence.cache_repository import is_valid_result_value
from shawei.services import crawl_site


@dataclass(frozen=True)
class Site:
    name: str
    url: str
    pick: str = "top"


@dataclass(frozen=True)
class SiteFingerprint:
    site: Site
    fingerprint: tuple[str, ...]


@dataclass(frozen=True)
class AdmissionDuplicate:
    site: Site
    periods: tuple[int, ...]
    values: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class NewSiteAdmission:
    accepted: bool
    reason: str
    candidate: Site
    fingerprint: tuple[str, ...] | None = None
    duplicates: tuple[AdmissionDuplicate, ...] = ()
    fail_lines: tuple[str, ...] = ()
    suspicions: tuple[AdmissionDuplicate, ...] = ()


@dataclass(frozen=True)
class SiteCheckResult:
    index: int
    fingerprint: SiteFingerprint | None
    fail_line: str | None
    messages: list[str]


def configured_sites() -> list[Site]:
    return [Site(site.name, site.url, site.pick) for site in load_sites()]


def issue_window(period: int, periods: int) -> list[int]:
    if period <= 0:
        raise ValueError("当前期数必须大于 0")
    if periods <= 0:
        raise ValueError("对比期数必须大于 0")
    return list(range(period, period - periods, -1))


def load_recent_cache_vectors(
    path: Path = RECENT_CACHE_PATH, *, allow_incomplete: bool = False
) -> tuple[int, int, list[tuple[Site, dict[int, str]]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise LookupError(f"缺少最近10期缓存: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LookupError(f"最近10期缓存格式错误: {path}") from exc
    if not isinstance(payload, dict):
        raise LookupError(f"最近10期缓存格式错误: {path}")
    try:
        period = int(payload["period"])
        window = int(payload.get("window") or 10)
    except (KeyError, TypeError, ValueError) as exc:
        raise LookupError("最近10期缓存缺少有效 period/window") from exc
    if window != 10:
        raise LookupError("最近10期缓存的window必须为10")
    items = payload.get("sites")
    if not isinstance(items, list) or not items:
        raise LookupError("最近10期缓存没有有效站点数据")
    active_items = [item for item in items if isinstance(item, dict) and not item.get("archived")]
    if not active_items:
        raise LookupError("最近10期缓存没有有效活动站点数据")
    if payload.get("site_count") != len(active_items):
        raise LookupError("最近10期缓存活动站点数量与元数据不一致")
    if not allow_incomplete and (
        payload.get("fail_count") != 0
        or payload.get("site_count") != payload.get("vector_count")
    ):
        raise LookupError("最近10期缓存包含失败或站点数量不完整，不能作为新增判重依据")

    vectors: list[tuple[Site, dict[int, str]]] = []
    expected_periods = set(issue_window(period, window))
    incomplete_sites: list[str] = []
    cached_snapshot: list[tuple[str, str, str]] = []
    for item in active_items:
        name = str(item.get("name") or "")
        url = str(item.get("url") or "")
        pick = canonical_pick(str(item.get("pick") or "top"))
        if not name or not url:
            raise LookupError("最近10期缓存站点身份信息格式错误")
        cached_snapshot.append((name, url, pick))
        try:
            periods = [int(value) for value in item["periods"]]
            values = [str(value) for value in item["values"]]
        except (KeyError, TypeError, ValueError):
            incomplete_sites.append(name)
            continue
        if (
            len(periods) != len(values)
            or len(periods) != 10
            or len(set(periods)) != 10
            or item.get("failed_periods")
            or any(not is_valid_result_value(value, url) for value in values)
        ):
            incomplete_sites.append(name)
            continue
        period_values = dict(zip(periods, values))
        if set(period_values) != expected_periods:
            incomplete_sites.append(name)
            continue
        vectors.append((Site(name, url, pick), period_values))
    if not vectors:
        raise LookupError("最近10期缓存没有完整近10期向量，不能作为新增判重依据，请先全站刷新缓存")
    if incomplete_sites and not allow_incomplete:
        sample = "、".join(incomplete_sites[:5])
        suffix = "等" if len(incomplete_sites) > 5 else ""
        raise LookupError(
            f"最近10期缓存存在不完整站点: {sample}{suffix}，不能作为新增判重依据，请先全站刷新缓存"
        )
    if not allow_incomplete and payload.get("vector_count") != len(vectors):
        raise LookupError("最近10期缓存向量数量与元数据不一致，不能作为新增判重依据")
    cached_snapshot.sort()
    configured_snapshot = sorted(
        (site.name, site.url, canonical_pick(site.pick))
        for site in configured_sites()
    )
    if cached_snapshot != configured_snapshot:
        raise LookupError(
            "最近10期缓存与当前 sites.json 的 name/url/pick 配置快照不一致，请先全站刷新缓存"
        )
    return period, window, vectors


def find_existing_site(
    name: str, url: str, sites: list[Site] | None = None
) -> Site | None:
    normalized_name = normalize_text(name)
    normalized_url = (url or "").strip()
    for site in sites if sites is not None else configured_sites():
        if normalize_text(site.name) == normalized_name or site.url.strip() == normalized_url:
            return site
    return None


def fingerprint_from_records(
    records: list[Record], period: int, periods: int
) -> tuple[tuple[str, ...] | None, list[int]]:
    by_period = {record.period: record for record in records}
    wanted = issue_window(period, periods)
    missing = [item for item in wanted if item not in by_period]
    if missing:
        return None, missing
    invalid = [item for item in wanted if not is_valid_tail_record(by_period[item])]
    if invalid:
        return None, invalid
    return tuple(record_value(by_period[item]) for item in wanted), []


def period_values_from_records(
    records: list[Record], period: int, periods: int
) -> tuple[dict[int, str] | None, list[int]]:
    fingerprint, missing = fingerprint_from_records(records, period, periods)
    if fingerprint is None:
        return None, missing
    return dict(zip(issue_window(period, periods), fingerprint)), []


def _find_admission_matches(
    candidate_values: dict[int, str], existing: list[tuple[Site, dict[int, str]]]
) -> tuple[list[AdmissionDuplicate], list[AdmissionDuplicate]]:
    wanted = sorted(candidate_values, reverse=True)
    candidate_fingerprint = tuple(candidate_values[item] for item in wanted)
    duplicates: list[AdmissionDuplicate] = []
    suspicions: list[AdmissionDuplicate] = []

    def match(site: Site, periods: tuple[int, ...], reason: str) -> AdmissionDuplicate:
        return AdmissionDuplicate(
            site, periods, tuple(candidate_values[item] for item in periods), reason
        )

    for site, values in existing:
        if len(wanted) == 10 and all(period in values for period in wanted):
            if tuple(values[item] for item in wanted) == candidate_fingerprint:
                duplicates.append(match(site, tuple(wanted), "近10期原始排序完全重复"))
                continue
        runs: list[tuple[int, ...]] = []
        current: list[int] = []
        for period in wanted:
            same = period in values and values[period] == candidate_values[period]
            if same and (not current or current[-1] - period == 1):
                current.append(period)
                continue
            if current:
                runs.append(tuple(current))
            current = [period] if same else []
        if current:
            runs.append(tuple(current))
        hard_runs = [run for run in runs if len(run) >= 6]
        if hard_runs:
            duplicates.extend(match(site, run, f"连续{len(run)}期重复") for run in hard_runs)
            continue
        suspicions.extend(
            match(site, run, f"连续{len(run)}期相同，疑似重复，需人工确认")
            for run in runs
            if 3 <= len(run) <= 5
        )
    return duplicates, suspicions


def find_admission_duplicates(
    candidate_values: dict[int, str], existing: list[tuple[Site, dict[int, str]]]
) -> list[AdmissionDuplicate]:
    return _find_admission_matches(candidate_values, existing)[0]


def find_admission_suspicions(
    candidate_values: dict[int, str], existing: list[tuple[Site, dict[int, str]]]
) -> list[AdmissionDuplicate]:
    return _find_admission_matches(candidate_values, existing)[1]


def evaluate_new_site_admission(
    name: str,
    url: str,
    pick: str,
    period: int,
    periods: int = 10,
    timeout: int = 20,
    workers: int = 8,
) -> NewSiteAdmission:
    del workers
    pick = canonical_pick(pick)
    candidate = Site(name, url, pick)
    sites = configured_sites()
    if find_existing_site(name, url, sites):
        return NewSiteAdmission(False, "sites.json 已存在，拒收，不做后续操作", candidate)
    try:
        cache_period, cache_window, existing_values = load_recent_cache_vectors(
            allow_incomplete=True
        )
    except LookupError as exc:
        return NewSiteAdmission(False, str(exc), candidate)
    if period != cache_period:
        return NewSiteAdmission(
            False,
            f"新增站判重基准期必须使用 recent_10_cache.json 当前期号 {cache_period}，不能使用 {period}",
            candidate,
        )
    periods = min(periods, cache_window)
    wanted_periods = issue_window(period, periods)
    with crawl_site.site_lock_for(url):
        base_ok = False
        base_errors: list[str] = []
        for base_period in (cache_period, cache_period - 1):
            try:
                base_records = crawl_site.collect_site_records(
                    url, name, pick=pick, timeout=timeout, target_period=base_period
                )
            except Exception as exc:
                base_errors.append(f"{base_period}期:{type(exc).__name__}: {exc}")
                continue
            if any(
                record.period == base_period and is_valid_tail_record(record)
                for record in base_records
            ):
                base_ok = True
                break
            base_errors.append(f"{base_period}期: 没有找到有效数据")
        if not base_ok:
            return NewSiteAdmission(
                False,
                "新增站必须能按指定方向抓到 recent_10_cache.json 最新期或上一期: "
                + "；".join(base_errors),
                candidate,
            )
        candidate_records = crawl_site.collect_site_records(
            url, name, pick=pick, timeout=timeout
        )
        available = {
            record.period for record in candidate_records if is_valid_tail_record(record)
        }
        validated: dict[int, str] = {}
        errors: list[str] = []
        for target in wanted_periods:
            try:
                target_records = crawl_site.collect_site_records(
                    url, name, pick=pick, timeout=timeout, target_period=target
                )
            except Exception as exc:
                if target in available:
                    errors.append(f"{target}期:{type(exc).__name__}: {exc}")
                continue
            valid = [
                record
                for record in target_records
                if record.period == target and is_valid_tail_record(record)
            ]
            if len(valid) != 1:
                if target in available:
                    errors.append(f"{target}期: 没有唯一有效数据")
                continue
            validated[target] = record_value(valid[0])
        if errors:
            return NewSiteAdmission(
                False, "新增站逐期精准校验失败: " + "；".join(errors), candidate
            )
    missing = [item for item in wanted_periods if item not in validated]
    if not validated:
        return NewSiteAdmission(
            False,
            "新增站没有可用的真实数据: " + "、".join(f"{item}期" for item in missing),
            candidate,
        )
    candidate_two_tail = is_two_tail_site_url(candidate.url)
    scoped_existing = [
        item
        for item in existing_values
        if is_two_tail_site_url(item[0].url) == candidate_two_tail
    ]
    duplicates, suspicions = _find_admission_matches(validated, scoped_existing)
    fingerprint = tuple(validated[item] for item in wanted_periods if item in validated)
    if duplicates:
        return NewSiteAdmission(
            False,
            "新增站与缓存现有目标硬重复，拒收",
            candidate,
            fingerprint,
            tuple(duplicates),
        )
    if suspicions:
        return NewSiteAdmission(
            False,
            "新增站连续3-5期相同，属于疑似重复，需要人工确认",
            candidate,
            fingerprint,
            suspicions=tuple(suspicions),
        )
    detail = f"真实有效{len(validated)}期"
    if missing:
        detail += "，缺少" + "、".join(f"{item}期" for item in missing)
    return NewSiteAdmission(
        True, f"新增站{detail}且不重复，可添加后抽抓验证", candidate, fingerprint
    )


def group_duplicate_sites(items: list[SiteFingerprint]) -> list[list[Site]]:
    groups: dict[tuple[bool, tuple[str, ...]], list[Site]] = defaultdict(list)
    seen: dict[tuple[bool, tuple[str, ...]], set[str]] = defaultdict(set)
    for item in items:
        key = (is_two_tail_site_url(item.site.url), item.fingerprint)
        if item.site.url not in seen[key]:
            seen[key].add(item.site.url)
            groups[key].append(item.site)
    return [sites for sites in groups.values() if len(sites) >= 2]


def format_duplicate_groups(groups: list[list[Site]]) -> list[str]:
    lines: list[str] = []
    for index, sites in enumerate(groups, start=1):
        if lines:
            lines.append("")
        lines.append(f"重复组{index}")
        lines.extend(site.name for site in sites)
    return lines
