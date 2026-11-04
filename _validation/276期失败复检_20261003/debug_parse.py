# -*- coding: utf-8 -*-
"""只读诊断：复现项目浏览器渲染路径，检查 topic_published_body_tail 解析链为何取不到 276。"""
import io, sys, os

ROOT = r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2'
sys.path.insert(0, ROOT)
os.chdir(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\_validation\276期失败复检_20261003')

from shawei.parsers.topic import (
    _DynamicHtmlParser, _dynamic_class_tokens, _dynamic_node_text_in_order,
    _topic_body_header_period, _TOPIC_PUBLISHED_BODY_CLASSES,
    _TOPIC_PUBLISHED_TAIL_PATTERN, _topic_body_has_author_anchor,
    extract_topic_published_body_records, PERIOD_RE,
)
from shawei.fetch import browser
from shawei.services.crawl_site import effective_rule_for

URL = 'https://ihdfsxo.kgqq8-mbcz5-qpbkfh.xyz:16677/topic/258481.html'
NAME = '傻傻熊二'

rule = effective_rule_for(URL, NAME)
print('rule:', rule)
print('chunk_keywords:', rule.chunk_keywords)
print('prefer_rendered:', rule.prefer_rendered, 'render_timeout:', getattr(rule, 'render_timeout', None))

docs = browser.render_browser_documents(URL, 45)
print('rendered docs:', len(docs), [len(d) for d in docs])
for k, d in enumerate(docs):
    io.open('dbg_render_%d.html' % k, 'w', encoding='utf-8').write(d)

for k, d in enumerate(docs):
    parser = _DynamicHtmlParser()
    try:
        parser.feed(d); parser.close()
    except Exception as e:
        print('doc%d parse error %r' % (k, e)); continue
    stack = [parser.root]; found = 0
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
                    rows.append((int(m.group(1)), t[:56]))
            if rows:
                found += 1
                ps = sorted(r[0] for r in rows)
                body = _dynamic_node_text_in_order(node)
                print('doc%d container#%d classes=%s header=%s rows=%d min=%d max=%d has276=%s author=%s kw=%s'
                      % (k, found, sorted(cls), _topic_body_header_period(node), len(rows),
                         ps[0], ps[-1], any(p == 276 for p in ps),
                         _topic_body_has_author_anchor(node, NAME),
                         any(w and w in body for w in rule.chunk_keywords)))
                if any(p == 276 for p in ps):
                    print('     276 rows:', [r for r in rows if r[0] == 276])
                    print('     tail rows:', rows[-3:])
        stack.extend(reversed(node.children))

for tp in (276, None):
    recs = extract_topic_published_body_records(
        docs[0], NAME, rule.chunk_keywords, rule.exclude_keywords,
        rule.max_chunk_span, rule.require_draw_signal, tp, 'bottom',
        rule.allow_same_period_records,
    )
    print('extract target_period=%r -> %d records; periods=%s' % (
        tp, len(recs), sorted({r.period for r in recs})[-6:]))
    for r in recs:
        if r.period >= 274:
            print('   ', r.period, r.tail, repr(getattr(r, 'source_snippet', '')[:80]))
