from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from shawei.config.paths import FAIL_OUTPUT_DIR, ROOT_DIR
from shawei.persistence import txt_writer
from shawei.persistence.atomic_file import atomic_write_text
from shawei.services import duplicate_check


def parse_periods(values: list[str]) -> list[int]:
    parts = [
        part
        for part in re.split(r"[\s,，]+", " ".join(values).strip())
        if part
    ]
    periods: list[int] = []
    seen: set[int] = set()
    for part in parts:
        if not re.fullmatch(r"\d+", part):
            raise ValueError(f"期数格式错误: {part}")
        period = int(part)
        if period <= 0:
            raise ValueError(f"期数必须大于0: {part}")
        if period not in seen:
            seen.add(period)
            periods.append(period)
    if not periods:
        raise ValueError("至少输入一个期数")
    return periods


def parse_fail_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return {}
    failures: dict[str, str] = {}
    for line in lines:
        match = re.match(r"失败\s+(.+?)\s+(\S+)\s+原因:\s*(.*)$", line.strip())
        if match:
            name, _url, reason = match.groups()
            failures[name] = reason or "失败原因为空"
    return failures


def run_period(period: int, timeout: int | None, workers: int | None) -> int:
    success_name, failure_name = txt_writer.default_current_output_names(period)
    success_path = txt_writer._resolve_path(success_name)
    failure_path = txt_writer._resolve_failure_path(failure_name)
    success_path.unlink(missing_ok=True)
    failure_path.unlink(missing_ok=True)
    command = [
        sys.executable,
        str(ROOT_DIR / "shawei_crawler.py"),
        "--period",
        str(period),
        "--no-update-cache",
    ]
    if timeout is not None:
        command.extend(("--timeout", str(timeout)))
    if workers is not None:
        command.extend(("--workers", str(workers)))
    completed = subprocess.run(command, cwd=str(ROOT_DIR))
    return int(completed.returncode)


def build_summary(periods: list[int], output: Path | None = None) -> Path:
    sites = duplicate_check.configured_sites()
    successes_by_period: dict[int, set[str]] = {}
    failures_by_period: dict[int, dict[str, str]] = {}
    for period in periods:
        success_name, failure_name = txt_writer.default_current_output_names(period)
        success_path = txt_writer._resolve_path(success_name)
        failure_path = txt_writer._resolve_failure_path(failure_name)
        successes_by_period[period] = set(txt_writer._read_existing_successes(success_path))
        failures_by_period[period] = parse_fail_file(failure_path)

    lines = [
        "多期汇总失败报告",
        "规则: 指定期数中任意一期抓取成功即算通过；这里只列全部失败目录",
        "期数: " + " ".join(str(period) for period in periods),
        "",
    ]
    failure_count = 0
    for site in sites:
        if any(site.name in successes_by_period[period] for period in periods):
            continue
        failure_count += 1
        lines.extend((f"目录: {site.name}", f"方向: {site.pick}", f"地址: {site.url}"))
        for period in periods:
            reason = failures_by_period[period].get(site.name)
            if not reason:
                reason = "未生成失败记录，且成功文件中也未找到该目录"
            lines.append(f"{period}期: {reason}")
        lines.append("")
    if failure_count == 0:
        lines.append("无全部失败目录")
    lines.insert(3, f"全部失败目录数: {failure_count}")
    report_path = output or (
        FAIL_OUTPUT_DIR
        / ("-".join(str(period) for period in periods) + "多期汇总失败.txt")
    )
    if not report_path.is_absolute():
        report_path = FAIL_OUTPUT_DIR / report_path
    atomic_write_text(report_path, "\n".join(lines) + "\n", encoding="utf-8-sig")
    return report_path
