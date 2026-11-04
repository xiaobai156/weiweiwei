# -*- coding: utf-8 -*-
"""只读：从已保存的赤兔渲染 HTML 中定位「杀一尾」表格及其期号行。"""
import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent


def text(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s)).strip()


for name in sorted(OUT.glob('chitu_render_*.html')):
    html = name.read_text(encoding='utf-8', errors='replace')
    tables = re.findall(r'<table.*?</table>', html, re.S | re.I)
    print('=== %s len=%d tables=%d ===' % (name.name, len(html), len(tables)))
    hit = [t for t in tables if '杀一尾' in t or '杀一肖' in t]
    print('含 杀一尾/杀一肖 的表格数 =', len(hit))
    for ti, t in enumerate(hit[:4]):
        rows = re.findall(r'<tr.*?</tr>', t, re.S | re.I)
        print('  [表%d] len=%d rows=%d' % (ti, len(t), len(rows)))
        for r in rows[:8]:
            cells = [text(c) for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, re.S | re.I)]
            print('     ', ' | '.join(cells)[:220])
        if len(rows) > 8:
            print('      ...')
            for r in rows[-3:]:
                cells = [text(c) for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, re.S | re.I)]
                print('     ', ' | '.join(cells)[:220])
    # 期号行上下文
    for m in list(re.finditer(r'289\s*期', html))[:6]:
        seg = text(html[max(0, m.start() - 300):m.start() + 300])
        print('  [289期 上下文]', seg[:300])
