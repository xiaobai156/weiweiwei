"""324 寻宝探码取证：HTTP 500 是站方删帖还是临时故障。"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent
TARGET = "https://12388990827.688756.xyz/bbs/topic.php?id=19155"
SIBLINGS = [
    "https://12388990827.688756.xyz/bbs/topic.php?id=19128",
    "https://12388990827.688756.xyz/bbs/topic.php?id=19127",
    "https://12388990827.688756.xyz/bbs/index.php",
    "https://12388990827.688756.xyz/bbs/",
]


def fetch(url: str, tries: int = 3) -> tuple[int | str, str]:
    last = ""
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as resp:
                raw = resp.read()
            for enc in ("utf-8", "gb18030"):
                try:
                    return resp.status, raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return resp.status, raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body = exc.read()
            for enc in ("utf-8", "gb18030"):
                try:
                    last = f"HTTP {exc.code}: " + body.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                last = f"HTTP {exc.code}"
            if exc.code == 500:
                continue
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
    return "ERR", last


def main() -> None:
    report = {}
    for url in [TARGET, *SIBLINGS]:
        status, text = fetch(url)
        report[url] = {"status": str(status), "len": len(text), "head": text[:300]}
        print(f"\n=== {url} -> {status} {len(text)} 字符 ===")
        print("  ", text[:200].replace("\n", " "))
    (OUT / "probe_324_xunbao.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
