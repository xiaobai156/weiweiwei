from __future__ import annotations

import argparse
import sys

from shawei.config import sites as site_config
from shawei.config.paths import RECENT_CACHE_PATH
from shawei.persistence import cache_repository, health_repository, txt_writer
from shawei.persistence.atomic_file import atomic_write_text
from shawei.services import batch_crawl


def should_update_cache(success_count: int, total_sites: int) -> bool:
    """Allow a cache roll for any valid finalized live-result count."""
    if total_sites <= 0 or success_count < 0 or success_count > total_sites:
        return False
    return True


def _result_matches_site(site, result) -> bool:
    if result.success_line:
        if result.fail_line or not result.ranking_value:
            return False
        parsed = txt_writer.parse_success_line(result.success_line)
        return bool(
            parsed
            and parsed[0] == site.name
            and parsed[2] == result.ranking_value
        )
    return bool(result.fail_line) and result.ranking_value is None


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
        show_progress=True,
    )


def _write_outputs(period: int, args: argparse.Namespace, results):
    default_success, default_failure = txt_writer.default_current_output_names(period)
    success_path = txt_writer.resolve_success_path(args.success or default_success)
    failure_path = txt_writer.resolve_failure_path(args.fail or default_failure)
    success_lines = [result.success_line for result in results if result.success_line]
    ranking_values = [
        result.ranking_value
        for result in results
        if result.success_line and result.ranking_value
    ]
    failure_lines = [result.fail_line for result in results if result.fail_line]
    ranked = txt_writer.format_single_period_success(success_lines, ranking_values)
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
    results = _crawl(indexed, len(sites), args, args.retries, max(1, args.workers))
    if len(results) != len(sites):
        print("批量抓取结果不完整、重复或索引越界，拒绝覆盖正式输出", file=sys.stderr)
        return 1
    result_indexes: list[int] = []
    for result in results:
        index = getattr(result, "index", None)
        if type(index) is not int:
            print("批量抓取结果不完整、重复或索引越界，拒绝覆盖正式输出", file=sys.stderr)
            return 1
        result_indexes.append(index)
    if sorted(result_indexes) != list(range(1, len(sites) + 1)):
        print("批量抓取结果不完整、重复或索引越界，拒绝覆盖正式输出", file=sys.stderr)
        return 1
    ordered = sorted(results, key=lambda result: result.index)
    if any(
        not _result_matches_site(site, result)
        for site, result in zip(sites, ordered)
    ):
        print("批量抓取结果字段矛盾或站点身份不匹配，拒绝覆盖正式输出", file=sys.stderr)
        return 1
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
        print("最近10期缓存: 实时结果计数无效，本次不更新")
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
