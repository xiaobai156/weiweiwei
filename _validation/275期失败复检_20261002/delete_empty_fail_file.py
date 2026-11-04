"""删除 275 期失败清单文件（已无数据项：唯一站潇洒人生已封存，不可重抓）。

走项目自带路径 txt_writer.write_optional_fail_file(path, [])：file_lock + unlink，
与真实「零失败跑批」收尾行为一致。只读校验其余正式文件未受影响。
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shawei.persistence.txt_writer import write_optional_fail_file  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT.parent
FAIL = OUT / "七类数据统一归纳失败" / "275期-尾-失败.txt"
WATCH = {
    "275期-尾.txt": OUT / "七类数据统一归纳" / "275期-尾.txt",
    "recent_10_cache.json": ROOT / "recent_10_cache.json",
    "sites.json": ROOT / "sites.json",
    "shawei_site_health.json": ROOT / "shawei_site_health.json",
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest().upper() if p.exists() else "<缺失>"


def main() -> int:
    if not FAIL.exists():
        print("失败文件本就不存在，无需删除")
        return 0
    before = {name: sha(p) for name, p in WATCH.items()}
    size = FAIL.stat().st_size
    head = FAIL.read_text(encoding="utf-8-sig").strip()
    print(f"待删文件 {FAIL.name}: {size} B，内容 {head!r}")

    existed = write_optional_fail_file(FAIL, [])
    print(f"write_optional_fail_file 返回 {existed}；删除后文件存在: {FAIL.exists()}")

    after = {name: sha(p) for name, p in WATCH.items()}
    for name in WATCH:
        flag = "一致" if before[name] == after[name] else "**已变化**"
        print(f"  {name}: {after[name][:16]}… {flag}")
    return 0 if not FAIL.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
