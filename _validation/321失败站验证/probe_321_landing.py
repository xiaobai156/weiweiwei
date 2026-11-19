"""血气方刚 321：landing-page-data 全量里查目标 ID / 站名，确认是否被站方下架。"""

from __future__ import annotations

import base64
import binascii
import json
import sys
import urllib3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BASE = "https://xjsjbkv.b3e4x-wxhjo-lbdbjg.xyz:29477"
TARGET_ID = "6a3978d3018539c611cb8920"
NAME = "血气方刚"

urllib3.disable_warnings()


def decode_b64(text: str) -> str:
    try:
        return base64.b64decode(text + "=" * (-len(text) % 4)).decode("utf-8", "ignore")
    except (binascii.Error, ValueError):
        return ""


def main() -> None:
    import requests

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    session.verify = False
    url = f"{BASE}/api/proxy/landing-page-data?url=jbx"
    resp = session.get(url, timeout=60)
    body = resp.text
    (OUT / "landing_321.json").write_text(body, encoding="utf-8")
    print("状态", resp.status_code, "长度", len(body))
    print("目标ID 出现次数:", body.count(TARGET_ID))

    data = json.loads(body)
    hits = []

    def walk(node, path=""):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}[{i}]")
        elif isinstance(node, str):
            if node == TARGET_ID or TARGET_ID in node:
                hits.append((path, "直接命中"))
            elif len(node) > 8 and "/" not in node and " " not in node:
                if decode_b64(node).strip() == NAME:
                    hits.append((path, f"base64命中:{node[:40]}"))

    walk(data)
    print("遍历命中:", hits)

    print("明文 血气方刚 次数:", body.count(NAME))
    authors = set()

    def collect(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"authorNickname", "nickname", "author"} and isinstance(value, str) and value:
                    authors.add(value)
                collect(value)
        elif isinstance(node, list):
            for value in node:
                collect(value)

    collect(data)
    decoded = {decode_b64(a).strip() for a in authors if decode_b64(a).strip()}
    print("作者数:", len(authors), "解码后:", len(decoded))
    print("含目标站名:", NAME in decoded)
    (OUT / "landing_authors_321.json").write_text(
        json.dumps({"raw": sorted(authors), "decoded": sorted(decoded), "has_target": NAME in decoded}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
