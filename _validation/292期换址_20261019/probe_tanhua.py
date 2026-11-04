# -*- coding: utf-8 -*-
"""昙花一现换址候选验证（只读）：IP 直连镜像 read.php?tid=1904 是否含本站 292 期数据。

判定：站名锚点 + 292 期 + 取值 + 方向，四项齐全才算命中。
不写配置、缓存、正式 TXT。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent
PERIOD = 292
CANDIDATES = [
    ("IP直连", "http://38.177.253.132:31882/read.php?tid=1904"),
    ("旧域名", "https://www.www144344.com/read.php?tid=1904"),
]
PERIOD_RE = re.compile(r"(?<!\d)(\d{2,4})\s*期")


def main() -> int:
    from playwright.sync_api import sync_playwright

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--ignore-certificate-errors"])
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        for label, url in CANDIDATES:
            item = {"label": label, "url": url}
            try:
                page.goto(url, timeout=45000, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)
                body = page.inner_text("body")
                item["final_url"] = page.url
                item["body_len"] = len(body)
                item["name_hit"] = "昙花一现" in body
                periods = sorted({int(x) for x in PERIOD_RE.findall(body)})
                item["periods_tail"] = periods[-6:]
                item["period_hit"] = PERIOD in periods
                idx = body.find("昙花一现")
                if idx < 0:
                    idx = body.find(f"{PERIOD}期")
                if idx >= 0:
                    item["context"] = re.sub(r"\s+", " ", body[max(0, idx - 150): idx + 450])
                (OUT / f"pw_tanhua_{label}.txt").write_text(body, encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                item["error"] = f"{type(exc).__name__}: {exc}"
            results.append(item)
            print(label, json.dumps({k: v for k, v in item.items() if k != "context"},
                                    ensure_ascii=False))
            if item.get("context"):
                print("   CTX:", item["context"][:400])
        ctx.close()
        browser.close()

    (OUT / "tanhua_probe.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
