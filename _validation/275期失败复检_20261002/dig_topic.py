"""只读：分析已下架帖子页的结构 + 站点其他入口（rcg.php）是否还有该作者。"""
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


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": BASE})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.status, resp.read().decode("gb2312", errors="replace")


text = (OUT / "raw_topic_30780.html").read_text(encoding="utf-8")
text = text.replace("</script>", "</script>\n")
print("=== topic 30780 结构 ===")
print("len", len(text))
plain = re.sub(r"<script.*?</script>", " ", text, flags=re.S)
plain = re.sub(r"<style.*?</style>", " ", plain, flags=re.S)
plain = re.sub(r"<[^>]+>", " ", plain)
plain = re.sub(r"\s+", " ", plain).strip()
print("正文:", plain[:600])
print("\n=== script/ajax 端点 ===")
for m in set(re.findall(r"""(?:fetch|url|action|\$\.(?:post|get|ajax))\s*[:(]\s*["']([^"']+)["']""", text)):
    print("  ", m)
print("\n=== 出现的 php/接口路径 ===")
for m in sorted(set(re.findall(r"[a-zA-Z_]+\.php(?:\?[^\"' ]*)?", text))):
    print("  ", m)
print("\n=== 关键词 ===")
for kw in ("下架", "作者", "uid", "author", "topicid", "id=30780"):
    for i, m in enumerate(re.finditer(re.escape(kw), text)):
        if i >= 3:
            break
        seg = re.sub(r"\s+", " ", text[max(0, m.start() - 80) : m.start() + 120])
        print(f"  [{kw}] {seg}")

print("\n=== rcg.php ===")
try:
    status, page = fetch(BASE + "rcg.php")
    (OUT / "raw_rcg.html").write_text(page, encoding="utf-8")
    flat = re.sub(r"<[^>]+>", " ", page)
    flat = re.sub(r"\s+", " ", flat)
    print("status", status, "len", len(page), "潇洒:", "潇洒" in page)
    print("text:", flat[:800])
    print("topic links:", sorted(set(re.findall(r"topic\.php\?id=(\d+)", page)), key=int)[:30])
except Exception as exc:  # noqa: BLE001
    print("error", type(exc).__name__, exc)

print("\n=== 邻居 id 探测（30770-30790 标题/状态） ===")
probe = {}
for tid in range(30776, 30786):
    try:
        status, page = fetch(f"{BASE}topic.php?id={tid}")
        title = re.search(r"<title>(.*?)</title>", page, re.S)
        down = "此帖子ID已被下架" in page
        has_period = bool(re.search(r"2\d\d\s*期", page))
        probe[tid] = {"status": status, "len": len(page), "down": down, "has_period": has_period}
    except Exception as exc:  # noqa: BLE001
        probe[tid] = {"error": f"{type(exc).__name__}: {exc}"}
    print(" ", tid, probe[tid])
(OUT / "neighbor_probe.json").write_text(json.dumps(probe, ensure_ascii=False, indent=1), encoding="utf-8")
