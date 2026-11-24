"""324 三站取证：逞心如意 / 转嗔为喜 / 寻宝探码。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent
CHENGXIN = "https://jkofyya.6sf58-wbz5a-thviwx.work:29477/article/admin/6a13f137c1d9e28d71e57742?url=jbp"
ZHUANCHEN = "https://djimkyw.n7ht1-wp4vm-ljitjr.xyz:29488/article/manager/6a329f1573fa32d0b73c0ca0?url=cmzj"
XUNBAO = "https://12388990827.688756.xyz/bbs/topic.php?id=19155"


def dump_rule(url: str, name: str) -> None:
    from shawei.config.rules import effective_rule_for

    try:
        print(f"[规则] {name}: {effective_rule_for(url, name)}")
    except Exception as exc:
        print(f"[规则] {name} 失败: {type(exc).__name__}: {exc}")


def probe_documents() -> None:
    from shawei.fetch.document_discovery import collect_documents

    for name, url in (("逞心如意", CHENGXIN), ("转嗔为喜", ZHUANCHEN), ("寻宝探码", XUNBAO)):
        print(f"\n=== {name} 抓取 ===")
        try:
            docs = collect_documents(url, "??", 30) if False else None
        except Exception:
            docs = None
        from shawei.services.crawl_site import _collect_fetch_documents

        try:
            documents = _collect_fetch_documents(url, name, 30)
            print("  文档数:", len(documents), [len(d) for d in documents])
            for i, doc in enumerate(documents):
                (OUT / f"{name}_doc{i}.txt").write_text(doc, encoding="utf-8", errors="replace")
                text = re.sub(r"<[^>]+>", " ", doc)
                periods = sorted({int(m) for m in re.findall(r"(?<!\d)(\d{3})\s*期", text)})
                print(
                    f"  doc{i}: {len(doc)} 字符 | 站名 {name in doc} | 期数 {periods[:3]}..{periods[-3:] if periods else []}"
                )
        except Exception as exc:
            print("  抓取异常:", type(exc).__name__, str(exc)[:200])


def main() -> None:
    dump_rule(CHENGXIN, "逞心如意")
    dump_rule(ZHUANCHEN, "转嗔为喜")
    dump_rule(XUNBAO, "寻宝探码")
    probe_documents()


if __name__ == "__main__":
    main()
