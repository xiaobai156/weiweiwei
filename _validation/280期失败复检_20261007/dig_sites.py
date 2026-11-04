# -*- coding: utf-8 -*-
"""只读深挖：三站 HTML 内 280 期行/表格的结构（用项目自带 TableParser）。"""
import io, os, re, sys
ROOT = r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2'
os.chdir(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\_validation\280期失败复检_20261007')
sys.path.insert(0, ROOT)
from shawei.parsers.common import TableParser  # noqa: E402

print('#' * 30, '赤兔：含「尾」表头的表格')
html = io.open('probe_chitu_280.html', encoding='utf-8').read()
parser = TableParser()
parser.feed(html)
parser.close()
print('表格数=%d 行组数=%d' % (len(parser.tables), len(parser.rows)))
hit = 0
for ti, table in enumerate(parser.tables):
    head = ' '.join(table[0]) if table else ''
    if not re.search(r'尾', head):
        continue
    hit += 1
    periods = []
    for row in table:
        m = re.search(r'(\d{3})\s*期', row[0]) if row else None
        if m:
            periods.append((int(m.group(1)), ' | '.join(x[:18] for x in row[:6])))
    print('--- 表%d 行数=%d 表头=%r' % (ti, len(table), head[:110]))
    print('    期号行数=%d 最新5行=%s' % (len(periods), [p for p in sorted(periods)[-5:]]))
    if not periods:
        print('    前3行=%s' % [r[:5] for r in table[:3]])
print('含「尾」表头的表数=%d' % hit)
print('HTML 内 280期 出现次数=%d 279期=%d' % (html.count('280期'), html.count('279期')))
for m in list(re.finditer(r'.{0,120}280\s*期.{0,160}', html))[:6]:
    print('  280ctx:', re.sub(r'\s+', ' ', m.group(0))[:260])

print()
print('#' * 30, '故里春意：280/279 行原始标记')
g = io.open('probe_guli_280.html', encoding='utf-8').read()
for key, pat in (('280', r'280\s*期.{0,240}'), ('279', r'279\s*期.{0,240}')):
    for m in list(re.finditer(pat, g))[:3]:
        print('  [%s] %s' % (key, re.sub(r'\s+', ' ', m.group(0))[:300]))
print('  含「90尾」次数=%d 「.9尾」次数=%d' % (g.count('90尾'), g.count('.9尾')))

print()
print('#' * 30, '张天师：主帖 280 行与前后文')
z = io.open('probe_zhang_280_http.html', encoding='utf-8').read()
flat = re.sub(r'<[^>]+>', '\n', z)
lines = [l.strip() for l in flat.splitlines() if l.strip()]
idx = [i for i, l in enumerate(lines) if l.startswith('27') or l.startswith('28')]
for i in idx[-6:]:
    print('  line%d: %r' % (i, lines[i][:150]))
m = re.search(r'.{0,300}280期:\s*★★★张天师.{0,300}', flat, re.S)
if m:
    print('  280 ctx raw:', re.sub(r'[\s]+', ' ', m.group(0))[:400])
print('  含「绝杀一尾【」次数=%d' % z.count('绝杀一尾【'))
