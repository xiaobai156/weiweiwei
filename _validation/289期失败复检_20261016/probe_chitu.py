# -*- coding: utf-8 -*-
"""只读取证：赤兔 289 期页内表格现状（渲染 + 原始）。"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2')
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

URL = 'https://zwpwuwq.fxnb4-uer1b-uftjcw.work:16677/#am'

from shawei.fetch import browser  # noqa: E402

docs = browser.render_browser_documents(URL, 60000)
print('文档数 =', len(docs))
report = {'url': URL, 'docs': []}
for i, d in enumerate(docs):
    html = d if isinstance(d, str) else getattr(d, 'html', None) or getattr(d, 'text', None) or str(d)
    m = re.search(r'<title[^>]*>(.*?)</title>', html, re.S | re.I)
    info = {'index': i, 'len': len(html), 'title': (m.group(1).strip() if m else None)}
    print('doc[%d] len=%d title=%s' % (i, len(html), info['title']))
    for pat in ('289', '288', '287'):
        info['has_%s' % pat] = pat in html
    # 表格
    tables = re.findall(r'<table.*?</table>', html, re.S | re.I)
    info['tables'] = len(tables)
    for ti, t in enumerate(tables[:3]):
        rows = re.findall(r'<tr.*?</tr>', t, re.S | re.I)
        print('  table[%d] rows=%d' % (ti, len(rows)))
        for r in rows[:8]:
            cells = [re.sub(r'<[^>]+>', '', c).strip() for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, re.S | re.I)]
            print('    ', ' | '.join(cells)[:200])
    # 期号行
    lines = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', l)).strip() for l in html.splitlines()]
    hits = [l for l in lines if re.search(r'28[5-9]\s*期', l)]
    info['period_lines'] = hits[:20]
    for l in hits[:12]:
        print('  期号行:', l[:200])
    report['docs'].append(info)
    (OUT / ('chitu_render_%d.html' % i)).write_text(html, encoding='utf-8')
(OUT / 'chitu_render.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

# 原始抓取（不渲染）
try:
    import urllib.request
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
    raw = urllib.request.urlopen(req, timeout=30).read()
    print('原始 len=%d has289=%s' % (len(raw), b'289' in raw))
except Exception as exc:
    print('原始抓取失败:', type(exc).__name__, exc)
