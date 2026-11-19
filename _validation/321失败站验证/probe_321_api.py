"""血气方刚 321 期接口取证：manager 接口是否真空，页面是否仍可渲染。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.fetch.dynamic_article import manager_article_api_urls  # noqa: E402

OUT = Path(__file__).resolve().parent
TARGET = "https://xjsjbkv.b3e4x-wxhjo-lbdbjg.xyz:29477/article/manager/6a3978d3018539c611cb8920?url=jbx"
SIBLING = "https://xjsjbkv.b3e4x-wxhjo-lbdbjg.xyz:29477/article/manager/6a3abfde018539c611cbec6a?url=jbx"


def main() -> None:
    import requests

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )
        }
    )
    session.verify = False
    report = {}
    for label, url in (("target", TARGET), ("sibling", SIBLING)):
        for api in manager_article_api_urls(url):
            try:
                resp = session.get(api, timeout=20)
                body = resp.text
                report.setdefault(label, []).append(
                    {"api": api, "status": resp.status_code, "len": len(body), "head": body[:200]}
                )
                print(label, resp.status_code, len(body), api)
                if resp.status_code == 200:
                    print("  片段:", body[:300].replace("\n", " "))
            except Exception as exc:  # pragma: no cover
                report.setdefault(label, []).append({"api": api, "error": f"{type(exc).__name__}: {exc}"})
                print(label, "ERR", type(exc).__name__, exc)
        try:
            page = session.get(url, timeout=25)
            print(label, "页面", page.status_code, len(page.text), "含站名:", "血气方刚" in page.text)
            (OUT / f"page_{label}.html").write_text(page.text, encoding="utf-8", errors="replace")
            report.setdefault(label, []).append(
                {"page": url, "status": page.status_code, "len": len(page.text), "has_name": "血气方刚" in page.text}
            )
        except Exception as exc:  # pragma: no cover
            print(label, "页面 ERR", type(exc).__name__, exc)
    (OUT / "probe_321_api.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
