from __future__ import annotations

import argparse
import sys
import time

from shawei.config import sites as site_config
from shawei.config.paths import RECENT_CACHE_PATH
from shawei.persistence import cache_repository, health_repository, txt_writer
from shawei.persistence.atomic_file import atomic_write_text
from shawei.services import batch_crawl


CACHE_UPDATE_SUCCESS_PERCENT = 85


def should_update_cache(success_count: int, total_sites: int) -> bool:
    """Allow a cache roll only when the live success ratio is strictly above 85%."""
    if total_sites <= 0 or success_count < 0:
        return False
    return success_count * 100 > total_sites * CACHE_UPDATE_SUCCESS_PERCENT


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="抓取杀尾当期数据。")
    parser.add_argument("--period", required=True, type=int, help="当前期数，例如 125")
    parser.add_argument("--success", default=None, help="成功结果文件")
    parser.add_argument("--fail", default=None, help="失败结果文件")
    parser.add_argument("--timeout", default=8, type=int)
    parser.add_argument("--workers", default=8, type=int)
    # Boundary mismatches can come from a stale HTTP/browser response.  The
    # crawler clears the URL cache before this retry; a genuinely newer page
    # still fails the absolute top/bottom boundary check.
    parser.add_argument("--retries", default=1, type=int)
    parser.add_argument("--missing-retries", default=2, type=int)
    parser.add_argument("--missing-retry-delay", default=2, type=int)
    parser.add_argument("--retry-failed-delay", default=0, type=int)
    parser.add_argument("--retry-failed-workers", default=4, type=int)
    parser.add_argument("--no-retry-failed", action="store_true", default=True)
    parser.add_argument("--retry-failed", action="store_false", dest="no_retry_failed")
    parser.add_argument("--no-update-cache", action="store_true")
    return parser.parse_args(argv)


def _crawl(
    indexed_sites,
    total: int,
    args: argparse.Namespace,
    retries: int,
    workers: int,
):
    return batch_crawl.crawl_indexed_sites(
        indexed_sites,
        total,
        args.period,
        args.timeout,
        retries=retries,
        workers=workers,
        missing_retries=args.missing_retries,
        missing_retry_delay=args.missing_retry_delay,
        show_progress=True,
    )


def _write_outputs(period: int, args: argparse.Namespace, results):
    default_success, default_failure = txt_writer.default_current_output_names(period)
    success_path = txt_writer.resolve_success_path(args.success or default_success)
    failure_path = txt_writer.resolve_failure_path(args.fail or default_failure)
    success_lines = [result.success_line for result in results if result.success_line]
    ranking_values = [result.ranking_value for result in results if result.ranking_value]
    failure_lines = [result.fail_line for result in results if result.fail_line]
    ranked = txt_writer.format_ranking(success_lines, ranking_values)
    atomic_write_text(
        success_path,
        "\n".join(ranked) + ("\n" if ranked else ""),
        encoding="utf-8-sig",
    )
    wrote_failure = txt_writer.write_optional_fail_file(failure_path, failure_lines)
    return success_path, failure_path, wrote_failure, success_lines, failure_lines


def _update_cache_after_realtime_outputs(period: int, sites, results) -> bool:
    """Persist the finalized live results without changing their judgement."""
    try:
        updated = cache_repository.update_recent_cache_from_current_results(
            RECENT_CACHE_PATH, period, sites, results
        )
    except Exception as exc:  # cache persistence is a separate post-run phase
        print(
            f"最近10期缓存更新失败: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return False
    return bool(updated)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")
    args = parse_args(argv)
    if args.period <= 0:
        print("参数错误: 当前期数必须大于 0", file=sys.stderr)
        return 2

    sites = site_config.load_sites()
    indexed = list(enumerate(sites, start=1))
    # The live crawl and unified validation decide success/failure from this
    # run's documents only; the disk cache is not consulted in this phase.
    results_by_index = {
        result.index: result
        for result in _crawl(indexed, len(sites), args, args.retries, max(1, args.workers))
    }

    if not args.no_retry_failed:
        failed_indexes = sorted(
            index
            for index, result in results_by_index.items()
            if result.fail_line and txt_writer.is_retryable_failure_line(result.fail_line)
        )
        if failed_indexes:
            delay = max(0, int(args.retry_failed_delay or 0))
            print(f"\n失败站点二次补跑: {len(failed_indexes)} 条")
            if delay:
                print(f"等待 {delay} 秒后开始补跑...")
                time.sleep(delay)
            retry_sites = [(index, sites[index - 1]) for index in failed_indexes]
            for result in _crawl(
                retry_sites,
                len(sites),
                args,
                max(args.retries, 1),
                max(1, args.retry_failed_workers),
            ):
                results_by_index[result.index] = result

    ordered = [results_by_index[index] for index in sorted(results_by_index)]
    # Finalize the current run's TXT outputs before any cache persistence.
    success_path, failure_path, wrote_failure, successes, failures = _write_outputs(
        args.period, args, ordered
    )
    health_repository.update_site_health(
        {index: site for index, site in enumerate(sites, start=1)}, ordered
    )

    print(f"\n完成: 成功 {len(successes)} 条, 失败 {len(failures)} 条")
    for line in txt_writer.format_failure_summary(failures):
        print(line)
    print(f"成功结果: {success_path}")
    print(f"失败结果: {failure_path}" if wrote_failure else "失败结果: 无失败，不生成失败文件")
    if args.no_update_cache:
        print("最近10期缓存: 本次按参数要求不更新")
        return 0
    if not should_update_cache(len(successes), len(sites)):
        success_percent = (len(successes) / len(sites) * 100) if sites else 0
        print(
            f"最近10期缓存: 成功 {len(successes)}/{len(sites)} "
            f"({success_percent:.2f}%) 未超过85%，本次不更新"
        )
        return 0
    # Cache is updated only after realtime judgement/output is complete.  It
    # is used for new-site duplicate detection, never to alter this run.  The
    # cache repository records failed sites in JSON when this gate is passed;
    # health JSON is updated above regardless of this gate.
    if not _update_cache_after_realtime_outputs(args.period, sites, ordered):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
