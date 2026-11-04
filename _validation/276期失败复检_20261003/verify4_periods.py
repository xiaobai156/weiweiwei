# -*- coding: utf-8 -*-
"""只读：首页作者行期号分布，判断 276 标签是「作者已发布」还是「站点当前期」。"""
import io, re, os
from collections import Counter
os.chdir(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\_validation\276期失败复检_20261003')

for f in ('verify2_home.html', 'verify2_topic.html'):
    h = io.open(f, encoding='utf-8').read()
    body_text = re.sub(r'<[^>]+>', '\n', h)
    body_text = re.sub(r'&nbsp;', ' ', body_text)
    rows = re.findall(r'(2\d\d)\s*期\s*[:：]\s*([^\s<【]{2,8})\s*【([^】]{1,10})】', body_text)
    cnt = Counter(r[0] for r in rows)
    print('==', f, 'author rows', len(rows), 'period dist', cnt.most_common(8))
    print('   sample rows:', rows[:6])
    print('   unique authors', len({r[1] for r in rows}))
    # 该站栏目名分布
    print('   columns', Counter(r[2] for r in rows).most_common(6))
