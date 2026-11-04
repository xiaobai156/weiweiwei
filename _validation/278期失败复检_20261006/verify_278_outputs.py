# -*- coding: utf-8 -*-
"""只读交叉校验：278 期定向重跑后 成功TXT / 失败TXT / 缓存 三方一致。"""
import io, json, os, sys
from pathlib import Path

ROOT = Path(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2')
BASE = Path(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集')
SUCCESS = BASE / '七类数据统一归纳' / '278期-尾.txt'
FAIL = BASE / '七类数据统一归纳失败' / '278期-尾-失败.txt'
CACHE = ROOT / 'recent_10_cache.json'
sys.path.insert(0, str(ROOT))
from shawei.persistence import txt_writer  # noqa: E402

lines = SUCCESS.read_text(encoding='utf-8-sig').splitlines()
parsed = [(txt_writer.parse_success_line(line), line) for line in lines]
sites = {p[0][0]: p[0][2] for p in parsed if p[0]}
site_lines = [p[1] for p in parsed if p[0]]
values = [p[0][2] for p in parsed if p[0]]

payload = json.loads(CACHE.read_text(encoding='utf-8-sig'))
entries = payload['sites']
active = [e for e in entries if not e.get('archived')]
archived = [e for e in entries if e.get('archived')]
cache_value = {}
for e in active:
    periods = e.get('periods') or []
    vals = e.get('values') or []
    if payload['period'] in periods:
        cache_value[e['name']] = vals[periods.index(payload['period'])]

print('TXT 站点行=%d  唯一名=%d' % (len(site_lines), len(sites)))
print('缓存 条目=%d 活跃=%d 封存=%d  site_count=%s fail_count=%s vector_count=%s period=%s window=%s'
      % (len(entries), len(active), len(archived), payload.get('site_count'), payload.get('fail_count'),
         payload.get('vector_count'), payload.get('period'), payload.get('window')))
print('顶层 fail_lines=%d generated_at=%s' % (len(payload.get('fail_lines') or []), payload.get('generated_at')))

only_txt = sorted(set(sites) - set(cache_value))
only_cache = sorted(set(cache_value) - set(sites))
mismatch = sorted((n, sites[n], cache_value[n]) for n in set(sites) & set(cache_value) if sites[n] != cache_value[n])
print('仅TXT有=%s  仅缓存有=%s  值不一致=%s' % (only_txt, only_cache, mismatch))
print('TXT==活跃=%s  TXT==site_count=%s' % (len(sites) == len(cache_value), len(sites) == payload.get('site_count')))
print('千呼万唤 =', sites.get('千呼万唤'), '| 缓存 =', cache_value.get('千呼万唤'))

target = [e for e in entries if e.get('name') == '千呼万唤']
if target:
    t = target[0]
    print('目标条目 periods[:3]=%s values[:3]=%s extended=%s failed_periods=%s failure_reasons=%s archived=%s'
          % (t.get('periods', [])[:3], t.get('values', [])[:3], t.get('extended'),
             t.get('failed_periods'), list((t.get('failure_reasons') or {}).keys()), t.get('archived')))
else:
    print('目标条目 缺失!')

expected = txt_writer.format_ranking(site_lines, values)
print('排行榜一致=%s （TXT 尾 %d 行 vs 期望 %d 行）' % (lines == expected, len(lines), len(expected)))
if lines != expected:
    for i, (a, b) in enumerate(zip(lines, expected)):
        if a != b:
            print('  首个差异行 %d: TXT=%r 期望=%r' % (i + 1, a, b))
            break
    print('  尾部 TXT=%s' % lines[-12:])
    print('  尾部 期望=%s' % expected[-12:])
print('排行榜行=%s' % [l for l in lines if l.strip().endswith(tuple('0123456789')) and '次' not in l][-10:])
print('失败文件存在=%s' % FAIL.exists())
print('仍带 failed_periods 的活跃站=%s' % sorted(
    (e['name'], e.get('failed_periods')) for e in active if e.get('failed_periods')))
