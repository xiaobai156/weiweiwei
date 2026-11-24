"""328 期：封存后按 AGENTS.md:51 规则删掉失败 TXT 里该站当期记录（清零则文件整体删除）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

FAIL_PATH = ROOT.parent / "七类数据统一归纳失败" / "328期-尾-失败.txt"
TARGET = "澳彩碼王"


def main() -> None:
    from shawei.persistence.txt_writer import write_optional_fail_file

    text = FAIL_PATH.read_text(encoding="utf-8-sig")
    lines = [line for line in text.splitlines() if line.strip()]
    kept = [line for line in lines if TARGET not in line]
    removed = len(lines) - len(kept)
    print(f"原 {len(lines)} 条，删除 {removed} 条，保留 {len(kept)} 条")
    for line in kept:
        print("  保留:", line[:120])
    kept_file = write_optional_fail_file(FAIL_PATH, kept)
    print("失败文件仍存在:", kept_file, "| 路径存在:", FAIL_PATH.exists())


if __name__ == "__main__":
    main()
