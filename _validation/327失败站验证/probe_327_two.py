"""327 白杨金牌 / 热血风云：确认是 503 限流还是页面真没有 327 行。"""

from __future__ import annotations

import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent
URLS = {
    "白杨金牌": "https://4.48kk49.com:1888/Article/ar_content/id/1556/tid/82.html",
    "热血风云": "https://4.48kk49.com:1888/Article/ar_content/id/1452/tid/82.html",
}


def fetch(url: str, tries: int = 4, wait: int = 8) -> tuple[str, str]:
    last = ""
    for attempt in range(tries):
        if attempt:
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
            for enc in ("utf-8", "gb18030"):
                try:
                    return "ok", raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return "ok", raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
    return last, ""


def main() -> None:
    for name, url in URLS.items():
        status, html = fetch(url)
        print(f"\n=== {name} -> {status} {len(html)} 字符")
        if not html:
            continue
        (OUT / f"raw_{name}.html").write_text(html, encoding="utf-8")
        plain = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
        plain = re.sub(r"<style.*?</style>", " ", plain, flags=re.S)
        plain = re.sub(r"<[^>]+>", "\n", plain)
        lines = [line.strip() for line in plain.splitlines() if line.strip()]
        print(f"  去标签 {len(lines)} 行 | 含本站名 {html.count(name)} | 含327 {html.count('327')}")
        rows = [line for line in lines if re.search(r"\d{3}\s*期", line)]
        print(f"  含期数行 {len(rows)} 条, 最后 8 条:")
        for line in rows[-8:]:
            print("   ", line[:140])


if __name__ == "__main__":
    main()
