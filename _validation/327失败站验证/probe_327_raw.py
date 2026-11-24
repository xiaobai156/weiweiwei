"""327 清肝明目：直接抓原始 HTML 看结构（渲染返回了 732 份长度 1 的文档，异常）。"""

from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent
URLS = {
    "清肝明目": "https://4.48kk49.com:1888/Article/ar_content/id/1543/tid/82.html",
    "白杨金牌": "https://4.48kk49.com:1888/Article/ar_content/id/1556/tid/82.html",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        raw = resp.read()
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def main() -> None:
    for name, url in URLS.items():
        html = fetch(url)
        (OUT / f"raw_{name}.html").write_text(html, encoding="utf-8")
        print(f"\n=== {name} 原始 HTML {len(html)} 字符 | 含327 {html.count('327')} | 含本站名 {html.count(name)}")
        plain = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
        plain = re.sub(r"<style.*?</style>", " ", plain, flags=re.S)
        plain = re.sub(r"<[^>]+>", "\n", plain)
        lines = [line.strip() for line in plain.splitlines() if line.strip()]
        print(f"去标签后 {len(lines)} 行, 前 30 行:")
        for i, line in enumerate(lines[:30]):
            print(f"  {i} {line[:110]}")
        rows = [line for line in lines if re.search(r"(3[0-9]{2})期", line)]
        print(f"含期数的行 {len(rows)} 条，最后 6 条:")
        for line in rows[-6:]:
            print("  ", line[:130])


if __name__ == "__main__":
    main()
