# -*- coding: utf-8 -*-
"""319：财源滚滚页面渲染取证，判断是「未发布319期」还是解析漏取。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shawei.fetch.browser import render_browser_documents  # noqa: E402

URL = "https://12388990827.688756.xyz/bbs/topic.php?id=19128"
OUT = Path(__file__).with_name("render_caiyuan.txt")


def main() -> None:
    docs = render_browser_documents(URL, 30)
    print(f"文档数={len(docs)} 长度={[len(d) for d in docs]}", flush=True)
    text = "\n".join(docs)
    OUT.write_text(text, encoding="utf-8")
    periods = sorted({int(m) for m in re.findall(r"(\d{3})\s*期", text)})
    print("出现的期数:", periods[-12:], flush=True)
    for line in text.splitlines():
        if "期" in line and "财源滚滚" in line:
            print("  >", line.strip()[:160], flush=True)
    print("--- 含 31x/32x 期 的行 ---", flush=True)
    for line in text.splitlines():
        if re.search(r"3[12]\d\s*期", line):
            print("  |", line.strip()[:160], flush=True)


if __name__ == "__main__":
    main()
