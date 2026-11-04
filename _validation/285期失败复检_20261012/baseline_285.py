"""285 期开工基线：只读打印五文件哈希、缓存/站点/health 条目、规则与解析器。"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\七类数据统一归纳")
FAIL_DIR = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\七类数据统一归纳失败")
FAIL_URL = "https://qvuuqqs.8imf7-hteuh-ylwuqv.xyz/#/forums/15340352"
FAIL_NAME = "曾氏"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> int:
    files = {
        "285期-尾.txt": OUT_DIR / "285期-尾.txt",
        "285期-尾-失败.txt": FAIL_DIR / "285期-尾-失败.txt",
        "recent_10_cache.json": ROOT / "recent_10_cache.json",
        "sites.json": ROOT / "sites.json",
        "shawei_site_health.json": ROOT / "shawei_site_health.json",
    }
    print("== 哈希/大小 ==")
    for label, path in files.items():
        if path.exists():
            print(f"{label}: {path.stat().st_size} B {sha(path)}")
        else:
            print(f"{label}: <不存在>")

    cache = json.loads((ROOT / "recent_10_cache.json").read_text(encoding="utf-8-sig"))
    print("\n== 缓存顶层 ==")
    for key in ("period", "window", "site_count", "fail_count", "generated_at", "vector_count"):
        print(f"{key}={cache.get(key)!r}")
    sites = cache.get("sites", [])
    print(f"条目数={len(sites)} 封存={sum(1 for s in sites if s.get('archived'))} 失败行={len(cache.get('fail_lines', []))}")
    print("fail_lines:", json.dumps(cache.get("fail_lines"), ensure_ascii=False))
    for item in sites:
        if item.get("name") == FAIL_NAME:
            print("\n== 缓存目标条目 ==")
            print(json.dumps(item, ensure_ascii=False, indent=1))

    rows = json.loads((ROOT / "sites.json").read_text(encoding="utf-8-sig"))
    print(f"\n== sites.json: 总 {len(rows)} 活跃 {sum(1 for r in rows if not r.get('archived'))} 封存 {sum(1 for r in rows if r.get('archived'))} ==")
    for i, row in enumerate(rows):
        if row.get("name") == FAIL_NAME:
            print(f"idx={i}", json.dumps(row, ensure_ascii=False))

    health = json.loads((ROOT / "shawei_site_health.json").read_text(encoding="utf-8-sig"))
    entry = health.get(FAIL_URL)
    print("\n== health 目标条目 ==")
    print(json.dumps(entry, ensure_ascii=False, indent=1) if entry else "<未找到>")

    print("\n== 失败 TXT 原文 ==")
    fail_path = FAIL_DIR / "285期-尾-失败.txt"
    if fail_path.exists():
        print(fail_path.read_text(encoding="utf-8-sig"))
    print("\n== 成功 TXT 是否含目标站 ==")
    out_path = OUT_DIR / "285期-尾.txt"
    if out_path.exists():
        text = out_path.read_text(encoding="utf-8-sig")
        print(f"行数={len(text.splitlines())} 含'{FAIL_NAME}'={'曾氏' in text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
