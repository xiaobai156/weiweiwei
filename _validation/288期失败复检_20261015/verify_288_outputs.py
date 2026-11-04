# -*- coding: utf-8 -*-
"""只读交叉校验：288 期定向重跑后 成功TXT / 失败TXT / 缓存 三方一致。"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2')
BASE = Path(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集')
PERIOD = 288
SUCCESS = BASE / '七类数据统一归纳' / f'{PERIOD}期-尾.txt'
FAIL = BASE / '七类数据统一归纳失败' / f'{PERIOD}期-尾-失败.txt'
CACHE = ROOT / 'recent_10_cache.json'
sys.path.insert(0, str(ROOT))
from shawei.persistence import txt_writer  # noqa: E402

EXPECT = {'两小无猜': '2', '坚持战斗': '2', '无量寿佛': '1', '童颜鹤发': '6',
          '怪咖小生': '2,8', '澳彩碼王': '4', '寻宝探码': '7', '财源滚滚': '9', '海角天涯': '1'}

lines = SUCCESS.read_text(encoding='utf-8-sig').splitlines()
parsed = {p[0]: p[2] for p in (txt_writer.parse_success_line(l) for l in lines) if p}
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
print('缓存 条目=%d 活跃=%d 封存=%d site_count=%s fail_count=%s vector=%s period=%s window=%s fail_lines=%d gen=%s'
      % (len(entries), len(active), len(entries) - len(active), payload.get('site_count'),
         payload.get('fail_count'), payload.get('vector_count'), payload.get('period'),
         payload.get('window'), len(payload.get('fail_lines') or []), payload.get('generated_at')))
print('仅TXT=%s 仅缓存=%s 值不一致=%s' % (
    sorted(set(parsed) - set(cache_value)), sorted(set(cache_value) - set(parsed)),
    sorted((n, parsed[n], cache_value[n]) for n in set(parsed) & set(cache_value) if parsed[n] != cache_value[n])))
print('TXT==有当期值的活跃站=%s' % (len(parsed) == len(cache_value)))

print('\n--- 本次 9 站 ---')
for name, want in EXPECT.items():
    e = next((x for x in entries if x['name'] == name), None)
    print('  %-6s 期望=%-3s TXT=%-5s 缓存=%-5s 条目 periods[:3]=%s values[:3]=%s failed=%s archived=%s'
          % (name, want, parsed.get(name), cache_value.get(name),
             (e or {}).get('periods', [])[:3], (e or {}).get('values', [])[:3],
             (e or {}).get('failed_periods'), (e or {}).get('archived')))
    ok = parsed.get(name) == want and cache_value.get(name) == want
    print('         %s' % ('OK' if ok else '!!! 与渲染证据不符'))

expected = txt_writer.format_ranking(site_lines, [txt_writer.parse_success_line(l)[2] for l in site_lines])
print('\n排行榜一致=%s (TXT %d 行 vs 期望 %d 行)' % (lines == expected, len(lines), len(expected)))
print('失败文件存在=%s' % FAIL.exists())
print('仍失败活跃站=%s' % sorted((e['name'], e.get('failed_periods')) for e in active if e.get('failed_periods')))
print('残留=%s' % [x for x in os.listdir(ROOT) if x.endswith(('.bak', '.lock', '.tmp'))])
print('失败目录残留=%s' % [x for x in os.listdir(str(FAIL.parent)) if x.endswith(('.bak', '.lock', '.tmp'))])
