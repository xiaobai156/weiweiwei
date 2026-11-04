# -*- coding: utf-8 -*-
"""只读：拆解 d-content 容器结构（是否含多个年份/多套 期号），确认 276 归属。"""
import io, sys, os, re

ROOT = r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2'
sys.path.insert(0, ROOT)
os.chdir(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\_validation\276期失败复检_20261003')

from shawei.parsers.topic import (
    _DynamicHtmlParser, _dynamic_class_tokens, _dynamic_node_text_in_order,
    _topic_body_header_period, _TOPIC_PUBLISHED_BODY_CLASSES,
    _TOPIC_PUBLISHED_TAIL_PATTERN, PERIOD_RE,
)

docs = [io.open('dbg_render_%d.html' % k, encoding='utf-8').read() for k in (0, 1)]
d = docs[1]
parser = _DynamicHtmlParser(); parser.feed(d); parser.close()

target = None
stack = [parser.root]
while stack:
    node = stack.pop()
    if node.tag in {'script', 'style', 'noscript'}:
        continue
    cls = _dynamic_class_tokens(node)
    if cls & _TOPIC_PUBLISHED_BODY_CLASSES:
        rows = []
        for child in node.children:
            if child.tag in {'script', 'style', 'noscript'}:
                continue
            t = _dynamic_node_text_in_order(child)
            m = PERIOD_RE.match(t)
            if m and _TOPIC_PUBLISHED_TAIL_PATTERN.search(t):
                rows.append((int(m.group(1)), t))
        if len(rows) > 100:
            target = (node, rows)
            break
    stack.extend(reversed(node.children))

node, rows = target
print('container classes', sorted(_dynamic_class_tokens(node)), 'children', len(node.children), 'rows', len(rows))
print('header period', _topic_body_header_period(node))
print('--- ancestor chain classes (node -> root) ---')
cur = node.parent
depth = 0
while cur is not None and depth < 8:
    print('  up%d tag=%s classes=%s text_head=%r' % (depth, cur.tag, sorted(_dynamic_class_tokens(cur)),
          _dynamic_node_text_in_order(cur)[:90]))
    cur = cur.parent; depth += 1

print('--- first 6 non-row children text (section headings?) ---')
shown = 0
for c in node.children:
    t = _dynamic_node_text_in_order(c).strip()
    if not t:
        continue
    if PERIOD_RE.match(t) and _TOPIC_PUBLISHED_TAIL_PATTERN.search(t):
        continue
    print('   CHILD tag=%s classes=%s text=%r' % (c.tag, sorted(_dynamic_class_tokens(c)), t[:140]))
    shown += 1
    if shown >= 12:
        break

print('--- rows for periods 270..280 (index, period, text) ---')
for i, (p, t) in enumerate(rows):
    if 270 <= p <= 280:
        print('   #%d %d %r' % (i, p, t[:70]))

print('--- duplicate periods count ---')
from collections import Counter
c = Counter(p for p, _ in rows)
dups = {p: n for p, n in c.items() if n > 1}
print('   distinct periods', len(c), 'dups', len(dups), 'e.g.', sorted(dups.items())[:12])
