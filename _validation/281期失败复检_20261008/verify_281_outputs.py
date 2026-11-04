# -*- coding: utf-8 -*-
"""只读交叉校验：281 期定向重跑后 成功TXT / 失败TXT / 缓存 三方一致。"""
import json, os, sys
from pathlib import Path

ROOT = Path(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2')
BASE = Path(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集')
PERIOD = 281
SUCCESS = BASE / '七类数据统一归纳' / f'{PERIOD}期-尾.txt'
FAIL = BASE / '七类数据统一归纳失败' / f'{PERIOD}期-尾-失败.txt'
CACHE = ROOT / 'recent_10_cache.json'
sys.path.insert(0, str(ROOT))
from shawei.persistence import txt_writer  # noqa: E402

lines = SUCCESS.read_text(encoding='utf-8-sig').splitlines()
parsed = {}
for l in lines:
    p = txt_writer.parse_success_line(l)
    if p:
        parsed[p[0]] = p[2]
site_lines = [l for l in lines if txt_writer.parse_success_line(l)]
payload = json.loads(CACHE.read_text(encoding='utf-8-sig'))
entries = payload['sites']
active = [e for e in entries if not e.get('archived')]
cache_value = {}
for e in active:
    periods, vals = e.get('periods') or [], e.get('values') or []
    if payload['period'] in periods:
        cache_value[e['name']] = vals[periods.index(payload['period'])]
print('TXT 站点行=%d 唯一名=%d' % (len(site_lines), len(parsed)))
print('缓存 条目=%d 活跃=%d site_count=%s fail_count=%s vector=%s period=%s fail_lines=%d gen=%s'
      % (len(entries), len(active), payload.get('site_count'), payload.get('fail_count'),
         payload.get('vector_count'), payload.get('period'),
         len(payload.get('fail_lines') or []), payload.get('generated_at')))
print('仅TXT=%s 仅缓存=%s 值不一致=%s' % (
    sorted(set(parsed) - set(cache_value)), sorted(set(cache_value) - set(parsed)),
    sorted((n, parsed[n], cache_value[n]) for n in set(parsed) & set(cache_value) if parsed[n] != cache_value[n])))
print('TXT==有值活跃站=%s' % (len(parsed) == len(cache_value)))
for n in ('傻不拉几', '水火不容', '天涯浪子'):
    print('  %s TXT=%s 缓存=%s' % (n, parsed.get(n), cache_value.get(n)))
for e in entries:
    if e['name'] in ('傻不拉几', '水火不容', '天涯浪子'):
        print('  条目 %s periods[:3]=%s values[:3]=%s extended=%s failed=%s' % (
            e['name'], (e.get('periods') or [])[:3], (e.get('values') or [])[:3],
            e.get('extended'), e.get('failed_periods')))
expected = txt_writer.format_ranking(site_lines, [txt_writer.parse_success_line(l)[2] for l in site_lines])
print('排行榜一致=%s (TXT %d 行 vs 期望 %d 行)' % (lines == expected, len(lines), len(expected)))
print('失败文件存在=%s' % FAIL.exists())
print('仍带 failed_periods 的活跃站=%s' % sorted((e['name'], e.get('failed_periods')) for e in active if e.get('failed_periods')))
print('残留=%s' % [x for x in os.listdir(ROOT) if x.endswith(('.bak', '.lock', '.tmp'))])
