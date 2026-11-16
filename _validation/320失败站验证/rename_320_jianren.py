"""把“坚韧不拔”改名为“摸风暗掩”（站方改名）。

- sites.json / recent_10_cache.json / shawei_site_health.json 只做字节级名称替换，保留原有 CRLF/BOM。
- 解析器标记与规则关键词同步改名，避免 fail-closed。
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = "坚韧不拔"
NEW = "摸风暗掩"


def replace_bytes(path: Path) -> int:
    raw = path.read_bytes()
    old = OLD.encode("utf-8")
    count = raw.count(old)
    if count:
        path.write_bytes(raw.replace(old, NEW.encode("utf-8")))
    return count


def replace_text(path: Path, pairs: list[tuple[str, str]]) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    changed = []
    for old, new in pairs:
        if old in text:
            text = text.replace(old, new)
            changed.append(old)
    if changed:
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    return changed


def main() -> None:
    for name in ("sites.json", "recent_10_cache.json", "shawei_site_health.json"):
        path = ROOT / name
        print(name, "名称替换处数:", replace_bytes(path))

    print(
        "topic.py",
        replace_text(
            ROOT / "shawei" / "parsers" / "topic.py",
            [('"jianren_topic_main_tail": ("坚韧不拔",)', '"jianren_topic_main_tail": ("摸风暗掩",)')],
        ),
    )
    print(
        "rules.py",
        replace_text(
            ROOT / "shawei" / "config" / "rules.py",
            [("chunk_keywords=('坚韧不拔', \"绝杀一尾\")", "chunk_keywords=('摸风暗掩', \"绝杀一尾\")")],
        ),
    )
    print(
        "shawei_failed_site_validator.py",
        replace_text(
            ROOT / "shawei_failed_site_validator.py",
            [('ValidationSite("坚韧不拔"', 'ValidationSite("摸风暗掩"')],
        ),
    )
    print(
        "test_failed_site_rule_regressions.py",
        replace_text(
            ROOT / "test_failed_site_rule_regressions.py",
            [('effective_rule_for(JIANREN_URL, "坚韧不拔")', 'effective_rule_for(JIANREN_URL, "摸风暗掩")')],
        ),
    )

    sites = json.loads((ROOT / "sites.json").read_text(encoding="utf-8-sig"))
    hit = [s for s in sites if s["url"].endswith("/topic/458345.html")]
    print("sites.json 条目:", hit)


if __name__ == "__main__":
    main()
