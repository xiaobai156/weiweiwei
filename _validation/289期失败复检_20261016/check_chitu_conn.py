# -*- coding: utf-8 -*-
"""只读：独立连通性 + 单次渲染复核（赤兔 289）。"""
import re
import socket
import ssl
import sys
import time
from pathlib import Path

ROOT = Path(r'C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2')
sys.path.insert(0, str(ROOT))

HOST = 'zwpwuwq.fxnb4-uer1b-uftjcw.work'
PORT = 16677
URL = 'https://%s:%d/#am' % (HOST, PORT)

print('时间 %s' % time.strftime('%H:%M:%S'))
try:
    ip = socket.gethostbyname(HOST)
    print('DNS %s -> %s' % (HOST, ip))
except Exception as exc:
    print('DNS 失败: %s: %s' % (type(exc).__name__, exc))
    ip = None

if ip:
    for proto in ('tcp',):
        t0 = time.time()
        s = socket.socket()
        s.settimeout(10)
        try:
            s.connect((ip, PORT))
            print('TCP %s:%d OK %.2fs' % (ip, PORT, time.time() - t0))
        except Exception as exc:
            print('TCP 失败 %.2fs: %s: %s' % (time.time() - t0, type(exc).__name__, exc))
        finally:
            s.close()
    t0 = time.time()
    try:
        ctx = ssl._create_unverified_context()
        req = 'GET / HTTP/1.1\r\nHost: %s:%d\r\nUser-Agent: Mozilla/5.0\r\nConnection: close\r\n\r\n' % (HOST, PORT)
        with socket.create_connection((ip, PORT), timeout=15) as sock:
            with ctx.wrap_socket(sock, server_hostname=HOST) as ss:
                ss.sendall(req.encode())
                data = b''
                while len(data) < 4096:
                    chunk = ss.recv(4096)
                    if not chunk:
                        break
                    data += chunk
        head = data.split(b'\r\n\r\n', 1)[0].decode('latin-1', 'replace')
        print('HTTPS 首行/状态 %.2fs: %s' % (time.time() - t0, head.splitlines()[0] if head else '(空)'))

        print('  响应头: %s' % ' | '.join(head.splitlines()[1:6]))
    except Exception as exc:
        print('HTTPS 失败 %.2fs: %s: %s' % (time.time() - t0, type(exc).__name__, exc))

from shawei.fetch import browser  # noqa: E402
try:
    t0 = time.time()
    docs = browser.render_browser_documents(URL, 60000)
    html = max(((d if isinstance(d, str) else (getattr(d, 'html', '') or str(d))) for d in docs), key=len)
    tbl = [t for t in re.findall(r'<table.*?</table>', html, re.S | re.I) if '杀一尾' in t or '杀一肖' in t]
    print('渲染 %.2fs docs=%d len=%d 杀一尾表=%d' % (time.time() - t0, len(docs), len(html), len(tbl)))
    if tbl:
        rows = re.findall(r'<tr.*?</tr>', tbl[0], re.S | re.I)
        for r in rows[:4]:
            cells = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', c)).replace('&nbsp;', '').strip()
                     for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, re.S | re.I)]
            print('   ', ' | '.join(cells))
        print('   表内含 289 期 =', bool(re.search(r'289\s*期', tbl[0])))
except Exception as exc:
    print('渲染失败: %s: %s' % (type(exc).__name__, str(exc)[:300]))
