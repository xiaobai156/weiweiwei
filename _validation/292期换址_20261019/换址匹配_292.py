# -*- coding: utf-8 -*-
"""292 期杀尾换址：用杀肖-V2 已确认的新镜像 origin 逐个匹配我们的文章 ID（只读）。

判定四要素：站名命中 / 292 期命中 / 取值可读 / 方向语义。
不写配置、缓存、正式 TXT；结果只落本隔离目录。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
PERIOD = 292
PERIOD_RE = re.compile(r"(?<!\d)(\d{2,4})\s*期")

# 我们的 7 个换址站：站名, 旧URL, 方向
TARGETS = [
    ("龙凤呈祥", "https://tulprhfc.wghcb-bnmgm-hyymaz.work:16655/topic/324698.html", "top"),
    ("可怜春天", "https://jogavu.6bl6s-ilo1w-yfnvvl.work:16677/topic/678625.html", "bottom"),
    ("正气凛然", "https://whsbrmz.qclrc-4mk42-vnxbyg.work:16677/topic/248009.html", "top"),
    ("违背烟蒂", "https://tulprhfc.wghcb-bnmgm-hyymaz.work:16655/topic/305414.html", "top"),
    ("清清淡淡", "https://iboatq.pjgpm-epbf7-lxpezb.work:16677/topic/324703.html", "top"),
    ("故里春意", "https://zdwcig.iyo4d-81klf-udwkqg.work:16677/topic/350485.html", "bottom"),
    ("八面驶风", "https://pvxiftuf.yumkw-u4s81-hpytyz.work:16677/topic/559099.html", "top"),
]

# 杀肖-V2 CHANGES.tsv 里实测可用、且与本站群同族的镜像 origin
CANDIDATE_ORIGINS = [
    "https://dzdsqxrw.1mppg-x8rsf-cxwlxc.cyou:17455",
]


def load_changes_origins() -> list[str]:
    """从杀肖-V2 CHANGES.tsv 收集所有「新URL」origin，按出现次数排序。"""
    path = Path(
        r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀肖-V2\audit\relocate-292\CHANGES.tsv"
    )
    if not path.exists():
        return []
    counts: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines()[1:]:
        cells = line.split("\t")
        if len(cells) < 3:
            continue
        new_url = cells[2].strip()
        if not new_url.startswith("http"):
            continue
        parts = new_url.split("/")
        if len(parts) > 2:
            origin = f"{parts[0]}//{parts[2]}"
            counts[origin] = counts.get(origin, 0) + 1
    return [o for o, _ in sorted(counts.items(), key=lambda kv: -kv[1])]


def main() -> int:
    from playwright.sync_api import sync_playwright

    origins = CANDIDATE_ORIGINS + [o for o in load_changes_origins() if o not in CANDIDATE_ORIGINS]
    print("候选 origin:", len(origins))
    for o in origins:
        print("  ", o)

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--ignore-certificate-errors"])
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        for name, old_url, pick in TARGETS:
            topic_path = "/" + old_url.split("/", 3)[3]  # topic/xxxx.html
            found = None
            tried = []
            for origin in origins:
                candidate = origin + topic_path
                tried.append(candidate)
                try:
                    page.goto(candidate, timeout=45000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2500)
                    body = page.inner_text("body")
                except Exception as exc:  # noqa: BLE001
                    tried[-1] += f" [ERR {type(exc).__name__}]"
                    continue
                periods = sorted({int(x) for x in PERIOD_RE.findall(body)})
                name_hit = name in body
                period_hit = PERIOD in periods
                if name_hit and period_hit:
                    idx = body.find(f"{PERIOD}期")
                    found = {
                        "origin": origin,
                        "url": candidate,
                        "final_url": page.url,
                        "body_len": len(body),
                        "periods_tail": periods[-6:],
                        "context": re.sub(r"\s+", " ", body[max(0, idx - 100): idx + 400]),
                    }
                    (OUT / f"hit_{name}.txt").write_text(body, encoding="utf-8")
                    break
                if period_hit or name_hit:
                    tried[-1] += f" [部分: 站名={name_hit} 期数={period_hit}]"
            results.append({
                "name": name, "old_url": old_url, "pick": pick,
                "topic_path": topic_path, "found": found, "tried": tried,
            })
            if found:
                print(f"✅ {name} -> {found['url']}")
                print("    ", found["context"][:260])
            else:
                print(f"❌ {name} 未在任何候选 origin 上命中 站名+292 期")
                for t in tried:
                    print("     ", t)
        ctx.close()
        browser.close()

    (OUT / "换址匹配_292.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
