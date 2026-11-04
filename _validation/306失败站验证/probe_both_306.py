"""306 期两个失败站的渲染取证（带重试，只读）。"""
from __future__ import annotations

import sys
import time

from playwright.sync_api import sync_playwright

TARGETS = {
    "zts": "https://wwlhc.com/thread-87037-1-1.html",
    "stqy": "https://xuknerw.fu5qv-a7f7o-nxmebt.work:16633/topic/272676.html",
}


def render(page, url: str, attempts: int = 4) -> str | None:
    for n in range(attempts):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3500)
            return page.inner_text("body")
        except Exception as exc:  # noqa: BLE001
            print(f"  attempt {n + 1} failed: {type(exc).__name__}: {str(exc)[:70]}", flush=True)
            time.sleep(4)
    return None


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--ignore-certificate-errors"])
        ctx = browser.new_context(
            ignore_https_errors=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )
        page = ctx.new_page()
        for key, url in TARGETS.items():
            print("==", key, url, flush=True)
            text = render(page, url)
            if text is None:
                print("  最终失败：无法渲染", flush=True)
                continue
            path = f"{key}_visible.txt"
            open(path, "w", encoding="utf-8").write(text)
            print(f"  渲染成功 {len(text)} 字 -> {path}", flush=True)
            for kw in ("304期", "305期", "306期"):
                idx = text.find(kw)
                if idx >= 0:
                    print(f"  [{kw}] {text[idx : idx + 120]!r}", flush=True)
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
