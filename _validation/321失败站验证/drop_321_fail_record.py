"""321 封存后：从失败 TXT 删除血气方刚当条，清零时文件整体删除。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.persistence.txt_writer import write_optional_fail_file  # noqa: E402

FAIL = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\七类数据统一归纳失败\321期-尾-失败.txt")
TARGET = "血气方刚"


def main() -> None:
    if not FAIL.exists():
        print("失败 TXT 不存在，无需处理")
        return
    lines = FAIL.read_text(encoding="utf-8-sig").splitlines()
    kept = [line for line in lines if line.strip() and TARGET not in line]
    removed = len([line for line in lines if line.strip() and TARGET in line])
    print("原条数", len([l for l in lines if l.strip()]), "删除", removed, "保留", len(kept))
    for line in kept:
        print("  保留:", line[:70])
    exists = write_optional_fail_file(FAIL, kept)
    print("文件仍存在:", exists, "| 路径存在:", FAIL.exists())


if __name__ == "__main__":
    main()
