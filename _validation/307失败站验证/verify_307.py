"""307 期失败站逐站真实验证（只读：不写正式 JSON/TXT/缓存）。"""
from __future__ import annotations

import json
import re
import sys
import traceback
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2")
sys.path.insert(0, str(ROOT))

from shawei.config.paths import FAIL_OUTPUT_DIR, OUTPUT_DIR  # noqa: E402
from shawei.config.sites import load_sites  # noqa: E402
from shawei.services.crawl_site import crawl_current_site  # noqa: E402

PERIOD = 307
OUT = Path(__file__).with_name("verify_307.json")
FAIL_PATH = FAIL_OUTPUT_DIR / f"{PERIOD}期-尾-失败.txt"

FAIL_RE = re.compile(
    r"^失败 (?P<name>.+?) (?P<url>https?://\S+) 方向: (?P<pick>top|bottom) "
    r"期数: (?P<period>\d+) 阶段: .+? 原因: (?P<reason>.*)$"
)


def blocks(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    return [b.strip() for b in re.split(r"(?:\r?\n){2,}", text.strip()) if b.strip()]


def classify(result) -> str:
    if result.success_line:
        return "有数据-成功"
    reason = result.failure_reason or ""
    no_data_marks = ("没有找到", "绝对top边界", "绝对bottom边界", "不是指定", "没有307期", "没有可验证尾数字段")
    if any(m in reason for m in no_data_marks):
        return "无数据-未发布307期"
    return "异常-传输/渲染"


def main() -> int:
    sites = load_sites()
    by_identity = {(s.name, s.url, s.pick): s for s in sites}
    targets = []
    seen = set()
    unmatched = []
    for block in blocks(FAIL_PATH):
        m = FAIL_RE.match(block.splitlines()[0].strip())
        if not m or int(m["period"]) != PERIOD:
            continue
        key = (m["name"], m["url"], m["pick"])
        if key in seen:
            continue
        seen.add(key)
        site = by_identity.get(key)
        if site is None:
            unmatched.append(key)
            continue
        targets.append(site)

    print(f"失败TXT站点 {len(seen)} 个，命中sites.json {len(targets)}，未命中 {len(unmatched)}", flush=True)
    for u in unmatched:
        print("  未在配置中:", u, flush=True)

    rows = []
    for n, site in enumerate(targets, 1):
        index = next(i for i, s in enumerate(sites, 1) if s is site)
        try:
            result = crawl_current_site(index, len(sites), site, PERIOD, 12, retries=1)
            row = {
                "name": site.name,
                "url": site.url,
                "pick": site.pick,
                "status": classify(result),
                "success_line": result.success_line,
                "failure_stage": result.failure_stage,
                "failure_reason": result.failure_reason,
                "messages": result.messages,
            }
        except Exception as exc:  # noqa: BLE001
            row = {
                "name": site.name,
                "url": site.url,
                "pick": site.pick,
                "status": "异常-未捕获异常",
                "success_line": None,
                "failure_stage": "验证脚本",
                "failure_reason": f"{type(exc).__name__}: {exc}",
                "messages": [traceback.format_exc()],
            }
        rows.append(row)
        print(f"[{n}/{len(targets)}] {row['status']:<18} {site.name} {row['success_line'] or (row['failure_reason'] or '')[:90]}", flush=True)
        OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {}
    for r in rows:
        summary[r["status"]] = summary.get(r["status"], 0) + 1
    print("汇总:", json.dumps(summary, ensure_ascii=False), flush=True)
    print("已写", OUT, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
