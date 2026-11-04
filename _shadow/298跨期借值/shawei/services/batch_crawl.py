from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import time
from typing import Iterable

from shawei.config.rules import SAME_PERIOD_RECORD_SELECTION_URLS
from shawei.domain.models import CurrentRunResult, SiteLike
from shawei.services.crawl_site import crawl_current_site


SiteRunResult = CurrentRunResult


def _write_progress(
    completed: int,
    total: int,
    successes: int,
    failures: int,
    started_at: float,
    current_name: str,
    final: bool = False,
) -> None:
    percent = int(completed * 100 / total) if total else 100
    elapsed = time.monotonic() - started_at
    line = (
        f"[进度 {completed}/{total} {percent}% 成功 {successes} "
        f"失败 {failures} 用时 {elapsed:.1f}s] 当前：{current_name}"
    )
    sys.stdout.write("\r" + line + ("\n" if final else ""))
    sys.stdout.flush()


def crawl_indexed_sites(
    indexed_sites: Iterable[tuple[int, SiteLike]],
    total: int,
    period: int,
    timeout: int,
    retries: int = 1,
    workers: int = 8,
    show_progress: bool = False,
) -> list[CurrentRunResult]:
    indexed_sites = list(indexed_sites)
    if not indexed_sites:
        return []
    worker_count = max(1, min(int(workers or 1), total))
    results: list[CurrentRunResult] = []
    progress_total = len(indexed_sites)
    started_at = time.monotonic()
    completed = 0
    successes = 0
    failures = 0
    if show_progress:
        _write_progress(0, progress_total, 0, 0, started_at, "准备中")
    priority_sites = [
        item for item in indexed_sites if item[1].url in SAME_PERIOD_RECORD_SELECTION_URLS
    ]
    regular_sites = [
        item for item in indexed_sites if item[1].url not in SAME_PERIOD_RECORD_SELECTION_URLS
    ]
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        # Submit the next phase only after the special-site phase has fully
        # completed.  This preserves the requested priority without changing
        # result ordering or the per-site worker behavior.
        for site_group in (priority_sites, regular_sites):
            pending = {
                executor.submit(
                    crawl_current_site,
                    index,
                    total,
                    site,
                    period,
                    timeout,
                    retries=retries,
                ): (index, site)
                for index, site in site_group
            }
            for future in as_completed(pending):
                index, site = pending[future]
                try:
                    result = future.result()
                except Exception as exc:
                    reason = f"{type(exc).__name__}: {exc}"
                    result = CurrentRunResult(
                        index=index,
                        success_line=None,
                        fail_line=(
                            f"失败 {site.name} {site.url} 方向: {site.pick} "
                            f"期数: {period} 阶段: 批量编排 原因: {reason}"
                        ),
                        ranking_value=None,
                        messages=[
                            f"[{index}/{total}] {site.name} {site.pick} {site.url}",
                            f"  失败: {reason}",
                        ],
                        failure_stage="批量编排",
                        failure_reason=reason,
                    )
                results.append(result)
                completed += 1
                if result.success_line:
                    successes += 1
                else:
                    failures += 1
                if show_progress:
                    _write_progress(
                        completed,
                        progress_total,
                        successes,
                        failures,
                        started_at,
                        site.name,
                        final=completed == progress_total,
                    )
    return sorted(results, key=lambda result: result.index)
