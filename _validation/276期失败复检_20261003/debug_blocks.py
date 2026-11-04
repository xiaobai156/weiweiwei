# -*- coding: utf-8 -*-
"""只读：定位渲染 HTML 中两处 275 行的所属容器，确认解析器应取哪一块。"""
import io, re

HTML = 'rendered_258481.html'
h = io.open(HTML, encoding='utf-8').read()
print('html len', len(h))

L, R = '\u3016', '\u3017'  # 〖 〗
targets = {
    'A_275_999': '275\u671f\uff1a\u2606\u7edd\u6740\u2460\u5c3e\u2606' + L + '999' + R,
    'B_275_111': '275\u671f\uff1a\u2606\u7edd\u6740\u2460\u5c3e\u2606' + L + '111' + R,
    'A_276_888': '276\u671f\uff1a\u2606\u7edd\u6740\u2460\u5c3e\u2606' + L + '888' + R,
}
for name, tag in targets.items():
    idx = [m.start() for m in re.finditer(re.escape(tag), h)]
    print('====', name, 'hits', len(idx), idx[:5])
    for i in idx[:2]:
        seg = h[max(0, i - 1200):i + 80]
        # 只留标签骨架，便于看容器
        skel = re.sub(r'\s+', ' ', seg)
        print('   -- ctx tail 900:')
        print('   ', skel[-900:])
    print()

# 反向：找出所有 class 含 topic-content / d-content / content 的容器起止，看哪块落在里面
for cls in ('topic-content', 'd-content'):
    for m in re.finditer(r'class="[^"]*' + cls + r'[^"]*"', h):
        print('container', cls, 'at', m.start(), h[max(0, m.start() - 200):m.start() + 200].replace('\n', ' ')[:320])
