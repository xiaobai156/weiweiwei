"""血气方刚 321：站内搜索该站名，确认是否改名/换帖或彻底下架。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BASE = "https://xjsjbkv.b3e4x-wxhjo-lbdbjg.xyz:29477"
NAME = "血气方刚"


def main() -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(ROOT / "browser-profile"),
            headless=True,
            viewport={"width": 1400, "height": 1000},
            ignore_https_errors=True,
            locale="zh-CN",
        )
        try:
            page = ctx.new_page()
            page.goto(BASE + "/", timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            found = {}
            # 1) 首页全部文章链接（含各类区）
            html = page.content()
            links = sorted(set(re.findall(r"/article/(?:manager|admin|lottery)/([0-9a-f]{24})", html)))
            found["home_article_ids"] = len(links)
            found["home_has_name"] = NAME in page.locator("body").inner_text()

            # 2) 尝试站内搜索接口
            for api in (
                f"{BASE}/api/proxy/manager-articles?keyword={NAME}",
                f"{BASE}/api/proxy/search?keyword={NAME}",
                f"{BASE}/api/proxy/articles/search?keyword={NAME}",
            ):
                try:
                    resp = page.request.get(api, timeout=20000)
                    text = resp.text()
                    found.setdefault("search", []).append(
                        {"api": api, "status": resp.status, "len": len(text), "sample": text[:150]}
                    )
                except Exception as exc:
                    found.setdefault("search", []).append({"api": api, "error": type(exc).__name__})

            # 3) 用 UI 搜索框搜站名
            body_text = page.locator("body").inner_text()
            (OUT / "render_home2.txt").write_text(body_text, encoding="utf-8")
            names = sorted(set(re.findall(r"【([^】]{2,8})】", body_text)))
            found["home_bracket_names"] = names[:40]
            found["name_in_bracket"] = NAME in names

            (OUT / "probe_321_onsite.json").write_text(
                json.dumps(found, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(json.dumps(found, ensure_ascii=False, indent=2)[:1500])
        finally:
            ctx.close()


if __name__ == "__main__":
    main()
