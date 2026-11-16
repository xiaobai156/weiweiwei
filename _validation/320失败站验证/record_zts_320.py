"""按用户确认的取值补录张天师 320 期（页面本身无 320 行，值为用户核对结果）。

只做两件事：写成功 TXT（重算排行）+ 定向更新缓存里张天师 320 期。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.config.paths import FAIL_OUTPUT_DIR, OUTPUT_DIR, RECENT_CACHE_PATH  # noqa: E402
from shawei.config.sites import load_sites  # noqa: E402
from shawei.domain.models import CurrentRunResult  # noqa: E402
from shawei.persistence import cache_repository, txt_writer  # noqa: E402
from shawei.persistence.atomic_file import atomic_write_text  # noqa: E402

PERIOD = 320
NAME = "张天师"
VALUE = "2"
LINE = f"2尾 {NAME}"


def read_successes(path: Path) -> dict[str, tuple[str, str]]:
    existing: dict[str, tuple[str, str]] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        parsed = txt_writer.parse_success_line(line)
        if parsed is not None:
            existing[parsed[0]] = (parsed[1], parsed[2])
    return existing


def main() -> int:
    success_path = OUTPUT_DIR / f"{PERIOD}期-尾.txt"
    existing = read_successes(success_path)
    print(f"现有站点行 {len(existing)}，目标站当前值 {existing.get(NAME)}")
    existing[NAME] = (LINE, VALUE)
    lines = [line for line, _ in existing.values()]
    values = [value for _, value in existing.values()]
    atomic_write_text(
        success_path,
        "\n".join(txt_writer.format_ranking(lines, values)) + "\n",
        encoding="utf-8-sig",
    )
    print(f"已写成功TXT: {success_path}")

    sites = load_sites(ROOT / "sites.json")
    index = next(
        (i for i, site in enumerate(sites, 1) if site.name == NAME),
        None,
    )
    if index is None:
        print("缓存更新失败: sites.json 找不到该站")
        return 1
    site = sites[index - 1]
    result = CurrentRunResult(
        index=index,
        success_line=LINE,
        fail_line=None,
        ranking_value=VALUE,
        messages=[f"用户核对补录: {NAME} {PERIOD}期 {VALUE}尾"],
        failure_stage="",
        failure_reason="",
    )
    ok = cache_repository.update_recent_cache_for_targeted_sites(
        RECENT_CACHE_PATH, PERIOD, sites, [result]
    )
    print("缓存更新:", ok)

    failure_path = FAIL_OUTPUT_DIR / f"{PERIOD}期-尾-失败.txt"
    kept = [
        block
        for block in (
            failure_path.read_text(encoding="utf-8-sig").strip().split("\n\n")
            if failure_path.exists()
            else []
        )
        if block.strip() and NAME not in block.splitlines()[0]
    ]
    txt_writer.write_optional_fail_file(failure_path, [b.strip() for b in kept])
    print("失败TXT剩余:", failure_path.exists())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
