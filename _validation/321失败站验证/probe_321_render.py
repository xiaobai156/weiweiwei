"""血气方刚 321：浏览器渲染 + 站内列表查找该站是否还在、ID 是否变了。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent
BASE = "https://xjsjbkv.b3e4x-wxhjo-lbdbjg.xyz:29477"
TARGET_ID = "6a3978d3018539c611cb8920"


def main() -> None:
    from playwright.sync_api import sync_playwright

    url = f"{BASE}/article/manager/{TARGET_ID}?url=jbx"
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(ROOT / "browser-profile"),
            headless=True,
            viewport={"width": 1280, "height": 900},
            ignore_https_errors=True,
            locale="zh-CN",
        )
        try:
            page = ctx.new_page()
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(3500)
            body = page.locator("body").inner_text()
            html = page.content()
            (OUT / "render_target.txt").write_text(body, encoding="utf-8")
            print("渲染 body 长度:", len(body), "| 含血气方刚:", "血气方刚" in body)
            print("前 300:", re.sub(r"\s+", " ", body)[:300])

            page2 = ctx.new_page()
            page2.goto(BASE + "/", timeout=45000, wait_until="domcontentloaded")
            page2.wait_for_timeout(3500)
            home = page2.locator("body").inner_text()
            home_html = page2.content()
            (OUT / "render_home.txt").write_text(home, encoding="utf-8")
            print("\n首页 body 长度:", len(home), "| 含血气方刚:", "血气方刚" in home)
            ids = sorted(set(re.findall(r"/article/(?:manager|admin)/([0-9a-f]{24})", home_html)))
            print("首页文章 ID 数:", len(ids), "| 目标 ID 在首页:", TARGET_ID in ids)
            rows = [ln.strip()[:80] for ln in home.splitlines() if "血气" in ln or "神童" in ln][:5]
            print("首页相关行:", rows)
            (OUT / "home_ids.json").write_text(
                json.dumps({"ids": ids, "has_target": TARGET_ID in ids}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        finally:
            ctx.close()


if __name__ == "__main__":
    main()
