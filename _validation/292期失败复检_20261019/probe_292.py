"""292 期 11 个失败站只读验证：HTTP + 浏览器渲染 + 专属文档收集，判断「异常/无数据」。

只读：不写正式 TXT、不写缓存、不改配置。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.fetch.browser import render_browser_documents  # noqa: E402
from shawei.fetch.document_discovery import collect_documents  # noqa: E402
from shawei.fetch.http_client import fetch_text  # noqa: E402
from shawei.config.rules import effective_rule_for  # noqa: E402

PERIOD = 292
OUT = Path(__file__).resolve().parent

TARGETS = [
    ("小明哥上", "https://gboqrz.sm0a0-x9x2c-xyvjdr.work/topic/172572.html", "top"),
    ("可见一斑", "https://gboqrz.sm0a0-x9x2c-xyvjdr.work/topic/241106.html", "bottom"),
    ("龙凤呈祥", "https://tulprhfc.wghcb-bnmgm-hyymaz.work:16655/topic/324698.html", "top"),
    ("可怜春天", "https://jogavu.6bl6s-ilo1w-yfnvvl.work:16677/topic/678625.html", "bottom"),
    ("正气凛然", "https://whsbrmz.qclrc-4mk42-vnxbyg.work:16677/topic/248009.html", "top"),
    ("违背烟蒂", "https://tulprhfc.wghcb-bnmgm-hyymaz.work:16655/topic/305414.html", "top"),
    ("清清淡淡", "https://iboatq.pjgpm-epbf7-lxpezb.work:16677/topic/324703.html", "top"),
    ("故里春意", "https://zdwcig.iyo4d-81klf-udwkqg.work:16677/topic/350485.html", "bottom"),
    ("八面驶风", "https://pvxiftuf.yumkw-u4s81-hpytyz.work:16677/topic/559099.html", "top"),
    ("六玄网", "https://lx11.www87127b.com:8443/#87127", "top"),
    ("昙花一现", "https://www.www144344.com/read.php?tid=1904", "bottom"),
]


def probe(name: str, url: str, pick: str) -> dict:
    info: dict[str, object] = {"name": name, "url": url, "pick": pick}
    rule = effective_rule_for(url, name)
    info["rule"] = {
        "allowed_sources": list(rule.allowed_sources),
        "prefer_rendered": rule.prefer_rendered,
        "dedicated_parser": rule.dedicated_parser,
    }

    http_text = ""
    try:
        http_text = fetch_text(url, 15)
        info["http_len"] = len(http_text)
    except Exception as exc:
        info["http_error"] = f"{type(exc).__name__}: {exc}"

    render_body = ""
    try:
        docs = render_browser_documents(url, 20)
        render_body = docs[0] if docs else ""
        info["render_len"] = len(render_body)
        info["render_has_period"] = f"{PERIOD}期" in render_body
        info["render_has_name"] = name in render_body
        (OUT / f"render_{name}.txt").write_text("\n\n=====\n\n".join(docs), encoding="utf-8")
    except Exception as exc:
        info["render_error"] = f"{type(exc).__name__}: {exc}"

    try:
        collected = collect_documents(url, 20)
        joined = "\n".join(collected)
        info["collect_docs"] = len(collected)
        info["collect_len"] = len(joined)
        info["collect_has_period"] = f"{PERIOD}期" in joined
        periods = sorted({int(m) for m in re.findall(r"(\d{3})\s*期", joined)})
        info["periods_max"] = periods[-1] if periods else None
        info["periods_tail"] = periods[-6:]
        (OUT / f"collect_{name}.txt").write_text(joined, encoding="utf-8")
    except Exception as exc:
        info["collect_error"] = f"{type(exc).__name__}: {exc}"

    # 分类：渲染/收集能拿到 292 期正文 => 异常(可重抓)；页面正常但确实没有 292 期 => 无数据
    reachable = bool(render_body or http_text)
    has_period = bool(info.get("render_has_period") or info.get("collect_has_period"))
    if has_period:
        info["verdict"] = "异常"
    elif reachable:
        info["verdict"] = "无数据(待确认)"
    else:
        info["verdict"] = "异常(站点不可达)"
    return info


results = []
for site_name, site_url, site_pick in TARGETS:
    item = probe(site_name, site_url, site_pick)
    results.append(item)
    print(
        site_name,
        site_pick,
        item.get("verdict"),
        "http=", item.get("http_len") or item.get("http_error"),
        "render=", item.get("render_len") or item.get("render_error"),
        "collect=", item.get("collect_len") or item.get("collect_error"),
        "period=", item.get("collect_has_period"),
        "max=", item.get("periods_max"),
    )

(OUT / "probe_292.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)
