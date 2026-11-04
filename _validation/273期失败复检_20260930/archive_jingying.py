"""封存「精英战队」：只给缓存条目打 archived 标记，其余条目逐字段不动。

- 走项目现有 file_lock + 原子替换（_atomic_write_text_unlocked）
- 不改动该站的 periods/values/failed_periods 历史数据
- 不动 sites.json（由外部编辑完成）
- generated_at 保持不变（本次是标记动作，不是抓取运行）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shawei.persistence.atomic_file import _atomic_write_text_unlocked, file_lock  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "recent_10_cache.json"
TARGET_NAME = "精英战队"
TARGET_URL = "https://buzsxio.821n4-hgj04-edkrft.xyz:29455/article/manager/6a4e865857dc857ae1c13534?url=bxj"


def main() -> int:
    with file_lock(CACHE):
        payload = json.loads(CACHE.read_text(encoding="utf-8-sig"))
        old_items = payload["sites"]

        hits = [i for i, it in enumerate(old_items)
                if it.get("name") == TARGET_NAME and it.get("url") == TARGET_URL]
        if len(hits) != 1:
            print(f"拒绝执行: 命中 {len(hits)} 条，期望唯一", file=sys.stderr)
            return 2
        idx = hits[0]
        if old_items[idx].get("archived"):
            print("已是封存状态，无改动")
            return 0

        new_items = []
        for i, item in enumerate(old_items):
            if i != idx:
                new_items.append(item)  # 原对象原样保留
                continue
            marked = dict(item)
            marked["archived"] = True
            new_items.append(marked)

        # 逐字段核验：除目标外，其余条目必须逐字段完全一致
        diffs = [
            old_items[i].get("name")
            for i in range(len(old_items))
            if i != idx and json.dumps(old_items[i], ensure_ascii=False, sort_keys=True)
            != json.dumps(new_items[i], ensure_ascii=False, sort_keys=True)
        ]
        if diffs:
            print(f"拒绝执行: 非目标条目被改动 {diffs}", file=sys.stderr)
            return 3

        target = new_items[idx]
        prefix = f"失败 {TARGET_NAME} {TARGET_URL} 方向: bottom "
        old_fail_lines = list(payload.get("fail_lines") or [])
        new_fail_lines = [ln for ln in old_fail_lines if not str(ln).startswith(prefix)]

        payload["sites"] = new_items
        payload["site_count"] = sum(1 for it in new_items if not it.get("archived"))
        payload["fail_count"] = sum(
            1 for it in new_items if not it.get("archived") and it.get("failed_periods")
        )
        payload["fail_lines"] = new_fail_lines

        _atomic_write_text_unlocked(
            CACHE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    print(
        "封存完成: sites.json 已标记；缓存条目 archived=true，"
        f"periods={target.get('periods')} values={target.get('values')} "
        f"failed_periods={target.get('failed_periods')} 保持原样"
    )
    print(
        f"fail_lines {len(old_fail_lines)}→{len(new_fail_lines)}；"
        f"site_count={payload['site_count']} fail_count={payload['fail_count']}；"
        f"站点条目总数 {len(new_items)} 不变；generated_at={payload['generated_at']} 未改"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
