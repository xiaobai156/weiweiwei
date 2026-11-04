"""只读：解析论坛首页/分页的（帖子ID, 标题, 作者）三元组，找「潇洒人生」的新帖。"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
BASE = "https://0130190827.767566.xyz/bbs/"
ROW_RE = re.compile(
    r"""href=["']topic\.php\?id=(\d+)["'][^>]*>\s*<span class="subject-tag">(.*?)</span>.*?"""
    r"""subject-username[^>]*>(.*?)</span>""",
    re.S,
)


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Referer": BASE + "index.php"}
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("gb2312", errors="replace")


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&#126980;", "🔴").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


all_rows: dict[str, dict] = {}
pages: dict[str, dict] = {}
for page in range(1, 6):
    url = f"{BASE}index.php?page={page}" if page > 1 else BASE + "index.php"
    try:
        html = fetch(url)
    except Exception as exc:  # noqa: BLE001
        pages[url] = {"error": f"{type(exc).__name__}: {exc}"}
        continue
    rows = [
        {"id": m.group(1), "subject": clean(m.group(2)), "author": clean(m.group(3))}
        for m in ROW_RE.finditer(html)
    ]
    pages[url] = {"len": len(html), "rows": len(rows), "has_潇洒": "潇洒" in html}
    (OUT / f"index_p{page}.html").write_text(html, encoding="utf-8")
    for row in rows:
        all_rows[row["id"]] = row
    print(f"== page {page} rows={len(rows)} len={len(html)} 潇洒={'潇洒' in html}")
    for row in rows:
        flag = "  <<< " if "潇洒" in row["subject"] or "潇洒" in row["author"] else ""
        print(f"   {row['id']:>6} | {row['author'][:14]:<14} | {row['subject'][:60]}{flag}")

(OUT / "index_rows.json").write_text(
    json.dumps({"pages": pages, "rows": list(all_rows.values())}, ensure_ascii=False, indent=1),
    encoding="utf-8",
)
authors = sorted({r["author"] for r in all_rows.values()})
print("\n=== 全部作者（%d） ===" % len(authors))
print(" | ".join(authors))
print("\n潇洒 命中:", [r for r in all_rows.values() if "潇洒" in r["subject"] + r["author"]])
print("275期 帖子数:", len([r for r in all_rows.values() if "275期" in r["subject"]]))
