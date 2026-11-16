"""320 期两站实时取证：页面身份、锁定状态、目标期行是否存在。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.fetch.browser import browser_profile_dir, render_browser_documents  # noqa: E402

OUT = Path(__file__).resolve().parent
TARGETS = {
    "坚韧不拔": "https://lxbwvnfv.3gwtt-z9y8n-wsxdfy.xyz:16677/topic/458345.html",
    "张天师": "https://wwlhc.com/thread-87037-1-1.html",
}


def main() -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(browser_profile_dir()),
            headless=True,
            viewport={"width": 1280, "height": 900},
            ignore_https_errors=True,
            locale="zh-CN",
        )
        try:
            for name, url in TARGETS.items():
                page = ctx.new_page()
                try:
                    page.goto(url, timeout=45000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2500)
                    try:
                        page.add_style_tag(
                            content="*{content-visibility:visible!important;contain-intrinsic-size:auto!important}"
                        )
                        page.wait_for_timeout(300)
                    except Exception as exc:  # pragma: no cover
                        print(name, "注入样式失败", type(exc).__name__)
                    final_url = page.url
                    title = page.title()
                    body = page.locator("body").inner_text()
                    html = page.content()
                    (OUT / f"live_{name}.txt").write_text(body, encoding="utf-8")
                    print(f"=== {name} ===")
                    print("请求URL:", url)
                    print("最终URL:", final_url)
                    print("标题:", title)
                    print("页内出现站名:", name in body, "| html 含站名:", name in html)
                    print("锁定/回复提示:", "游客" in body, "|", "隐藏内容" in body, "|", "回复" in body)
                    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
                    for kw in ("320期", "319期", "302期"):
                        hits = [ln[:110] for ln in lines if kw in ln][:4]
                        print(f"{kw} 文本行({len(hits)}):", hits)
                    print("body 长度:", len(body), "| html 长度:", len(html))
                finally:
                    page.close()
        finally:
            ctx.close()


if __name__ == "__main__":
    main()
