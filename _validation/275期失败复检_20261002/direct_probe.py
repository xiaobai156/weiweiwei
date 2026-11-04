"""只读：直连抓取 潇洒人生 帖子与论坛首页原始 HTML（gb2312 解码），找「下架/新帖」。"""
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

TARGETS = {
    "topic_30780": "https://0130190827.767566.xyz/bbs/topic.php?id=30780",
    "bbs_index": "https://0130190827.767566.xyz/bbs/",
}


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://0130190827.767566.xyz/bbs/",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = resp.read()
        return resp.status, data.decode("gb2312", errors="replace")


report: dict = {}
for key, url in TARGETS.items():
    entry: dict = {"url": url}
    try:
        status, text = fetch(url)
        entry["status"] = status
        entry["len"] = len(text)
        (OUT / f"raw_{key}.html").write_text(text, encoding="utf-8")
        entry["has_275"] = "275" in text
        entry["has_潇洒人生"] = "潇洒人生" in text
        entry["hits"] = {
            kw: [re.sub(r"\s+", " ", m.group(0)) for m in re.finditer(rf".{{0,50}}{kw}.{{0,80}}", text)][
                :6
            ]
            for kw in ("下架", "潇洒人生", "275期", "274期")
        }
        entry["title"] = (re.search(r"<title>(.*?)</title>", text, re.S) or [None, ""])[1].strip()
        entry["topic_links"] = list(
            dict.fromkeys(re.findall(r"""href=["']([^"']*topic\.php\?id=\d+[^"']*)["']""", text))
        )[:40]
    except Exception as exc:  # noqa: BLE001
        entry["error"] = f"{type(exc).__name__}: {exc}"
    report[key] = entry

(OUT / "direct_probe_out.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
)
for key, entry in report.items():
    print("==", key, entry.get("status"), entry.get("len"), "275:", entry.get("has_275"),
          "潇洒人生:", entry.get("has_潇洒人生"))
    print("   title:", entry.get("title"))
    print("   err:", entry.get("error", ""))
    for kw, hits in (entry.get("hits") or {}).items():
        for hit in hits:
            print(f"   [{kw}] {hit}")
    for link in entry.get("topic_links", [])[:20]:
        print("   link:", link)
