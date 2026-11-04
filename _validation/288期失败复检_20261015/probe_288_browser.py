# -*- coding: utf-8 -*-
"""288 期失败清单（9 站）逐站浏览器验证：渲染 + 静态抓取，判断「异常」还是「无数据」。

只读：证据写入本目录，不写任何业务文件。
产出 probe_288_browser_out.json / probe_288_<name>.txt|.html / probe_288_static_<name>.txt
"""
from __future__ import annotations

import gzip
import io
import json
import re
import socket
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.fetch.browser import render_browser_documents  # noqa: E402

HERE = Path(__file__).parent
FAIL = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\七类数据统一归纳失败\288期-尾-失败.txt")

TAG_RE = re.compile(r"<[^>]+>")
PERIOD_RE = re.compile(r"(\d{3})\s*期")
FAIL_RE = re.compile(r"^失败\s+(\S+)\s+(\S+)\s+方向:\s*(\S+)\s+期数:\s*(\d+)")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")


def parse_fail(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        m = FAIL_RE.match(line.strip())
        if m:
            out.append({"name": m.group(1), "url": m.group(2), "pick": m.group(3), "period": int(m.group(4))})
    return out


def to_text(doc: str) -> str:
    text = TAG_RE.sub("\n", doc) if "<" in doc else doc
    return re.sub(r"\n{2,}", "\n", text)


def static_fetch(url: str, timeout: int = 25) -> dict:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            body = raw.decode("utf-8", "replace")
            for enc in ("gb18030", "utf-8"):
                try:
                    body = raw.decode(enc)
                    break
                except Exception:
                    continue
            return {"ok": True, "status": resp.status, "len": len(raw),
                    "ctype": resp.headers.get("Content-Type"), "body": body}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": "HTTPError %s" % exc.code}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}


def summarize(text: str, name: str, period: int) -> dict:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    periods = sorted({int(m.group(1)) for m in PERIOD_RE.finditer(text)})
    name_lines = [ln for ln in lines if name in ln]
    per_lines = [ln for ln in lines if re.search(r"%d\s*期" % period, ln)]
    return {
        "nonempty_lines": len(lines),
        "periods_min_max": (periods[0], periods[-1]) if periods else None,
        "period_count": len(periods),
        "has_target_period": period in periods,
        "target_hits": text.count(str(period)),
        "name_hits": text.count(name),
        "has_name": name in text,
        "name_lines": name_lines[:6],
        "period_lines": per_lines[:8],
        "has_killed_draw_placeholder": bool(re.search(r"开\s*0{4}", text)),
        "suspicious_marks": [k for k in ("下架", "已被删除", "登录", "充值", "不存在", "无法访问", "禁止访问", "404") if k in text],
    }


def main() -> int:
    sites = parse_fail(FAIL)
    print("失败清单 %d 站" % len(sites))
    report = []
    for site in sites:
        name, url, period = site["name"], site["url"], site["period"]
        entry: dict = dict(site)
        print("\n===== %s (%s) %s =====" % (name, site["pick"], url))
        st = static_fetch(url)
        if st.get("ok"):
            text = to_text(st["body"])
            (HERE / ("static_%s.txt" % name)).write_text(text, encoding="utf-8")
            entry["static"] = summarize(text, name, period)
            entry["static"].update(status=st["status"], bytes=st["len"], ctype=st["ctype"])
            print("  静态: %s B %s 期号 %s 含%s=%s 含站名=%s" % (
                st["len"], st["ctype"], entry["static"]["periods_min_max"],
                period, entry["static"]["has_target_period"], entry["static"]["has_name"]))
            print("    站名行: %s" % entry["static"]["name_lines"][:2])
            print("    本期行: %s" % entry["static"]["period_lines"][:3])
        else:
            entry["static"] = {"ok": False, "error": st.get("error")}
            print("  静态: 失败 %s" % st.get("error"))
        try:
            docs = render_browser_documents(url, 45)
            text = to_text("\n".join(docs))
            (HERE / ("render_%s.txt" % name)).write_text(text, encoding="utf-8")
            (HERE / ("render_%s.html" % name)).write_text("\n".join(docs), encoding="utf-8")
            entry["render"] = summarize(text, name, period)
            entry["render"].update(doc_lengths=[len(d) for d in docs])
            print("  渲染: %s 期号 %s 含%s=%s 含站名=%s 占位=%s 可疑=%s" % (
                entry["render"]["doc_lengths"], entry["render"]["periods_min_max"],
                period, entry["render"]["has_target_period"], entry["render"]["has_name"],
                entry["render"]["has_killed_draw_placeholder"], entry["render"]["suspicious_marks"]))
            print("    站名行: %s" % entry["render"]["name_lines"][:3])
            print("    本期行: %s" % entry["render"]["period_lines"][:3])
        except Exception as exc:  # noqa: BLE001
            entry["render"] = {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}
            print("  渲染: 失败 %s: %s" % (type(exc).__name__, exc))
        report.append(entry)
    (HERE / "probe_288_browser_out.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n证据已写 probe_288_browser_out.json")
    return 0


if __name__ == "__main__":
    socket.setdefaulttimeout(30)
    sys.exit(main())
