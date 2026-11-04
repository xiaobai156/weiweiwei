# -*- coding: utf-8 -*-
"""封存「劲爆猛料」：只给缓存条目打 archived 标记，其余条目逐字段不动。

- 走项目现有 file_lock + 原子替换（_atomic_write_text_unlocked）
- 冻结该站 periods/values/extended/failed_periods/failure_reasons
- 不动 sites.json（由外部编辑完成）；generated_at 保持不变（标记动作，非抓取运行）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2')
sys.path.insert(0, str(ROOT))
from shawei.persistence.atomic_file import _atomic_write_text_unlocked, file_lock  # noqa: E402

CACHE = ROOT / 'recent_10_cache.json'
TARGET_NAME = '劲爆猛料'
TARGET_URL = 'https://67806780827.234535.xyz/bbs/topic.php?id=19587'
FROZEN_KEYS = ('periods', 'values', 'extended', 'failed_periods', 'failure_reasons')


def main() -> int:
    with file_lock(CACHE):
        payload = json.loads(CACHE.read_text(encoding='utf-8-sig'))
        old_items = payload['sites']
        hits = [i for i, it in enumerate(old_items)
                if it.get('name') == TARGET_NAME and it.get('url') == TARGET_URL]
        if len(hits) != 1:
            print('拒绝执行: 命中 %d 条，期望唯一' % len(hits), file=sys.stderr)
            return 2
        idx = hits[0]
        if old_items[idx].get('archived'):
            print('已是封存状态，无改动')
            return 0

        new_items = []
        for i, item in enumerate(old_items):
            if i != idx:
                new_items.append(item)
                continue
            marked = dict(item)
            marked['archived'] = True
            new_items.append(marked)

        diffs = [old_items[i].get('name') for i in range(len(old_items))
                 if i != idx and json.dumps(old_items[i], ensure_ascii=False, sort_keys=True)
                 != json.dumps(new_items[i], ensure_ascii=False, sort_keys=True)]
        if diffs:
            print('拒绝执行: 非目标条目被改动 %s' % diffs, file=sys.stderr)
            return 3
        for key in FROZEN_KEYS:
            if json.dumps(old_items[idx].get(key), ensure_ascii=False, sort_keys=True) != \
               json.dumps(new_items[idx].get(key), ensure_ascii=False, sort_keys=True):
                print('拒绝执行: 目标条目 %s 被改动' % key, file=sys.stderr)
                return 4

        target = new_items[idx]
        prefix = '失败 %s %s 方向: bottom ' % (TARGET_NAME, TARGET_URL)
        old_fail_lines = list(payload.get('fail_lines') or [])
        new_fail_lines = [ln for ln in old_fail_lines if not str(ln).startswith(prefix)]

        old_site_count, old_fail_count = payload['site_count'], payload['fail_count']
        payload['sites'] = new_items
        payload['site_count'] = sum(1 for it in new_items if not it.get('archived'))
        payload['fail_count'] = sum(1 for it in new_items
                                    if not it.get('archived') and it.get('failed_periods'))
        payload['fail_lines'] = new_fail_lines

        _atomic_write_text_unlocked(
            CACHE, json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print('封存完成: 缓存条目 archived=true，periods=%s values=%s failed=%s 保持原样'
          % (target.get('periods'), target.get('values'), target.get('failed_periods')))
    print('site_count %s→%s；fail_count %s→%s；fail_lines %s→%s；条目总数 %d 不变；generated_at=%s 未改'
          % (old_site_count, payload['site_count'], old_fail_count, payload['fail_count'],
             len(old_fail_lines), len(new_fail_lines), len(new_items), payload['generated_at']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
