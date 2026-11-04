# -*- coding: utf-8 -*-
"""288 期失败清单处置：开工前只读状态快照（不写业务文件）。"""
import hashlib
import json
import os

PROJ = r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2"
OK = r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\七类数据统一归纳"
FAIL = r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\七类数据统一归纳失败"


def sha(p):
    if not os.path.exists(p):
        return "MISSING"
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest().upper()


def load_json(p):
    raw = open(p, "rb").read()
    for enc in ("utf-8-sig", "gb18030", "utf-8"):
        try:
            return json.loads(raw.decode(enc)), enc
        except Exception:
            continue
    raise RuntimeError("cannot decode " + p)


def read_text(p):
    raw = open(p, "rb").read()
    for enc in ("utf-8-sig", "gb18030", "utf-8"):
        try:
            return raw.decode(enc), enc
        except Exception:
            continue
    return raw.decode("utf-8", "replace"), "replace"


print("=== 文件哈希 ===")
for p in (
    os.path.join(FAIL, "288期-尾-失败.txt"),
    os.path.join(OK, "288期-尾.txt"),
    os.path.join(PROJ, "recent_10_cache.json"),
    os.path.join(PROJ, "sites.json"),
    os.path.join(PROJ, "shawei_site_health.json"),
):
    print(" ", os.path.basename(p), os.path.getsize(p) if os.path.exists(p) else "-", sha(p))

cache, enc = load_json(os.path.join(PROJ, "recent_10_cache.json"))
print("\n=== cache 顶层 (编码 %s) ===" % enc)
print(" ", {k: v for k, v in cache.items() if not isinstance(v, (list, dict))})
print("  keys:", list(cache.keys()))
items = None
for k in ("sites", "items", "active_sites", "records"):
    if isinstance(cache.get(k), list):
        items = cache[k]
        print("  items key =", k)
        break
if items is None:
    for k, v in cache.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            items = v
            print("  items key(fallback) =", k)
            break
print("  条目 %d 封存 %d" % (len(items), sum(1 for i in items if i.get("archived"))))
fl = cache.get("fail_lines") or []
print("  fail_lines %d:" % len(fl))
for line in fl:
    print("    ", line)
print("\n=== 失败期为 288 / 287 的条目 ===")
for it in items:
    fp = it.get("failed_periods") or []
    if 288 in fp or 287 in fp:
        fr = it.get("failure_reasons") or {}
        print(" ", it.get("name"), "archived=%s" % it.get("archived"),
              "periods=%s" % (it.get("periods") or [])[:4],
              "failed=%s" % fp[:4])
        for per in (288, 287):
            if per in fp:
                print("      %d: %s" % (per, fr.get(str(per)) or fr.get(per)))

txt, enc2 = read_text(os.path.join(OK, "288期-尾.txt"))
lines = txt.splitlines()
print("\n=== 288期-尾.txt (%d 行, 编码 %s) ===" % (len(lines), enc2))
print("  前 3 行:", lines[:3])
print("  尾 3 行:", lines[-3:])
names = ["两小无猜", "坚持战斗", "无量寿佛", "童颜鹤发", "怪咖小生",
         "澳彩碼王", "寻宝探码", "财源滚滚", "海角天涯"]
for n in names:
    hit = [l for l in lines if n in l]
    print("  %-6s 在成功 TXT 中: %s" % (n, hit[:1] if hit else "无"))

site = json.loads(read_text(os.path.join(PROJ, "sites.json"))[0])
print("\n=== sites.json 条目 %d ===" % len(site))
for n in names:
    for s in (site if isinstance(site, list) else site.get("sites", [])):
        if s.get("name") == n:
            print("  ", n, s.get("pick"), s.get("url"), "archived=%s" % s.get("archived"))
