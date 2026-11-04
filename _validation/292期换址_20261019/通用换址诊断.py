# -*- coding: utf-8 -*-
"""通用换址诊断工具（只读）。

用途：项目里的站点批量报「最终 URL 与请求 URL 不同源 / 域名失效 / 期数找不到」时，
定位「旧域名 -> 新域名」，并验证新域名 + 原文章路径是否可取到目标期。

不写任何配置、缓存、正式 TXT；只输出诊断报告。

用法：
  py -3.10 通用换址诊断.py scan  <失败.txt> [更多失败.txt ...] [-o 报告.txt]
  py -3.10 通用换址诊断.py probe <失败.txt> [更多失败.txt ...] [-o 报告.txt] [--period 292]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

URL_RE = re.compile(r"https?://[^\s'\"）)，,；;]+")
PERIOD_RE = re.compile(r"(?<!\d)(\d{2,4})\s*期")


def read_lines(path: Path) -> list[str]:
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return path.read_text(encoding=enc).splitlines()
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"无法解码失败清单：{path}")


def extract(paths: list[Path]) -> tuple[list[dict], list[str]]:
    """从各种格式的失败清单里抽取 (站名, URL)。格式差异由「行内有 URL」兜底。"""
    entries, skipped = [], []
    for path in paths:
        for raw in read_lines(path):
            line = raw.strip()
            if not line or "失败分类统计" in line:
                continue
            urls = URL_RE.findall(line)
            if not urls:
                skipped.append(line[:120])
                continue
            url = urls[0]
            head = line[: line.index(url)].strip()
            # 站名 = URL 前最后一段非「失败/top/bottom/方向/期数」的词
            tokens = [
                t for t in re.split(r"[\s\t|]+", head)
                if t and t not in {"失败", "top", "bottom", "顶部", "尾部", "方向:", "期数:", "阶段:", "原因:"}
                and not t.endswith(":")
            ]
            name = tokens[-1] if tokens else ""
            name = re.sub(r"^(失败|错误)[:：]?", "", name).strip()
            entries.append({"name": name, "url": url, "source": path.name, "raw": line})
    return entries, skipped


def origin_of(url: str) -> str:
    parts = url.split("/")
    return parts[2] if len(parts) > 2 else ""


def cmd_scan(args: argparse.Namespace) -> int:
    import requests
    import urllib3

    urllib3.disable_warnings()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    }
    entries, skipped = extract([Path(p) for p in args.files])
    print(f"解析到 {len(entries)} 条，跳过 {len(skipped)} 行")

    by_origin: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        by_origin[origin_of(e["url"])].append(e)

    out = []
    for origin, items in sorted(by_origin.items(), key=lambda kv: -len(kv[1])):
        sample = items[0]["url"]
        try:
            r = requests.get(sample, headers=headers, timeout=25, verify=False, allow_redirects=False)
            code, loc = r.status_code, r.headers.get("Location", "").split("#")[0]
        except Exception as exc:  # noqa: BLE001
            code, loc = "ERR", f"{type(exc).__name__}"
        out.append({
            "origin": origin,
            "count": len(items),
            "names": [i["name"] for i in items],
            "status": code,
            "redirect": loc,
        })
        print(f"{origin:45s} {len(items):3d}站 {code} -> {loc[:70]}")

    if args.out:
        lines = ["旧域名\t站数\tHTTP\t跳转目标\t站点"]
        for row in out:
            lines.append(
                f"{row['origin']}\t{row['count']}\t{row['status']}\t{row['redirect']}\t{','.join(row['names'])}"
            )
        if skipped:
            lines += ["", "未能解析的行"] + skipped
        Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
        print("报告已写:", args.out)
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    from playwright.sync_api import sync_playwright

    entries, _ = extract([Path(p) for p in args.files])
    period = str(args.period) if args.period else None
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--ignore-certificate-errors"])
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        for e in entries:
            try:
                page.goto(e["url"], timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(3500)
                final = page.url
                text = page.inner_text("body")
                hit = (e["name"] in text) if e["name"] else None
                periods = sorted({int(x) for x in PERIOD_RE.findall(text)})
                # 只关心近期期号，避免历史期数干扰判断
                recent = [x for x in periods if x >= 200]
                want = period in {str(x) for x in periods} if period else None
                results.append({**e, "final": final, "name_hit": hit, "periods": periods, "period_hit": want})
                print(
                    f"{e['name'][:12]:14s} 文本{len(text):6d} "
                    f"站名={hit} 目标期={want} 近期期数{recent[-6:]}"
                )
            except Exception as exc:  # noqa: BLE001
                results.append({**e, "error": f"{type(exc).__name__}: {exc}"})
                print(f"{e['name'][:12]:14s} 失败 {type(exc).__name__}: {str(exc)[:60]}")
        ctx.close()
        browser.close()

    if args.out:
        lines = ["站名\t原URL\t最终URL\t站名命中\t目标期命中\t期数\t备注"]
        for r in results:
            lines.append(
                "\t".join(
                    str(x)
                    for x in (
                        r.get("name", ""), r.get("url", ""), r.get("final", ""),
                        r.get("name_hit", ""), r.get("period_hit", ""),
                        ",".join(str(p) for p in r.get("periods", [])[:8]),
                        r.get("error", ""),
                    )
                )
            )
        Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
        print("报告已写:", args.out)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="通用换址诊断（只读）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="按域名聚合失败清单，追 301 目标")
    scan.add_argument("files", nargs="+")
    scan.add_argument("-o", "--out")
    scan.set_defaults(func=cmd_scan)

    probe = sub.add_parser("probe", help="浏览器逐站验证：站名、目标期是否命中")
    probe.add_argument("files", nargs="+")
    probe.add_argument("-o", "--out")
    probe.add_argument("--period")
    probe.set_defaults(func=cmd_probe)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
