"""328 期：封存 澳彩碼王（https://12388990827.794555.xyz/bbs/topic.php?id=19959）。

sites.json 原文是 CRLF 双倍（字段间以 \\r\\r\\n 铺空行）、无 BOM；
只能用文本级替换，且写回时不能改变编码与换行，否则整文件 diff 虚报。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PATH = ROOT / "sites.json"
NAME = "澳彩碼王"
URL = "https://12388990827.794555.xyz/bbs/topic.php?id=19959"
TAIL = "\r\r\n\r\r\n\r\r\n\r\r\n\r\r\n  }"
TAIL_ARCHIVED = (
    "\r\r\n\r\r\n\r\r\n\r\r\n\r\r\n    \"archived\": true" + TAIL
)


def main() -> None:
    raw = PATH.open("r", encoding="utf-8", newline="").read()
    before = len(raw.encode("utf-8"))

    needle = f'"name": "{NAME}"'
    indices = [i for i in range(len(raw)) if raw.startswith(needle, i)]
    if len(indices) != 1:
        raise SystemExit(f"站点名命中 {len(indices)} 处，需唯一: {NAME}")
    start = indices[0]
    seg_start = raw.rindex("{", 0, start)
    seg_end = raw.index("}", start) + 1
    segment = raw[seg_start:seg_end]
    if URL not in segment:
        raise SystemExit(f"条块 URL 不匹配: {segment[:200]}")
    if '"archived"' in segment:
        raise SystemExit("该条已封存，无需重复操作")
    if not segment.endswith(TAIL):
        raise SystemExit(f"条块尾部格式与预期不同: {segment[-40:]!r}")

    new_segment = (
        segment[: -len(TAIL)].replace('    "pick": "bottom"', '    "pick": "bottom",', 1)
        + TAIL_ARCHIVED
    )
    raw = raw[:seg_start] + new_segment + raw[seg_end:]
    PATH.open("w", encoding="utf-8", newline="").write(raw)

    data = json.loads(PATH.open("r", encoding="utf-8", newline="").read())
    active = [e for e in data if not e.get("archived")]
    archived = [e for e in data if e.get("archived")]
    hit = [e for e in data if e.get("name") == NAME and e.get("url") == URL]
    after = len(raw.encode("utf-8"))
    print(f"字节 {before} -> {after}")
    print(f"总条目 {len(data)} | 活动 {len(active)} | 封存 {len(archived)}")
    print("目标条目:", json.dumps(hit, ensure_ascii=False))


if __name__ == "__main__":
    main()
