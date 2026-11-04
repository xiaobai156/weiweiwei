# -*- coding: utf-8 -*-
"""只读探针：280 期尾三个失败站的当期发布状态（浏览器渲染 + 直连 HTTP 双路）。"""
import gzip
import io
import os
import re
import ssl
import urllib.request
import zlib

os.chdir(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\_validation\280期失败复检_20261007')
from playwright.sync_api import sync_playwright

PROFILE = r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\browser-profile'
SITES = {
    'chitu_280': ('赤兔', 'https://zwpwuwq.fxnb4-uer1b-uftjcw.work:16677/#am'),
    'guli_280': ('故里春意', 'https://zdwcig.iyo4d-81klf-udwkqg.work:16677/topic/350485.html'),
    'zhang_280': ('张天师', 'https://wwlhc.com/thread-87037-1-1.html'),
}
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def http_fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Encoding': 'gzip, deflate'})
    with urllib.request.urlopen(req, timeout=45, context=CTX) as r:
        raw = r.read()
        enc = (r.headers.get('Content-Encoding') or '').lower()
        body = raw
        if 'gzip' in enc:
            body = gzip.decompress(raw)
        elif 'deflate' in enc:
            try:
                body = zlib.decompress(raw)
            except Exception:
                body = zlib.decompress(raw, -zlib.MAX_WBITS)
        return r.status, r.headers.get('Content-Type'), body


with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(PROFILE, headless=True)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    for key, (name, url) in SITES.items():
        print('=' * 78)
        print(key, name, url)
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            for _ in range(8):
                page.mouse.wheel(0, 20000)
                page.wait_for_timeout(800)
            body = page.inner_text('body')
            io.open('probe_%s_body.txt' % key, 'w', encoding='utf-8').write(body)
            io.open('probe_%s.html' % key, 'w', encoding='utf-8').write(page.content())
            lines = [l.strip() for l in body.splitlines() if l.strip()]
            pl = [l for l in lines if re.match(r'2\d\d\s*期', l)]
            print('  [browser] title=%r body=%d 非空行=%d 期号行=%d' % (page.title(), len(body), len(lines), len(pl)))
            print('  first6:', [x[:64] for x in pl[:6]])
            print('  last6 :', [x[:64] for x in pl[-6:]])
            print('  含280:', [x[:80] for x in pl if '280' in x][:4])
            print('  含279:', [x[:80] for x in pl if '279' in x][:4])
        except Exception as exc:  # noqa: BLE001
            print('  [browser] ERROR %s: %s' % (type(exc).__name__, exc))
        try:
            st, ct, raw = http_fetch(url)
            text = None
            for enc in ('utf-8', 'gb18030'):
                try:
                    text = raw.decode(enc)
                    break
                except Exception:
                    continue
            print('  [http] status=%s ctype=%s bytes=%d charset=%s' % (st, ct, len(raw), enc if text else '?'))
            if text:
                io.open('probe_%s_http.html' % key, 'w', encoding='utf-8').write(text)
                flat = re.sub(r'<[^>]+>', '\n', text)
                hits = [l.strip() for l in flat.splitlines() if re.match(r'2\d\d\s*期|l\d\d\d期', l.strip())]
                print('  [http] 期号行=%d 含280=%s 含279=%s' % (
                    len(hits), '280期' in text, '279期' in text))
                for m in list(re.finditer(r'.{0,40}280\s*期.{0,60}', flat))[:4]:
                    print('   280ctx:', re.sub(r'\s+', ' ', m.group(0)))
        except Exception as exc:  # noqa: BLE001
            print('  [http] ERROR %s: %s' % (type(exc).__name__, exc))
    ctx.close()
