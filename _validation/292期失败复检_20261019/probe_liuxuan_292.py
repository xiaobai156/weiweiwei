"""六玄网（87127）手动链路探测：入口 -> yjjy/wenzhang.js -> iframe 正文 -> zhjs 脚本，看当前期号。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.fetch.decoding import decode_document_writeln_html  # noqa: E402
from shawei.fetch.http_client import fetch_text  # noqa: E402

URL = "https://lx11.www87127b.com:8443/#87127"
OUT = Path(__file__).resolve().parent
info: dict[str, object] = {}

page = fetch_text(URL, 20)
loader_url = urljoin(URL, "yjjy/wenzhang.js")
info["loader_url"] = loader_url
loader = fetch_text(loader_url, 20)
loader_html = decode_document_writeln_html(loader)
(OUT / "liuxuan_loader.html").write_text(loader_html, encoding="utf-8")
iframes = re.findall(r"<iframe\b[^>]*\bsrc\s*=\s*['\"]([^'\"]+)['\"]", loader_html, flags=re.I)
info["iframes"] = iframes
print("iframes", iframes)

if len(iframes) == 1:
    detail_url = urljoin(URL, iframes[0])
    info["detail_url"] = detail_url
    detail = fetch_text(detail_url, 20)
    (OUT / "liuxuan_detail.html").write_text(detail, encoding="utf-8")
    info["detail_has_anchor"] = "六玄网论坛" in detail
    zhjs = re.search(
        r"<div\b[^>]*\bid\s*=\s*['\"]zhjs['\"][^>]*>\s*<script\b[^>]*\bsrc\s*=\s*(['\"])(.*?)\1",
        detail,
        flags=re.I | re.S,
    )
    if zhjs:
        zhjs_url = urljoin(detail_url, zhjs.group(2))
        info["zhjs_url"] = zhjs_url
        script = fetch_text(zhjs_url, 20)
        html = decode_document_writeln_html(script)
        (OUT / "liuxuan_zhjs.html").write_text(html, encoding="utf-8")
        plain = re.sub(r"<[^>]+>", " ", html)
        periods = sorted({int(m) for m in re.findall(r"(\d{3})\s*期", plain)})
        info["zhjs_periods_tail"] = periods[-8:]
        info["zhjs_periods_max"] = periods[-1] if periods else None
        info["zhjs_has_292"] = 292 in periods
        idx = plain.find("综合绝杀")
        info["zhjs_sample"] = re.sub(r"\s+", " ", plain[max(0, idx - 100): idx + 500])
    else:
        info["zhjs_error"] = "zhjs 脚本未匹配"

print(json.dumps(info, ensure_ascii=False, indent=2)[:3000])
(OUT / "liuxuan_probe.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
