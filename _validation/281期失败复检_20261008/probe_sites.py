# -*- coding: utf-8 -*-
"""只读探针：281 期尾三个失败站的当期发布状态（浏览器长超时渲染 + 动态接口）。"""
import io, os, re, ssl, gzip, zlib, urllib.request
os.chdir(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\_validation\281期失败复检_20261008')
from playwright.sync_api import sync_playwright

PROFILE = r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\browser-profile'
SITES = {
    'shabulaji': ('傻不拉几', 'https://ymkakun.dwgml-7jbcy-ohrbrq.xyz:16677/'),
    'shuihuoburong': ('水火不容', 'https://bsfqohr.318t2-xt68t-ssbbaz.xyz:16677/topic/371396.html'),
    'tianyaliangzi': ('天涯浪子', 'https://plwyrcj.4ai8j-p62x5-pnsukp.work:29411/article/admin/6a129b2ad5071f9d0b8b4521?url=gjp'),
}
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE


def http(url, timeout=45):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Encoding': 'gzip, deflate'})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        raw = r.read()
        enc = (r.headers.get('Content-Encoding') or '').lower()
        if 'gzip' in enc:
            raw = gzip.decompress(raw)
        elif 'deflate' in enc:
            try:
                raw = zlib.decompress(raw)
            except Exception:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        return r.status, r.headers.get('Content-Type'), raw


with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(PROFILE, headless=True)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    for key, (name, url) in SITES.items():
        print('=' * 78)
        print(key, name, url)
        ok = False
        for attempt, timeout in ((1, 60000), (2, 90000)):
            try:
                resp = page.goto(url, wait_until='domcontentloaded', timeout=timeout)
                try:
                    page.wait_for_load_state('networkidle', timeout=20000)
                except Exception:
                    pass
                page.wait_for_timeout(2500)
                body = page.inner_text('body')
                io.open('probe_%s_body.txt' % key, 'w', encoding='utf-8').write(body)
                io.open('probe_%s.html' % key, 'w', encoding='utf-8').write(page.content())
                lines = [l.strip() for l in body.splitlines() if l.strip()]
                pl = [l for l in lines if re.match(r'2\d\d\s*期', l)]
                print('  [browser#%d] status=%s title=%r body=%d 非空行=%d 期号行=%d'
                      % (attempt, resp.status if resp else None, page.title(), len(body), len(lines), len(pl)))
                print('  first5:', [x[:60] for x in pl[:5]])
                print('  last5 :', [x[:60] for x in pl[-5:]])
                print('  含281:', [x[:70] for x in pl if '281' in x][:4])
                ok = True
                break
            except Exception as exc:  # noqa: BLE001
                print('  [browser#%d] ERROR %s: %s' % (attempt, type(exc).__name__, str(exc)[:160]))
        if not ok:
            print('  [browser] 两轮均失败')
        try:
            st, ct, raw = http(url)
            print('  [http] status=%s ctype=%s bytes=%d' % (st, ct, len(raw)))
        except Exception as exc:  # noqa: BLE001
            print('  [http] ERROR %s: %s' % (type(exc).__name__, str(exc)[:120]))
        if key == 'tianyaliangzi':
            origin = url.split('/article/')[0]
            aid = '6a129b2ad5071f9d0b8b4521'
            for api in ('%s/api/proxy/admin-articles/%s' % (origin, aid),
                        '%s/api/proxy/manager-articles/%s' % (origin, aid)):
                try:
                    res = page.evaluate(
                        """async (u) => { try { const r = await fetch(u,{credentials:'include'});
                            const t = await r.text();
                            return {status:r.status, len:t.length, has281:t.includes('281期'),
                                    head:t.slice(0,80)}; } catch(e){ return {err:String(e)}; } }""", api)
                except Exception as exc:  # noqa: BLE001
                    res = {'err': '%s: %s' % (type(exc).__name__, exc)}
                print('  [api] %s -> %s' % (api.split('/api/')[-1], res))
    ctx.close()
