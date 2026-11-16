"""检查 458345 这个帖子所在站点的首页/列表，确认“坚韧不拔”是否还存在于站内。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent
BASE = "https://lxbwvnfv.3gwtt-z9y8n-wsxdfy.xyz:16677"


def main() -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(ROOT / "browser-profile"),
            headless=True,
            viewport={"width": 1280, "height": 900},
            ignore_https_errors=True,
            locale="zh-CN",
        )
        try:
            for path in ("/", "/topic/458345.html"):
                page = ctx.new_page()
                try:
                    page.goto(BASE + path, timeout=45000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2500)
                    body = page.locator("body").inner_text()
                    html = page.content()
                    name = "index" if path == "/" else "topic458345"
                    (OUT / f"list_{name}.txt").write_text(body, encoding="utf-8")
                    print(f"=== {path} ===")
                    print("标题:", page.title(), "| body 长度:", len(body))
                    print("含 坚韧不拔:", "坚韧不拔" in body, "| 含 澳门关云长:", "澳门关云长" in body)
                    links = sorted(set(re.findall(r"/topic/(\d+)\.html", html)))
                    print("topic 链接数:", len(links), "样例:", links[:12])
                    rows = [ln.strip() for ln in body.splitlines() if ln.strip()]
                    heads = [ln[:80] for ln in rows if "期" in ln and "资料" in ln][:8]
                    print("资料类标题行:", heads)
                finally:
                    page.close()
        finally:
            ctx.close()


if __name__ == "__main__":
    main()
