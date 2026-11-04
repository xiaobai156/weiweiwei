"""用项目持久化会话渲染张天师，检查 306 期是否真的没有可见尾数（只读）。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from playwright.sync_api import sync_playwright

from shawei.fetch.browser import browser_profile_dir

URL = "https://wwlhc.com/thread-87037-1-1.html"


def main() -> int:
    profile = browser_profile_dir()
    print("profile:", profile, flush=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(profile),
            headless=True,
            viewport={"width": 1280, "height": 2600},
            ignore_https_errors=True,
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)
            html = page.content()
            text = page.inner_text("body")
        except Exception as exc:  # noqa: BLE001
            print("渲染失败:", type(exc).__name__, exc, flush=True)
            ctx.close()
            return 1
        logged_in = "退出" in text or "积分" in text
        ctx.close()

    Path("zts_persist.html").write_text(html, encoding="utf-8")
    Path("zts_persist.txt").write_text(text, encoding="utf-8")
    print("logged_in hints:", logged_in, "| html", len(html), "| text", len(text), flush=True)
    idx = text.find("306期: ★★★张天师")
    if idx < 0:
        idx = text.find("306期")
    print("306 context:", repr(text[max(0, idx - 30) : idx + 220]), flush=True)
    print("hide notice count:", text.count("隐藏内容请回复"), flush=True)
    m = re.search(r"306期.{0,300}", text, re.S)
    if m:
        print("raw 306 slice:", repr(m.group(0)[:300]), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
