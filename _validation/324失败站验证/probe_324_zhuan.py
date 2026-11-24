"""324 转嗔为喜取证：站点列表里该站是否换了文章 ID。"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent
BASE = "https://djimkyw.n7ht1-wp4vm-ljitjr.xyz:29488"
TARGET = f"{BASE}/article/manager/6a329f1573fa32d0b73c0ca0?url=cmzj"


def fetch(url: str) -> tuple[str, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read()
        for enc in ("utf-8", "gb18030"):
            try:
                return "ok", raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return "ok", raw.decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}: {exc}", ""


def main() -> None:
    report: dict[str, object] = {}
    for path in ["/", "/article", "/article/manager"]:
        status, text = fetch(BASE + path)
        print(f"{BASE + path} -> {status} {len(text)} 字符")
        report[path] = {"status": status, "len": len(text)}
        if "转嗔为喜" in text:
            for m in re.finditer("转嗔为喜", text):
                seg = text[max(0, m.start() - 260) : m.start() + 60]
                ids = re.findall(r"6a[0-9a-f]{22}", seg)
                print("   找到 转嗔为喜, 附近 id:", ids[-3:] if ids else "无")
                report.setdefault("hits", []).append({"path": path, "ids": ids[-3:]})

    status, text = fetch(TARGET)
    print(f"目标页 -> {status} {len(text)} 字符 | 解密盛典 {text.count('解密盛典')} | 转嗔为喜 {text.count('转嗔为喜')}")
    (OUT / "probe_324_zhuan.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
