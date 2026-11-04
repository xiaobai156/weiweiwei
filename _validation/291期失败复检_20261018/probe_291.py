"""291 期两个失败站（小明哥上 / 可见一斑）只读验证：HTTP + 浏览器渲染 + strdecode 解码。"""
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

TARGETS = [
    ("小明哥上", "https://gboqrz.sm0a0-x9x2c-xyvjdr.work/topic/172572.html", "top"),
    ("可见一斑", "https://gboqrz.sm0a0-x9x2c-xyvjdr.work/topic/241106.html", "bottom"),
]

OUT = Path(__file__).resolve().parent
result: dict[str, object] = {}


def snapshot(name: str, url: str) -> dict[str, object]:
    info: dict[str, object] = {}
    try:
        page = fetch_text(url, 15)
        info["http_len"] = len(page)
        info["http_head"] = page[:200].replace("\n", " ")
    except Exception as exc:
        info["http_error"] = f"{type(exc).__name__}: {exc}"
        page = ""
    try:
        docs = render_browser_documents(url, 20)
        info["render_docs"] = len(docs)
        info["render_body_len"] = len(docs[0]) if docs else 0
        info["render_has_291"] = "291" in (docs[0] if docs else "")
        (OUT / f"render_{name}.txt").write_text("\n\n=====\n\n".join(docs), encoding="utf-8")
    except Exception as exc:
        info["render_error"] = f"{type(exc).__name__}: {exc}"
    try:
        collected = collect_documents(url, 20)
        info["collect_docs"] = len(collected)
        joined = "\n".join(collected)
        info["collect_len"] = len(joined)
        info["collect_has_name"] = name in joined
        periods = sorted({int(m) for m in re.findall(r"(\d{3})\s*期", joined)})
        info["periods_seen"] = periods
        (OUT / f"collect_{name}.txt").write_text(joined, encoding="utf-8")
    except Exception as exc:
        info["collect_error"] = f"{type(exc).__name__}: {exc}"
    rule = effective_rule_for(url, name)
    info["rule"] = (
        {
            "allowed_sources": list(rule.allowed_sources),
            "chunk_keywords": list(rule.chunk_keywords),
            "prefer_rendered": rule.prefer_rendered,
        }
        if rule is not None
        else None
    )
    return info


for site_name, site_url, pick in TARGETS:
    result[site_name] = snapshot(site_name, site_url)
    print(site_name, pick, json.dumps(result[site_name], ensure_ascii=False)[:600])

(OUT / "probe_291.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
)
