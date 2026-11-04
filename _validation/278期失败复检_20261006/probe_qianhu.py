# -*- coding: utf-8 -*-
"""只读探针：278 期失败站「千呼万唤」页是否已存在 278 期记录（pick=top）。

失败原因：LookupError: 绝对top边界是277期，不是指定278期
规则：shawei\config\rules.py:656  allowed_sources=("compact",) prefer_rendered=True
"""
import io, os, re
os.chdir(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\_validation\278期失败复检_20261006')
from playwright.sync_api import sync_playwright

PROFILE = r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\browser-profile'
URL = 'https://ryfbdty.p4a53-f1hew-diwcrg.xyz:16677/topic/497782.html'

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(PROFILE, headless=True)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(URL, wait_until='domcontentloaded', timeout=60000)
    for _ in range(8):
        page.mouse.wheel(0, 20000)
        page.wait_for_timeout(800)
    body = page.inner_text('body')
    io.open('probe_qianhu_body.txt', 'w', encoding='utf-8').write(body)
    html = page.content()
    io.open('probe_qianhu_page.html', 'w', encoding='utf-8').write(html)
    print('url', URL)
    print('title', repr(page.title()))
    print('body len', len(body), 'html len', len(html))
    for sel in ('.big-con', '.boxn', '.big-tit', 'h1'):
        el = page.query_selector(sel)
        if el:
            print('banner %-9s' % sel, repr(re.sub(r'\s+', ' ', el.inner_text())[:80]))
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    pl = [l for l in lines if re.match(r'2\d\d\s*期', l)]
    print('非空行', len(lines), '| 期号行', len(pl))
    print('first 6:', [x[:60] for x in pl[:6]])
    print('last 6 :', [x[:60] for x in pl[-6:]])
    print('rows with 278:', [x[:80] for x in pl if '278' in x])
    print('rows with 277:', [x[:80] for x in pl if '277' in x][:4])
    print('placeholder(开0000) 行数:', sum(1 for x in pl if '开0000' in x or '开:0000' in x))
    ctx.close()
