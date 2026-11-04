# -*- coding: utf-8 -*-
"""只读：赤兔 杀一尾 表全量行 + 两站专属解析器取值规则定位。"""
import io, os, re, sys
ROOT = r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2'
os.chdir(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\_validation\280期失败复检_20261007')
sys.path.insert(0, ROOT)
from shawei.parsers.common import TableParser  # noqa: E402

html = io.open('probe_chitu_280.html', encoding='utf-8').read()
parser = TableParser(); parser.feed(html); parser.close()
for ti, table in enumerate(parser.tables):
    head = ' '.join(table[0]) if table else ''
    if '杀一尾' not in head:
        continue
    print('=== 表%d 行数=%d 表头=%r' % (ti, len(table), head[:120]))
    for r in table:
        print('   ', ' | '.join(x[:24] for x in r[:7]))
# 是否任何表含 280 期 且 表头含 杀一尾
print('=== 同时含 280 与 杀一尾 的表 ===')
n = 0
for ti, table in enumerate(parser.tables):
    flat = ' '.join(' '.join(r) for r in table)
    if '280期' in flat and '杀一尾' in flat:
        n += 1
        print('  表%d 行数=%d 表头=%r' % (ti, len(table), (' '.join(table[0])[:80] if table else '')))
print('  合计 %d' % n)

# 故里春意专属解析器
src = io.open(os.path.join(ROOT, 'shawei', 'parsers', 'dedicated.py'), encoding='utf-8').read()
for name in ('gulichunyi_topic_tail', 'discuz_main_post_kill_tail'):
    i = src.find('DEDICATED_PARSER_HANDLERS["%s"]' % name)
    print('\n=== %s 注册行 idx=%d ===' % (name, i))
    if i > 0:
        print(src[max(0, i - 120):i + 160])
# 错误文案来源
for f in ('shawei/parsers/dedicated.py', 'shawei/parsers/topic.py', 'shawei/validation/validator.py'):
    text = io.open(os.path.join(ROOT, f), encoding='utf-8').read()
    for m in re.finditer(r'.{0,160}单尾字段缺少可证明的直接值.{0,80}', text, re.S):
        print('\n[%s] %s' % (f, re.sub(r'\s+', ' ', m.group(0))))
