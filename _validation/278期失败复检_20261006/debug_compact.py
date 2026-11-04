# -*- coding: utf-8 -*-
"""只读诊断：278 期「千呼万唤」渲染页里 278 行为何未被 compact 解析接收。"""
import io, os, re, sys
ROOT = r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2'
os.chdir(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\_validation\278期失败复检_20261006')
sys.path.insert(0, ROOT)

from shawei.fetch import browser
from shawei.services import crawl_site as cs
from shawei.config.rules import strict_rule_for
from shawei.parsers import common as C
from shawei.domain.text import normalize_text
from shawei.config.constants import PERIOD_CHUNK_RE, PERIOD_RE, TAIL_PATTERNS

URL = 'https://ryfbdty.p4a53-f1hew-diwcrg.xyz:16677/topic/497782.html'
SITE = '千呼万唤'
rule = strict_rule_for(URL)
print('RULE sources=%s keywords=%s prefer_rendered=%s body_text=%s maxspan=%s draw_sig=%s site_kw=%s' % (
    rule.allowed_sources, rule.chunk_keywords, rule.prefer_rendered,
    getattr(rule, 'prefer_rendered_body_text', None), rule.max_chunk_span,
    rule.require_draw_signal, rule.require_site_keyword))

rendered = browser.render_browser_documents(URL, 45)
print('rendered[%d]:' % len(rendered), [(len(d), bool(re.search(r'<[A-Za-z][^>]*>', d))) for d in rendered])
rendered = cs._prefer_rendered_documents(rendered, prefer_body_text=rule.prefer_rendered_body_text)
print('preferred[%d]' % len(rendered), [len(d) for d in rendered])
docs = cs._documentize(URL, rendered, 'browser')
print('documents', len(docs))
recs = cs._extract_site_records_from_documents(docs, SITE, 'top', rule, 278)
print('DECISION records', len(recs), [(r.period, r.tail) for r in recs[:8]])

for i, d in enumerate(docs):
    c = cs._document_content(d)
    rs = C.extract_compact_records(c, SITE, rule.chunk_keywords, rule.exclude_keywords,
                                   rule.max_chunk_span, rule.require_draw_signal, rule.require_site_keyword)
    print('-- doc%d chars=%d sources=%s compact_records=%d %s' % (
        i, len(c), getattr(d, 'source_type', '?'), len(rs), sorted({r.period for r in rs})[-5:]))
    if not rs:
        continue
    txt = normalize_text(re.sub(r'<[^>]+>', ' ', c))
    chunks = [ch.strip() for ch in PERIOD_CHUNK_RE.split(txt) if ch.strip()]
    hits = [ch for ch in chunks if PERIOD_RE.match(ch)
            and int(PERIOD_RE.match(ch).group(1)) == 278]
    print('   278期 chunk 数:', len(hits))
    for h in hits[:2]:
        io.open('debug_278_chunk.txt', 'w', encoding='utf-8').write(h[:2000])
        w = C._strong_tail_candidate_window(h, rule.chunk_keywords, site_name=SITE,
                                            max_span=rule.max_chunk_span,
                                            require_draw_signal=rule.require_draw_signal,
                                            require_site_keyword=rule.require_site_keyword)
        pred = C._prediction_text(h)
        print('   chunk[:160]=', repr(h[:160]))
        print('   window=', repr(w[:160]) if w else None)
        print('   prediction=', repr(pred[:120]))
        print('   extract_tail(window)=', C._extract_tail_value(w) if w else None,
              '| extract_tail(chunk)=', C._extract_tail_value(h))
        print('   draw_signal(chunk)=', C._has_draw_signal(h), '| wave=', repr(C._extract_wave_value(h)))
        for j, p in enumerate(TAIL_PATTERNS):
            m = p.search(pred)
            if m:
                print('   TAIL_PATTERN#%d %s -> %r' % (j, p.pattern, m.group(1)))
    # 277 对照
    hits2 = [ch for ch in chunks if PERIOD_RE.match(ch) and int(PERIOD_RE.match(ch).group(1)) == 277]
    for h in hits2[:1]:
        w = C._strong_tail_candidate_window(h, rule.chunk_keywords, site_name=SITE,
                                            max_span=rule.max_chunk_span,
                                            require_draw_signal=rule.require_draw_signal,
                                            require_site_keyword=rule.require_site_keyword)
        print('   [277 对照] window=%r tail=%s' % (w[:120] if w else None, C._extract_tail_value(w) if w else None))
