from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from shawei.config.paths import FAIL_OUTPUT_DIR, OUTPUT_DIR
from shawei.persistence.atomic_file import atomic_write_text


def resolve_success_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR / path


def resolve_failure_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    FAIL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return FAIL_OUTPUT_DIR / path


def default_current_output_names(period: int) -> tuple[str, str]:
    return f"{period}期-尾.txt", f"{period}期-尾-失败.txt"


def split_ranking_value(value: str) -> tuple[str, ...]:
    normalized = re.sub(r"\s+", "", str(value or ""))
    if re.fullmatch(r"\d", normalized):
        return (normalized,)
    if re.fullmatch(r"\d、\d", normalized):
        return tuple(normalized.split("、"))
    if re.fullmatch(r"(?:\d尾){1,2}", normalized):
        return tuple(re.findall(r"\d", normalized))
    if re.fullmatch(r"\d、\d尾", normalized):
        return tuple(re.findall(r"\d", normalized))
    return ()


def format_ranking(lines: list[str], values: list[str]) -> list[str]:
    output = list(lines)
    expanded_values: list[str] = []
    for value in values:
        parts = split_ranking_value(value)
        expanded_values.extend(parts or [value])
    counter = Counter(expanded_values)
    if counter:
        output.extend(("", "尾数 次数"))
        for value, count in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
            label = f"{value}尾" if re.fullmatch(r"\d", value) else value
            output.append(f"{label:<3} {count}次")
    return output


def parse_success_line(line: str) -> tuple[str, str, str] | None:
    stripped = line.strip()
    if not stripped or stripped == "尾数 次数" or re.search(r"\s\d+次$", stripped):
        return None
    parts = stripped.rsplit(maxsplit=1)
    if len(parts) != 2:
        return None
    value_text, site_name = parts
    ranking_parts = split_ranking_value(value_text)
    if not ranking_parts:
        return None
    return site_name, stripped, "、".join(ranking_parts)


def read_existing_successes(path: Path) -> dict[str, tuple[str, str]]:
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return {}
    existing = {}
    for line in lines:
        parsed = parse_success_line(line)
        if parsed is not None:
            site_name, success_line, ranking_value = parsed
            existing[site_name] = (success_line, ranking_value)
    return existing


def classify_failure_text(text: str) -> str:
    lowered = text.lower()
    if "没有找到" in text or "缺少" in text or "不是指定" in text or "missing" in lowered:
        return "没有数据"
    if "非0-9尾" in text:
        return "非0-9尾"
    if any(marker in lowered for marker in ("unexpected_eof", "ssl", "tls", "handshake")):
        return "TLS失败"
    if any(marker in lowered for marker in ("winerror 10054", "connection reset", "remote host")):
        return "连接断开"
    if "timed out" in lowered or "timeout" in lowered:
        return "超时"
    if "http error" in lowered or "httperror" in lowered:
        return "HTTP失败"
    return "抓取/解析失败"


def format_failure_summary(fail_lines: Iterable[str]) -> list[str]:
    counter = Counter(classify_failure_text(line) for line in fail_lines if line)
    if not counter:
        return ["失败分类: 无"]
    parts = [
        f"{name} {count} 条"
        for name, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]
    return ["失败分类: " + " / ".join(parts)]


def is_retryable_failure_line(line: str) -> bool:
    return classify_failure_text(line) in {"TLS失败", "连接断开", "超时", "HTTP失败"}


def format_failure_records(fail_lines: Iterable[str]) -> str:
    records = [line.rstrip("\r\n") for line in fail_lines if line and line.strip()]
    return "\n\n".join(records) + "\n" if records else ""


def write_optional_fail_file(path: Path, fail_lines: list[str]) -> bool:
    if fail_lines:
        atomic_write_text(path, format_failure_records(fail_lines), encoding="utf-8-sig")
        return True
    if path.exists():
        path.unlink()
    return False


_resolve_path = resolve_success_path
_resolve_failure_path = resolve_failure_path
_default_current_output_names = default_current_output_names
_split_ranking_value = split_ranking_value
_format_ranking = format_ranking
_parse_success_line = parse_success_line
_read_existing_successes = read_existing_successes
