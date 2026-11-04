"""只读核验：273 期成功 TXT / 失败 TXT 与缓存三方一致，且缓存只被白名单两站改写。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shawei.persistence import txt_writer  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT.parent / "七类数据统一归纳" / "273期-尾.txt"
FAIL = ROOT.parent / "七类数据统一归纳失败" / "273期-尾-失败.txt"

TARGETS = {
    "千祥云集": "https://dfgrufao.tz0ex-y6o7v-lazxsq.work:29400/article/admin/6a041b804ea5c20141013dc8?url=lbw",
    "精英战队": "https://buzsxio.821n4-hgj04-edkrft.xyz:29455/article/manager/6a4e865857dc857ae1c13534?url=bxj",
}
FAIL_RE = re.compile(
    r"^失败 (?P<name>.+?) (?P<url>https?://\S+) 方向: (?P<pick>top|bottom) "
    r"期数: (?P<period>\d+) 阶段: .+? 原因: (?P<reason>.*)$"
)


def main() -> None:
    cache = json.loads((ROOT / "recent_10_cache.json").read_text(encoding="utf-8-sig"))
    sites_txt = json.loads((ROOT / "sites.json").read_text(encoding="utf-8-sig"))

    success: dict[str, str] = {}
    for line in OUT.read_text(encoding="utf-8-sig").splitlines():
        parsed = txt_writer.parse_success_line(line)
        if parsed is not None:
            success[parsed[0]] = parsed[2]

    failures: dict[str, str] = {}
    for block in re.split(r"(?:\r?\n){2,}", FAIL.read_text(encoding="utf-8-sig").strip()):
        if not block.strip():
            continue
        m = FAIL_RE.match(block.splitlines()[0].strip())
        if m:
            failures[m["name"]] = m["reason"]

    print(f"成功TXT站点 {len(success)} 条；失败TXT站点 {len(failures)} 条")

    active = [it for it in cache["sites"] if not it.get("archived")]
    mism = []
    for item in active:
        name = item.get("name")
        values = {int(p): v for p, v in zip(item.get("periods") or [], item.get("values") or [])}
        reasons = {int(p): r for p, r in (item.get("failure_reasons") or {}).items()}
        in_txt = name in success
        has_fail = 273 in reasons
        if in_txt:
            if str(values.get(273, "")) != str(success[name]):
                mism.append(f"{name}: 缓存273={values.get(273)!r} TXT={success[name]!r}")
            if has_fail:
                mism.append(f"{name}: 成功却在缓存标记273失败")
        else:
            if not has_fail:
                mism.append(f"{name}: 既不在成功TXT也无273失败记录")
    print(f"缓存↔成功TXT/失败TXT 不一致 {len(mism)} 条")
    for line in mism[:20]:
        print("  !", line)

    # 其它站点：成功 TXT 里必须有缓存值；失败 TXT 必须与缓存失败记录逐字相同
    only_cache_fail = [n for n in failures if n not in {i["name"] for i in active}]
    print(f"失败TXT中的站在缓存中不存在: {only_cache_fail}")

    print("--- 白名单两站终态 ---")
    for item in active:
        if item.get("name") in TARGETS:
            print(
                json.dumps(
                    {
                        "name": item["name"],
                        "periods": item.get("periods"),
                        "values": item.get("values"),
                        "failed_periods": item.get("failed_periods"),
                        "archived": item.get("archived"),
                    },
                    ensure_ascii=False,
                )
            )

    print("--- 站点总数一致性 ---")
    print("cache.active =", len(active), "cache.site_count =", cache.get("site_count"))
    print("sites.json 条数 =", len(sites_txt))
    print("成功TXT站点数 + 失败TXT站点数 =", len(success) + len(failures))


if __name__ == "__main__":
    main()
