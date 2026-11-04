# -*- coding: utf-8 -*-
"""292 期杀尾换址诊断（只读）：旧域名 301 -> 新 origin，用原文章路径重建 URL 并浏览器验证。

判定四要素：站名命中 / 目标期命中 / 取值可读 / 方向语义。不写配置、缓存、正式 TXT。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests
import urllib3

urllib3.disable_warnings()

OUT = Path(__file__).resolve().parent
PERIOD = 292
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
}
PERIOD_RE = re.compile(r"(?<!\d)(\d{2,4})\s*期")

# 站名, 旧URL, 方向
TARGETS = [
    ("龙凤呈祥", "https://tulprhfc.wghcb-bnmgm-hyymaz.work:16655/topic/324698.html", "top"),
    ("可怜春天", "https://jogavu.6bl6s-ilo1w-yfnvvl.work:16677/topic/678625.html", "bottom"),
    ("正气凛然", "https://whsbrmz.qclrc-4mk42-vnxbyg.work:16677/topic/248009.html", "top"),
    ("违背烟蒂", "https://tulprhfc.wghcb-bnmgm-hyymaz.work:16655/topic/305414.html", "top"),
    ("清清淡淡", "https://iboatq.pjgpm-epbf7-lxpezb.work:16677/topic/324703.html", "top"),
    ("故里春意", "https://zdwcig.iyo4d-81klf-udwkqg.work:16677/topic/350485.html", "bottom"),
    ("八面驶风", "https://pvxiftuf.yumkw-u4s81-hpytyz.work:16677/topic/559099.html", "top"),
]


def resolve_origin(url: str) -> dict:
    """追一次 301，返回新 origin（scheme+netloc）。"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=25, verify=False, allow_redirects=False)
        loc = r.headers.get("Location", "")
        info = {"status": r.status_code, "location": loc}
        if loc:
            parts = urlsplit(loc)
            info["new_origin"] = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        return info
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def rebuild(old_url: str, new_origin: str) -> str:
    """保留原路径（文章 ID 不变），只换 origin。"""
    parts = urlsplit(old_url)
    return urlunsplit((urlsplit(new_origin).scheme, urlsplit(new_origin).netloc, parts.path, parts.query, ""))


def main() -> int:
    from playwright.sync_api import sync_playwright

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--ignore-certificate-errors"])
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        for name, old_url, pick in TARGETS:
            item = {"name": name, "old_url": old_url, "pick": pick}
            item.update(resolve_origin(old_url))
            new_origin = item.get("new_origin")
            if not new_origin:
                item["verdict"] = "无法定位新域名"
                results.append(item)
                print(name, "-> 无法定位新域名", item.get("error") or item.get("status"))
                continue
            candidate = rebuild(old_url, new_origin)
            item["candidate_url"] = candidate
            try:
                page.goto(candidate, timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                body = page.inner_text("body")
                item["final_url"] = page.url
                item["body_len"] = len(body)
                item["name_hit"] = name in body
                periods = sorted({int(x) for x in PERIOD_RE.findall(body)})
                item["periods_tail"] = periods[-6:]
                item["period_hit"] = PERIOD in periods
                idx = body.find(f"{PERIOD}期")
                if idx < 0:
                    idx = body.find(name)
                if idx >= 0:
                    item["context"] = re.sub(r"\s+", " ", body[max(0, idx - 120): idx + 320])
                (OUT / f"pw_{name}.txt").write_text(body, encoding="utf-8")
                if item["period_hit"] and item["name_hit"]:
                    item["verdict"] = "换址成功(站名+期数命中)"
                elif item["period_hit"]:
                    item["verdict"] = "期数命中但站名未命中(需核别名)"
                else:
                    item["verdict"] = "新域名下无本期数据"
            except Exception as exc:  # noqa: BLE001
                item["error"] = f"{type(exc).__name__}: {exc}"
                item["verdict"] = "渲染失败"
            results.append(item)
            print(
                name, item.get("verdict"),
                "| origin", new_origin,
                "| name", item.get("name_hit"),
                "| period", item.get("period_hit"),
                "| tail", item.get("periods_tail"),
                "|", (item.get("context") or "")[:120],
            )
        ctx.close()
        browser.close()

    (OUT / "换址诊断_292.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
