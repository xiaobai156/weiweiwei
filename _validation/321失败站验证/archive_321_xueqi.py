"""封存 血气方刚：sites.json 文本级拼接加 archived，保留 CRLF 与空行。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "sites.json"
TARGET = "血气方刚"


def detect_nl(text: str) -> str:
    for nl in ("\r\r\n", "\r\n", "\n"):
        if nl in text:
            return nl
    return "\n"


def main() -> None:
    raw = PATH.read_bytes()
    text = PATH.open("r", encoding="utf-8-sig", newline="").read()
    nl = detect_nl(text)
    needle = f'"name": "{TARGET}"'
    start = text.index(needle)
    obj_start = text.rindex("{", 0, start)
    obj_end = text.index("}", start) + 1
    block = text[obj_start:obj_end]
    if '"archived"' in block:
        print("已经封存，无需重复")
        return
    pick_at = text.rindex('"pick"', start, obj_end)
    line_end = text.index(nl, pick_at)
    insertion = nl + nl + "    " + '"archived": true'
    new_text = text[:line_end] + "," + insertion + nl + "  }" + text[obj_end:]
    PATH.open("w", encoding="utf-8", newline="").write(new_text)
    print("原字节", len(raw), "→ 新字节", len(PATH.read_bytes()))
    print("条块预览:", repr(text[obj_start:obj_end]))


if __name__ == "__main__":
    sys.exit(main())
