# -*- coding: utf-8 -*-
"""320：两站页面渲染取证，判断是「未发布320期」还是解析漏取。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shawei.fetch.browser import render_browser_documents  # noqa: E402

TARGETS = {
    "坚韧不拔": "https://lxbwvnfv.3gwtt-z9y8n-wsxdfy.xyz:16677/topic/458345.html",
    "张天师": "https://wwlhc.com/thread-87037-1-1.html",
}


def plain(html: str) -> str:
    txt = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    txt = re.sub(r"<style.*?</style>", " ", txt, flags=re.S)
    txt = re.sub(r"<[^>]+>", " ", txt)
    return re.sub(r"[ \t\u00a0]+", " ", txt)


def main() -> None:
    for name, url in TARGETS.items():
        docs = None
        for timeout in (25, 45):
            try:
                docs = render_browser_documents(url, timeout)
                break
            except Exception as exc:  # noqa: BLE001
                print(f"[{name}] 超时{timeout} {type(exc).__name__}", flush=True)
        if docs is None:
            print(f"[{name}] 渲染失败", flush=True)
            continue
        body = plain(docs[0])
        full = plain("\n".join(docs))
        print(f"[{name}] body={len(body)} html={len(full)} 游客={'游客' in full}", flush=True)
        Path(__file__).with_name(f"render_{name}.txt").write_text(full, encoding="utf-8")
        periods = sorted({int(m) for m in re.findall(r"(\d{3})\s*期", full)})
        print(f"  期数范围 {periods[:3]}..{periods[-6:]} 共{len(periods)}个", flush=True)
        if "已被下架" in full:
            print("  !! 已下架", flush=True)
        for line in full.splitlines():
            s = line.strip()
            if not s:
                continue
            if name in s and re.search(r"\d{3}\s*期", s):
                print("  >", s[:200], flush=True)


if __name__ == "__main__":
    main()
