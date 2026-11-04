# -*- coding: utf-8 -*-
"""只读复现：张天师 / 故里春意 的专属解析结果与 safety_guards 判定细节。"""
import inspect
import io
import os
import re
import sys
ROOT = r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2'
os.chdir(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\_validation\280期失败复检_20261007')
sys.path.insert(0, ROOT)

from shawei.fetch import browser
from shawei.services import crawl_site as cs
from shawei.config.rules import strict_rule_for
from shawei.parsers import dedicated as D
from shawei.parsers import safety_guards as G

TARGETS = [
    ('张天师', 'https://wwlhc.com/thread-87037-1-1.html', 'bottom', 280),
    ('故里春意', 'https://zdwcig.iyo4d-81klf-udwkqg.work:16677/topic/350485.html', 'bottom', 280),
]


def documents_for(rule, url, name, pick):
    if rule.prefer_rendered:
        rendered = browser.render_browser_documents(url, 45)
        rendered = cs._prefer_rendered_documents(
            rendered, prefer_body_text=getattr(rule, 'prefer_rendered_body_text', False))
        return cs._documentize(url, rendered, 'browser')
    collected = cs.document_discovery.collect_documents(
        url, 45, rule.follow_link_keywords, rule.follow_link_rendered,
        rule.follow_link_only, pick, site_name=name,
        follow_link_pagination=rule.follow_link_pagination)
    return cs._documentize(url, collected, 'page')


def call_parser(document, name, rule, pick, target, site_url):
    sig = inspect.signature(D.extract_dedicated_records)
    kwargs = {}
    for key, value in (
        ('chunk_keywords', rule.chunk_keywords), ('exclude_keywords', rule.exclude_keywords),
        ('max_chunk_span', getattr(rule, 'max_chunk_span', 240)), ('require_draw_signal', getattr(rule, 'require_draw_signal', True)),
        ('require_site_keyword', getattr(rule, 'require_site_keyword', True)), ('target_period', target),
        ('pick', pick), ('anchor_span', getattr(rule, 'anchor_span', 1500)),
        ('allow_same_period_records', getattr(rule, 'allow_same_period_records', False)),
        ('site_url', site_url),
    ):
        if key in sig.parameters:
            kwargs[key] = value
    return D.extract_dedicated_records(document, name, rule.dedicated_parser, **kwargs)


for name, url, pick, target in TARGETS:
    print('=' * 78)
    print(name, url, 'pick=%s target=%d' % (pick, target))
    rule = strict_rule_for(url)
    print('  rule parser=%r sources=%s prefer_rendered=%s kw=%s' % (
        rule.dedicated_parser, rule.allowed_sources, rule.prefer_rendered, rule.chunk_keywords))
    try:
        docs = documents_for(rule, url, name, pick)
    except Exception as exc:  # noqa: BLE001
        print('  fetch ERROR %s: %s' % (type(exc).__name__, exc))
        continue
    print('  documents=%d sizes=%s' % (len(docs), [len(cs._document_content(d)) for d in docs]))
    for i, d in enumerate(docs):
        content = cs._document_content(d)
        io.open('debug_%s_doc%d.html' % (name, i), 'w', encoding='utf-8').write(content)
        try:
            recs = call_parser(content, name, rule, pick, target, url)
        except Exception as exc:  # noqa: BLE001
            print('  doc%d parser ERROR %s: %s' % (i, type(exc).__name__, exc))
            recs = []
        print('  doc%d records=%d periods=%s' % (
            i, len(recs), sorted(r.period for r in recs)[-6:]))
        for r in recs[-3:]:
            print('      rec period=%s tail=%s snippet=%r' % (r.period, r.tail, (r.source_snippet or '')[:110]))
        try:
            G.enforce_parsed_records(recs, source='dedicated', parser_name=rule.dedicated_parser,
                                     document=content, site_name=name)
            print('  doc%d guard PASS' % i)
        except Exception as exc:  # noqa: BLE001
            print('  doc%d guard RAISE %s: %s' % (i, type(exc).__name__, exc))
    # 证据细节
    content = cs._document_content(docs[0])
    ev = G._period_evidence_by_period(content)
    for p in (279, 280):
        e = ev.get(p)
        if not e:
            print('  evidence %d: <无>' % p)
            continue
        pred = G._prediction_only(e)
        safe, err = G._field_candidate_status(pred, rule.dedicated_parser, 9)
        print('  evidence %d 原始=%r' % (p, e[:220]))
        print('     prediction_only=%r' % pred[:200])
        print('     safe_match(期望9)=%s err=%r multi=%s' % (
            safe, err, G._has_ambiguous_multi_digit_tail(e)))
