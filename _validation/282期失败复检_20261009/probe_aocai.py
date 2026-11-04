# -*- coding: utf-8 -*-
"""只读探针：282 期失败站「澳彩之家」——专属接口 404 的性质（记录删除 vs 暂时）。"""
import io, os, re
os.chdir(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\_validation\282期失败复检_20261009')
from playwright.sync_api import sync_playwright

PROFILE = r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\browser-profile'
BASE = 'https://buzsxio.821n4-hgj04-edkrft.xyz:29455'
AID = '6a1303be5eabe2c9e91d873a'
PAGE = f'{BASE}/article/manager/{AID}?url=bxj'

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(PROFILE, headless=True)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(PAGE, wait_until='domcontentloaded', timeout=60000)
    try:
        page.wait_for_load_state('networkidle', timeout=20000)
    except Exception:
        pass
    page.wait_for_timeout(2500)
    body = page.inner_text('body')
    io.open('probe_aocai_body.txt', 'w', encoding='utf-8').write(body)
    print('page title=%r body=%d' % (page.title(), len(body)))
    print('body head:', re.sub(r'\s+', ' ', body)[:300])

    for api in (f'{BASE}/api/proxy/admin-articles/{AID}',
                f'{BASE}/api/proxy/manager-articles/{AID}',
                f'{BASE}/api/proxy/manager-articles',
                f'{BASE}/api/proxy/landing-page-data?url=bxj'):
        res = page.evaluate(
            """async (u) => { try { const r = await fetch(u,{credentials:'include'});
                const t = await r.text();
                return {status:r.status, len:t.length, hasId:t.includes('6a1303be5eabe2c9e91d873a'),
                        hasName:t.includes('澳彩之家'), head:t.slice(0,90)}; }
                catch(e){ return {err:String(e)}; } }""", api)
        print('[api] %s -> %s' % (api.split('/api/')[-1], res))

    # 站点首页/列表里是否还有「澳彩之家」
    page.goto(f'{BASE}/?url=bxj', wait_until='domcontentloaded', timeout=60000)
    try:
        page.wait_for_load_state('networkidle', timeout=20000)
    except Exception:
        pass
    page.wait_for_timeout(2500)
    home = page.inner_text('body')
    io.open('probe_aocai_home.txt', 'w', encoding='utf-8').write(home)
    print('home body=%d 含澳彩之家=%s 含281期=%s 含282期=%s'
          % (len(home), '澳彩之家' in home, '281期' in home, '282期' in home))
    for m in list(re.finditer(r'.{0,60}澳彩之家.{0,80}', home))[:4]:
        print('  ctx:', re.sub(r'\s+', ' ', m.group(0)))
    ctx.close()
