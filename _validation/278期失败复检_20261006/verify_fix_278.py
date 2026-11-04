# -*- coding: utf-8 -*-
"""只读验证：把 TAIL_PATTERNS 的 \d{1,3} 放宽到 \d{1,4} 是否恰好修复 278 期（且不影响其他期）。"""
import io, json, os, re, sys
ROOT = r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2'
os.chdir(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\_validation\278期失败复检_20261006')
sys.path.insert(0, ROOT)

from shawei.fetch import browser
from shawei.services import crawl_site as cs
from shawei.config.rules import strict_rule_for
from shawei.parsers import common as C
from shawei.config import constants as K

URL = 'https://ryfbdty.p4a53-f1hew-diwcrg.xyz:16677/topic/497782.html'
SITE = '千呼万唤'
rule = strict_rule_for(URL)

rendered = browser.render_browser_documents(URL, 45)
rendered = cs._prefer_rendered_documents(rendered, prefer_body_text=rule.prefer_rendered_body_text)
docs = cs._documentize(URL, rendered, 'browser')
print('documents', len(docs))


def compact_all():
    merged = {}
    for i, d in enumerate(docs):
        c = cs._document_content(d)
        rs = C.extract_compact_records(c, SITE, rule.chunk_keywords, rule.exclude_keywords,
                                       rule.max_chunk_span, rule.require_draw_signal,
                                       rule.require_site_keyword)
        for r in rs:
            merged[(i, r.period)] = r.tail
    return merged


before = compact_all()
print('BEFORE count=%d max_period=%s last6=%s' % (
    len(before), max(p for _, p in before), sorted(before.items())[-6:]))
try:
    recs = cs._extract_site_records_from_documents(docs, SITE, 'top', rule, 278)
    print('BEFORE decision: records=%d %s' % (len(recs), [(r.period, r.tail) for r in recs[:5]]))
except Exception as exc:  # noqa: BLE001
    print('BEFORE decision raised %s: %s' % (type(exc).__name__, exc))

# 1:1 放宽 \d{1,3} -> \d{1,4}
widened = []
for p in K.TAIL_PATTERNS:
    assert p.pattern.count('{1,3}') == 1, p.pattern
    widened.append(re.compile(p.pattern.replace('{1,3}', '{1,4}'), p.flags))
C.TAIL_PATTERNS = tuple(widened)
print('patched patterns:', len(C.TAIL_PATTERNS))

after = compact_all()
print('AFTER  count=%d max_period=%s last6=%s' % (
    len(after), max(p for _, p in after), sorted(after.items())[-6:]))
diff = sorted(set(after.items()) ^ set(before.items()))
print('DIFF count=%d' % len(diff))
for key, val in diff:
    old = before.get(key, '<无>')
    new = after.get(key, '<无>')
    print('  doc%d %s: %r -> %r' % (key[0], key[1], old, new))
try:
    recs = cs._extract_site_records_from_documents(docs, SITE, 'top', rule, 278)
    print('AFTER decision: records=%d %s' % (len(recs), [(r.period, r.tail) for r in recs[:6]]))
except Exception as exc:  # noqa: BLE001
    print('AFTER decision raised %s: %s' % (type(exc).__name__, exc))

json.dump({'before': {('%d|%d' % k): v for k, v in before.items()},
           'after': {('%d|%d' % k): v for k, v in after.items()}},
          io.open('verify_fix_278_out.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
