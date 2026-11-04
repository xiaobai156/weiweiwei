# -*- coding: utf-8 -*-
"""只读：复核站点首页对「傻傻熊二」的展示期号与链接，并抓取主题页 big-con 页头。"""
import io, os, re, json, sys

os.chdir(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\_validation\276期失败复检_20261003')
sys.path.insert(0, r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2')

from playwright.sync_api import sync_playwright

BASE = 'https://ihdfsxo.kgqq8-mbcz5-qpbkfh.xyz:16677'
TOPIC = BASE + '/topic/258481.html'
PROFILE = r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\browser-profile'
NAME = '傻傻熊二'

out = {}
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(PROFILE, headless=True)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    for label, url in (('home', BASE + '/index.html'), ('topic', TOPIC)):
        page.goto(url, wait_until='domcontentloaded', timeout=60000)
        for _ in range(8):
            page.mouse.wheel(0, 20000)
            page.wait_for_timeout(900)
        html = page.content()
        body = page.inner_text('body')
        io.open('verify2_%s.html' % label, 'w', encoding='utf-8').write(html)
        io.open('verify2_%s.txt' % label, 'w', encoding='utf-8').write(body)
        hits = [m.start() for m in re.finditer(re.escape(NAME), html)]
        rows = [m.start() for m in re.finditer(r'2[0-9]{2}\s*期\s*[:：]\s*' + re.escape(NAME), html)]
        out[label] = {'html_len': len(html), 'body_len': len(body), 'name_hits': len(hits), 'row_hits': len(rows)}
        print('==', label, out[label])
        for i in rows[:6]:
            seg = re.sub(r'\s+', ' ', html[max(0, i - 300):i + 260])
            print('   ROW:', seg[-520:])
        print('   body lines with name:')
        for ln in body.splitlines():
            if NAME in ln:
                print('     ', ln.strip()[:120])

    # 页头 big-con
    page.goto(TOPIC, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(1500)
    for sel in ('.big-con', '.boxn', '.d-content'):
        try:
            el = page.query_selector(sel)
            if el:
                t = re.sub(r'\s+', ' ', el.inner_text())[:160]
                print('HEAD', sel, repr(t))
        except Exception as e:
            print('HEAD', sel, 'err', e)
    ctx.close()

io.open('verify2_out.json', 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=1))
