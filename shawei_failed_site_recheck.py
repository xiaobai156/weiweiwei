"""按当期失败 TXT 定向重抓，绝不启动全站抓取。"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from shawei.config.sites import load_sites
from shawei.config.paths import FAIL_OUTPUT_DIR, OUTPUT_DIR
from shawei.persistence import txt_writer
from shawei.persistence.atomic_file import atomic_write_text
from shawei.services.crawl_site import crawl_current_site


FAIL_RE = re.compile(
    r"^失败 (?P<name>.+?) (?P<url>https?://\S+) 方向: (?P<pick>top|bottom) "
    r"期数: (?P<period>\d+) 阶段: .+? 原因: (?P<reason>.*)$"
)


def _failure_blocks(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8-sig")
    return [block.strip() for block in re.split(r"(?:\r?\n){2,}", text.strip()) if block.strip()]


def _read_existing_successes_strict(path: Path):
    """Treat an unreadable existing success file as a hard write barrier."""
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        raise RuntimeError(f"成功TXT读取失败，拒绝覆盖: {path}")
    existing = {}
    for line in lines:
        parsed = txt_writer.parse_success_line(line)
        if parsed is not None:
            existing[parsed[0]] = (parsed[1], parsed[2])
    return existing


def _targets(path: Path, period: int, sites):
    by_identity = {(site.name, site.url, site.pick): site for site in sites}
    targets = []
    for block in _failure_blocks(path):
        match = FAIL_RE.match(block.splitlines()[0].strip())
        if not match or int(match["period"]) != period:
            continue
        site = by_identity.get((match["name"], match["url"], match["pick"]))
        if site is not None:
            targets.append(site)
    return targets


def recheck_failed(period: int, timeout: int = 8, workers: int = 1) -> int:
    success_path = OUTPUT_DIR / f"{period}期-尾.txt"
    failure_path = FAIL_OUTPUT_DIR / f"{period}期-尾-失败.txt"
    sites = load_sites()
    targets = _targets(failure_path, period, sites)
    if not targets:
        print(f"{period}期失败TXT没有可重抓站点")
        return 0

    results = [
        crawl_current_site(
            next(i for i, site in enumerate(sites, 1) if site is target),
            len(sites), target, period, max(1, timeout), retries=1,
        )
        for target in targets
    ]
    try:
        existing = _read_existing_successes_strict(success_path)
    except RuntimeError as exc:
        print(str(exc))
        return 2
    passed = [result for result in results if result.success_line]
    for result in passed:
        name = sites[result.index - 1].name
        existing[name] = (result.success_line, result.ranking_value)
    lines = [line for line, _ in existing.values()]
    values = [value for _, value in existing.values()]
    atomic_write_text(success_path, "\n".join(txt_writer.format_ranking(lines, values)) + "\n", encoding="utf-8-sig")

    passed_keys = {
        (sites[result.index - 1].name, sites[result.index - 1].url,
         sites[result.index - 1].pick, period)
        for result in passed
    }
    kept = []
    for block in _failure_blocks(failure_path):
        match = FAIL_RE.match(block.splitlines()[0].strip())
        key = (
            (match["name"], match["url"], match["pick"], int(match["period"]))
            if match else None
        )
        if key not in passed_keys:
            kept.append(block)
    txt_writer.write_optional_fail_file(failure_path, kept)
    print(f"定向重抓完成: 目标 {len(targets)}，成功 {len(passed)}，仍失败 {len(targets) - len(passed)}")
    return 0 if len(passed) == len(targets) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="只重抓当期失败 TXT 中的站点")
    parser.add_argument("--period", required=True, type=int)
    parser.add_argument("--timeout", default=8, type=int)
    parser.add_argument("--workers", default=1, type=int, help="保留参数；定向站点逐站执行")
    args = parser.parse_args()
    return recheck_failed(args.period, args.timeout, args.workers)


if __name__ == "__main__":
    raise SystemExit(main())
