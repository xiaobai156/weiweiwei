"""305 期失败站网络可达性分类探针（只读，不写正式输出）。"""
from __future__ import annotations

import json
import re
import socket
import ssl
import sys
from pathlib import Path
from urllib.parse import urlsplit

FAIL_PATH = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\七类数据统一归纳失败\305期-尾-失败.txt")
OUT = Path(__file__).with_name("net_probe_305.json")

FAIL_RE = re.compile(
    r"^失败 (?P<name>.+?) (?P<url>https?://\S+) 方向: (?P<pick>top|bottom) "
    r"期数: (?P<period>\d+) 阶段: .+? 原因: (?P<reason>.*)$"
)


def blocks(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    return [b.strip() for b in re.split(r"(?:\r?\n){2,}", text.strip()) if b.strip()]


def parse() -> list[dict]:
    rows = []
    for block in blocks(FAIL_PATH):
        m = FAIL_RE.match(block.splitlines()[0].strip())
        if not m:
            continue
        rows.append({"name": m["name"], "url": m["url"], "pick": m["pick"], "period": int(m["period"])})
    return rows


def probe(row: dict) -> dict:
    u = urlsplit(row["url"])
    host = u.hostname or ""
    port = u.port or (443 if u.scheme == "https" else 80)
    out = dict(row, host=host, port=port, dns=None, tcp=None, tls=None, http=None, detail="")
    try:
        infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        out["dns"] = sorted({i[4][0] for i in infos})
    except Exception as exc:  # noqa: BLE001
        out["dns"] = f"FAIL {type(exc).__name__}: {exc}"
        return out
    try:
        s = socket.create_connection((host, port), timeout=8)
        out["tcp"] = "ok"
        if u.scheme == "https":
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            try:
                ss = ctx.wrap_socket(s, server_hostname=host)
                out["tls"] = f"ok {ss.version()}"
                ss.close()
            except Exception as exc:  # noqa: BLE001
                out["tls"] = f"FAIL {type(exc).__name__}: {exc}"
                s.close()
        else:
            s.close()
    except Exception as exc:  # noqa: BLE001
        out["tcp"] = f"FAIL {type(exc).__name__}: {exc}"
    return out


def main() -> int:
    rows = parse()
    print(f"失败站 {len(rows)} 个，期数 {sorted({r['period'] for r in rows})}")
    results = []
    for row in rows:
        r = probe(row)
        results.append(r)
        print(f"{r['name']:<8} tcp={r['tcp']!s:<60.60} tls={r['tls']!s:<40.40}")
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("已写", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
