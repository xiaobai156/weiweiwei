# -*- coding: utf-8 -*-
"""284 期「两小无猜」只读探针：TLS 证书状态 + 浏览器/HTTP 双路可取性。"""
import io
import os
import ssl
import socket
import urllib.request
from datetime import datetime, timezone

os.chdir(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\_validation\284期失败复检_20261011')
URL = 'https://estsghu.t7gsm-xl1x8-uohlna.xyz:16677/topic/357708.html'
HOST = 'estsghu.t7gsm-xl1x8-uohlna.xyz'
PORT = 16677
PROFILE = r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2\browser-profile'

print('本机时间(UTC):', datetime.now(timezone.utc).isoformat())

# 1) 证书有效期（不校验证书，直连取 peer cert）
try:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((HOST, PORT), timeout=20) as sock:
        with ctx.wrap_socket(sock, server_hostname=HOST) as tls:
            der = tls.getpeercert(binary_form=True)
            info = tls.getpeercert()
    print('[cert] 已取到 DER %d B，subject=%s' % (len(der), info.get('subject') if info else None))
    if info:
        print('[cert] notBefore=%s notAfter=%s' % (info.get('notBefore'), info.get('notAfter')))
    # 用 cryptography 解析(若可用)
    try:
        from cryptography import x509
        cert = x509.load_der_x509_certificate(der)
        nb = cert.not_valid_before_utc if hasattr(cert, 'not_valid_before_utc') else cert.not_valid_before
        na = cert.not_valid_after_utc if hasattr(cert, 'not_valid_after_utc') else cert.not_valid_after
        print('[cert] 精确 notBefore=%s notAfter=%s CN=%s' % (
            nb, na, cert.subject.rfc4514_string()))
        now = datetime.now(timezone.utc)
        print('[cert] 当前是否在有效期内:', nb <= now <= na)
    except Exception as exc:  # noqa: BLE001
        print('[cert] cryptography 解析不可用:', type(exc).__name__, exc)
except Exception as exc:  # noqa: BLE001
    print('[cert] 取证书失败 %s: %s' % (type(exc).__name__, exc))

# 2) urllib 默认校验 / 关闭校验
for label, mkctx in (('verify=ON', lambda: ssl.create_default_context()),
                     ('verify=OFF', None)):
    try:
        if mkctx is None:
            c = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            c.check_hostname = False
            c.verify_mode = ssl.CERT_NONE
        else:
            c = mkctx()
        req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'identity'})
        with urllib.request.urlopen(req, timeout=30, context=c) as r:
            raw = r.read()
        print('[http %s] status=%s bytes=%d' % (label, r.status, len(raw)))
        text = raw.decode('utf-8', 'replace')
        io.open('probe_liangxiao_http_%s.html' % label.replace('=', ''), 'w', encoding='utf-8').write(text)
        print('[http %s] 含284期=%s 含两小无猜=%s' % (label, '284期' in text, '两小无猜' in text))
    except Exception as exc:  # noqa: BLE001
        print('[http %s] ERROR %s: %s' % (label, type(exc).__name__, str(exc)[:200]))

# 3) playwright：默认 vs ignore_https_errors
from playwright.sync_api import sync_playwright  # noqa: E402

with sync_playwright() as p:
    for label, kwargs in (('默认(校验证书)', {}), ('ignore_https_errors', {'ignore_https_errors': True})):
        try:
            ctx = p.chromium.launch_persistent_context(PROFILE, headless=True, **kwargs)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(URL, wait_until='domcontentloaded', timeout=60000)
            for _ in range(6):
                page.mouse.wheel(0, 20000)
                page.wait_for_timeout(700)
            body = page.inner_text('body')
            io.open('probe_liangxiao_%s_body.txt' % label.replace('(', '_').replace(')', ''),
                    'w', encoding='utf-8').write(body)
            io.open('probe_liangxiao_%s.html' % label.replace('(', '_').replace(')', ''),
                    'w', encoding='utf-8').write(page.content())
            lines = [l.strip() for l in body.splitlines() if l.strip()]
            pl = [l for l in lines if l[:3].isdigit() and '期' in l]
            print('[browser %s] title=%r body=%d 非空行=%d 期号行=%d' % (label, page.title(), len(body), len(lines), len(pl)))
            print('    首5:', [x[:70] for x in pl[:5]])
            print('    末5:', [x[:70] for x in pl[-5:]])
            print('    含284:', [x[:80] for x in pl if '284' in x][:3])
            ctx.close()
        except Exception as exc:  # noqa: BLE001
            print('[browser %s] ERROR %s: %s' % (label, type(exc).__name__, str(exc)[:300]))
