# -*- coding: utf-8 -*-
"""只读对照：取同站另一位作者页（武松打虎 258480）验证「页头期号=作者最新已发布期」这一语义。"""
import io, os, re, sys
os.chdir(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\_validation\276期失败复检_20261003')
from playwright.sync_api import sync_playwright

PROFILE = r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\browser-profile'
URLS = {
    'wusong_258480': 'https://ihdfsxo.kgqq8-mbcz5-qpbkfh.xyz:16677/topic/258480.html',
    'shasha_258481': 'https://ihdfsxo.kgqq8-mbcz5-qpbkfh.xyz:16677/topic/258481.html',
}
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(PROFILE, headless=True)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    for label, url in URLS.items():
        page.goto(url, wait_until='domcontentloaded', timeout=60000)
        for _ in range(8):
            page.mouse.wheel(0, 20000)
            page.wait_for_timeout(800)
        body = page.inner_text('body')
        io.open('verify5_%s.txt' % label, 'w', encoding='utf-8').write(body)
        head = ''
        for sel in ('.big-con', '.boxn'):
            el = page.query_selector(sel)
            if el:
                head = re.sub(r'\s+', ' ', el.inner_text())[:60]
                break
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        pl = [l for l in lines if re.match(r'2\d\d\s*期', l)]
        print('==', label)
        print('   banner:', repr(head))
        print('   period lines:', len(pl), '| first:', pl[0][:50] if pl else None)
        print('   last 4:', [x[:46] for x in pl[-4:]])
        print('   has 276 row:', any('276' in x and '期' in x for x in pl))
    ctx.close()
