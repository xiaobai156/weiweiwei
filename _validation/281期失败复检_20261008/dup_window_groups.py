# -*- coding: utf-8 -*-
"""只读：汇总杀尾-修复版2 缓存中「近 10 期逐期完全一致」的站点目录组。"""
import io, json, collections

CACHE = r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\recent_10_cache.json'
c = json.load(io.open(CACHE, encoding='utf-8-sig'))
top, window = int(c['period']), int(c['window'])
wanted = list(range(top, top - window, -1))
print('缓存: period=%s window=%s generated_at=%s' % (top, window, c.get('generated_at')))
print('窗口期号: %s' % wanted)


def window_map(item):
    periods, values = item.get('periods') or [], item.get('values') or []
    return {int(p): str(v) for p, v in zip(periods, values)}


active = [s for s in c['sites'] if not s.get('archived')]
archived = [s for s in c['sites'] if s.get('archived')]
full, partial = [], []
for s in c['sites']:
    m = window_map(s)
    (full if all(p in m for p in wanted) else partial).append((s, m))
print('条目 %d（活跃 %d / 封存 %d）；满 %d 期 = %d 条，不满 = %d 条'
      % (len(c['sites']), len(active), len(archived), window, len(full), len(partial)))
print('不满 10 期清单: %s' % [(s['name'], sorted(set(wanted) - set(m))) for s, m in partial])

groups = collections.defaultdict(list)
for s, m in full:
    groups[tuple(m[p] for p in wanted)].append(s)
dup = {k: v for k, v in groups.items() if len(v) >= 2}
print('--- 近 10 期逐期完全一致组数: %d ---' % len(dup))
for key, members in sorted(dup.items(), key=lambda kv: -len(kv[1])):
    print('组（%d 站）值序列 %s：' % (len(members), list(key)))
    for s in members:
        print('    %-10s pick=%-6s %s' % (s['name'], s.get('pick'), s.get('url')))

if not dup:
    print('（无）')

# 参考：3~9 期全等的弱重复对（供参考，不属「近10期完全一致」）
print('--- 参考：不足 10 期但 ≥3 期逐期全等的组 ---')
short = collections.defaultdict(list)
for s, m in full:
    short[tuple(m[p] for p in wanted)].append(s)
weak = collections.defaultdict(list)
for s in active:
    m = window_map(s)
    ks = sorted((p for p in wanted if p in m), reverse=True)
    weak[tuple((p, m[p]) for p in ks)].append(s)
for key, members in sorted(weak.items(), key=lambda kv: -len(kv[1])):
    if len(members) < 2 or len(key) >= window:
        continue
    print('  组（%d 站，%d 期全等）%s：%s' % (len(members), len(key), key, [x['name'] for x in members]))
