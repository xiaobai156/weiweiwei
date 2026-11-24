"""324 转嗔为喜：直接问站方接口，这个文章 ID 归属哪个站。"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent
BASE = "https://djimkyw.n7ht1-wp4vm-ljitjr.xyz:29488"
ARTICLE_ID = "6a329f1573fa32d0b73c0ca0"
CANDIDATES = [
    f"{BASE}/api/manager/article/{ARTICLE_ID}",
    f"{BASE}/api/manager/articles/{ARTICLE_ID}",
    f"{BASE}/api/article/{ARTICLE_ID}",
    f"{BASE}/api/admin/article/{ARTICLE_ID}",
    f"{BASE}/api/manager/article?id={ARTICLE_ID}",
    f"{BASE}/api/articles/{ARTICLE_ID}",
]


def get(url: str) -> tuple[str, str]:
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            return f"HTTP {resp.status}", resp.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        body = ""
        if hasattr(exc, "read"):
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                body = ""
        return f"{type(exc).__name__}: {exc}", body


def main() -> None:
    report = {}
    for url in CANDIDATES:
        status, text = get(url)
        ok = "HTTP 200" in status and len(text) > 40
        print(f"\n{url}\n  -> {status} | {len(text)} 字符")
        if text:
            print("  ", text[:260].replace("\n", " "))
        report[url] = {"status": status, "len": len(text), "head": text[:400]}
        if ok:
            break
    (OUT / "probe_324_zhuan_api.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
