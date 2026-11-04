"""285 期「曾氏」浏览器复检：渲染 Qvuu SPA，确认页面/作者主页上是否存在 285。

只读，不写任何正式文件。产出 probe_zengshi_browser_out.json + *.html/.txt。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shawei.fetch.browser import render_browser_documents  # noqa: E402

HERE = Path(__file__).parent
TARGETS = {
    "forum_15340352": "https://qvuuqqs.8imf7-hteuh-ylwuqv.xyz/#/forums/15340352",
    "user_1014": "https://qvuuqqs.8imf7-hteuh-ylwuqv.xyz/#/users/1014",
}
TAG_RE = re.compile(r"<[^>]+>")
PERIOD_LINE_RE = re.compile(r"(\d{2,3})\s*期[^\n<]{0,80}?曾氏[^\n<]{0,40}?杀\s*《\s*(\d)\s*》\s*尾[^\n<]{0,20}?")


def to_text(document: str) -> str:
    text = TAG_RE.sub("\n", document) if "<" in document else document
    return re.sub(r"\n{2,}", "\n", text)


def main() -> int:
    report: dict = {}
    for key, url in TARGETS.items():
        entry: dict = {"url": url}
        try:
            documents = render_browser_documents(url, 60)
        except Exception as exc:  # noqa: BLE001
            entry["error"] = f"{type(exc).__name__}: {exc}"
            report[key] = entry
            print(f"[{key}] 渲染失败: {entry['error']}")
            continue
        entry["document_count"] = len(documents)
        entry["doc_lengths"] = [len(d) for d in documents]
        text = to_text("\n".join(documents))
        (HERE / f"probe_zengshi_browser_{key}.txt").write_text(text, encoding="utf-8")
        (HERE / f"probe_zengshi_browser_{key}.html").write_text("\n".join(documents), encoding="utf-8")
        entry["body_len"] = len(text)
        entry["contains_285"] = "285" in text
        entry["count_285"] = text.count("285")
        entry["contains_zengshi"] = "曾氏" in text
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        entry["nonempty_lines"] = len(lines)
        entry["period_lines_285"] = [ln for ln in lines if "285" in ln][:20]
        entry["zengshi_kill_lines"] = sorted(set(PERIOD_LINE_RE.findall(text)), reverse=True)[:12]
        entry["zengshi_lines"] = [ln for ln in lines if "曾氏绝杀一尾" in ln][:12]
        report[key] = entry
        print(f"[{key}] docs={entry['document_count']} lens={entry['doc_lengths']} body={entry['body_len']} "
              f"285={entry['contains_285']}(x{entry['count_285']}) 曾氏={entry['contains_zengshi']} lines={entry['nonempty_lines']}")
        print(f"   285 行: {entry['period_lines_285'][:6]}")
        print(f"   曾氏绝杀一尾行: {entry['zengshi_lines'][:6]}")
    (HERE / "probe_zengshi_browser_out.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("证据已写 probe_zengshi_browser_out.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
