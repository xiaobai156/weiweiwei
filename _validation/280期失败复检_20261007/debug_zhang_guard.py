# -*- coding: utf-8 -*-
"""只读：定位张天师 guard 触发点（逐记录单独过 guard）。"""
import inspect, io, os, sys
ROOT = r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2'
os.chdir(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\_validation\280期失败复检_20261007')
sys.path.insert(0, ROOT)
from shawei.fetch import browser
from shawei.services import crawl_site as cs
from shawei.config.rules import strict_rule_for
from shawei.parsers import dedicated as D, safety_guards as G

URL = 'https://wwlhc.com/thread-87037-1-1.html'
NAME = '张天师'
rule = strict_rule_for(URL)
rendered = cs._prefer_rendered_documents(browser.render_browser_documents(URL, 45),
                                        prefer_body_text=getattr(rule, 'prefer_rendered_body_text', False))
docs = cs._documentize(URL, rendered, 'browser')
content = cs._document_content(docs[0])
sig = inspect.signature(D.extract_dedicated_records)
kw = {k: v for k, v in (
    ('chunk_keywords', rule.chunk_keywords), ('exclude_keywords', rule.exclude_keywords),
    ('max_chunk_span', getattr(rule, 'max_chunk_span', 240)),
    ('require_draw_signal', getattr(rule, 'require_draw_signal', True)),
    ('require_site_keyword', getattr(rule, 'require_site_keyword', True)),
    ('target_period', 280), ('pick', 'bottom'), ('site_url', URL)) if k in sig.parameters}
recs = D.extract_dedicated_records(content, NAME, rule.dedicated_parser, **kw)
print('records=%d' % len(recs))
for r in recs[-4:]:
    print('  period=%s tail=%s vals=%s snippet=%r' % (r.period, r.tail, r.tail_values, (r.source_snippet or '')[:120]))
for r in recs:
    try:
        G.enforce_parsed_records([r], source='dedicated', parser_name=rule.dedicated_parser,
                                 document=content, site_name=NAME)
    except Exception as exc:  # noqa: BLE001
        ev = G._record_evidence(r, G._period_evidence_by_period(content))
        print('TRIP period=%s tail=%s err=%s' % (r.period, r.tail, exc))
        print('   evidence=%r' % ev[:260])
        print('   prediction_only=%r' % G._prediction_only(ev)[:200])
        print('   field_status(expect %s)=%s' % (r.tail, G._field_candidate_status(G._prediction_only(ev), rule.dedicated_parser, r.tail)))
print('periods:', sorted(x.period for x in recs)[-8:])
