# -*- coding: utf-8 -*-
"""只读轮询：赤兔「杀一尾」表顶行期号是否已换到 289。"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2')
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from shawei.fetch import browser  # noqa: E402

BASE = 'https://zwpwuwq.fxnb4-uer1b-uftjcw.work:16677/#am'
ATTEMPTS = 10
INTERVAL = 180


def probe(url):
    docs = browser.render_browser_documents(url, 60000)
    html = max(((d if isinstance(d, str) else (getattr(d, 'html', '') or str(d))) for d in docs), key=len)
    tbl = [t for t in re.findall(r'<table.*?</table>', html, re.S | re.I) if '杀一尾' in t or '杀一肖' in t]
    if not tbl:
        return {'error': '未找到杀一尾表', 'len': len(html)}
    t = tbl[0]
    rows = re.findall(r'<tr.*?</tr>', t, re.S | re.I)
    parsed = []
    for r in rows[1:6]:
        cells = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', c)).replace('&nbsp;', '').strip()
                 for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, re.S | re.I)]
        parsed.append(cells)
    m = re.search(r'(\d{3})\s*期', parsed[0][0]) if parsed and parsed[0] else None
    return {'top_period': int(m.group(1)) if m else None, 'has_289_in_table': bool(re.search(r'289\s*期', t)),
            'rows': parsed}


log = []
for i in range(ATTEMPTS):
    url = BASE + ('?_cb=%d' % int(time.time())) if i == 0 else BASE
    try:
        r = probe(url)
    except Exception as exc:
        r = {'error': '%s: %s' % (type(exc).__name__, exc)}
    r['attempt'] = i + 1
    r['ts'] = time.strftime('%Y-%m-%d %H:%M:%S')
    r['cache_bust'] = (i == 0)
    log.append(r)
    (OUT / 'poll_chitu_289.json').write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: r.get(k) for k in ('attempt', 'ts', 'cache_bust', 'top_period', 'has_289_in_table', 'error')},
                     ensure_ascii=False), flush=True)
    if r.get('top_period') == 289:
        print('FOUND_289', flush=True)
        break
    if i < ATTEMPTS - 1:
        time.sleep(INTERVAL)
print('DONE', flush=True)
