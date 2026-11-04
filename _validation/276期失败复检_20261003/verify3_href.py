# -*- coding: utf-8 -*-
"""只读：首页该行 href 与全站 topic 链接核对。"""
import io, re, os
os.chdir(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\_validation\276期失败复检_20261003')

h = io.open('verify2_home.html', encoding='utf-8').read()
needle = '276\u671f:\u50bb\u50bb\u718a\u4e8c'
i = h.find(needle)
seg = h[max(0, i - 800):i + 80]
print('href candidates:', re.findall(r'href="([^"]+)"', seg))
print('ctx:', re.sub(r'\s+', ' ', seg)[-320:])
print()
links = re.findall(r'/topic/(\d+)\.html', h)
print('distinct topic ids on home:', len(set(links)))
print('258481 count on home:', h.count('258481'))
print('ids near 258481 in html?', sorted({x for x in links if x.startswith('2584')})[:20])

t = io.open('verify2_topic.html', encoding='utf-8').read()
print('topic page self ref 258481:', t.count('258481'))
print('topic page distinct topic ids:', len(set(re.findall(r'/topic/(\d+)\.html', t))))
