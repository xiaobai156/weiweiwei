# -*- coding: utf-8 -*-
"""319：财源滚滚是否为「帖子被下架」——查同站其它帖与站内列表。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shawei.fetch.browser import render_browser_documents  # noqa: E402

TARGET = "https://12388990827.688756.xyz/bbs/topic.php?id=19128"
INDEX = "https://12388990827.688756.xyz/bbs/index.php"
PEERS = [
    "https://12388990827.688756.xyz/bbs/topic.php?id=19127",
    "https://12388990827.688756.xyz/bbs/topic.php?id=19129",
]


def plain(html: str) -> str:
    txt = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    txt = re.sub(r"<style.*?</style>", " ", txt, flags=re.S)
    txt = re.sub(r"<[^>]+>", " ", txt)
    return re.sub(r"\s+", " ", txt)


def try_render(url: str) -> str:
    for timeout in (30, 45):
        try:
            docs = render_browser_documents(url, timeout)
            return plain("\n".join(docs))
        except Exception as exc:  # noqa: BLE001
            print(f"  {url} 超时{timeout} {type(exc).__name__}", flush=True)
    return ""


def main() -> None:
    for url in [TARGET, *PEERS]:
        text = try_render(url)
        if not text:
            print(f"[{url}] 渲染失败", flush=True)
            continue
        removed = "已被下架" in text
        periods = sorted({int(m) for m in re.findall(r"(3\d{2})\s*期", text)})
        print(f"[{url}] 下架={removed} 期数={periods[-8:]} 长度={len(text)}", flush=True)

    text = try_render(INDEX)
    if not text:
        print(f"[{INDEX}] 渲染失败", flush=True)
        return
    print("首页长度", len(text), flush=True)
    names = re.findall(r"topic\.php\?id=(\d+)", text)
    print("首页 topic 链接数", len(names), flush=True)
    print("含『财源滚滚』", "财源滚滚" in text, flush=True)
    hits = [m.start() for m in re.finditer("财源滚滚", text)]
    for i in hits[:5]:
        print("  ...", text[max(0, i - 60) : i + 40], flush=True)
    Path(__file__).with_name("render_caiyuan_index.txt").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
