# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from shawei.config.constants import DIRECTION_BOUNDARY_WINDOW
from shawei.config.paths import (
    FAIL_OUTPUT_DIR,
    OUTPUT_DIR,
    RECENT_CACHE_PATH,
    SITE_HEALTH_PATH,
    SITES_JSON_PATH,
)
from shawei.config.rules import effective_rule_for
from shawei.domain.models import Candidate, Record, StrictRule
from shawei.domain.text import is_bottom_pick, normalize_text
from shawei.fetch.browser import render_browser_documents
from shawei.fetch.document_discovery import collect_documents
from shawei.fetch.http_client import clear_fetch_cache
from shawei.parsers.common import is_valid_tail_record
from shawei.services.crawl_site import crawl_current_site
from shawei.validation.validator import collect_candidates, validate_documents


@dataclass(frozen=True)
class ValidationSite:
    name: str
    url: str
    pick: str
    period: int


def rule_for(site: ValidationSite) -> StrictRule:
    return effective_rule_for(site.url, site.name)


@dataclass(frozen=True)
class ValidationResult:
    site: ValidationSite
    passed: bool
    found_target: bool
    actual_values: tuple[str, ...]
    actual_count: int
    direction_ok: bool
    anchor_ok: bool
    keyword_ok: bool
    tail_ok: bool
    conflict_values: tuple[str, ...]
    duplicate_tail: bool
    failure_reason: str


TARGETED_FAILED_SITE_CHECKLIST = (
    ValidationSite("笑歌戏舞", "https://tcwsqrno.ril3o-7ghui-hiepuc.work:16633/topic/226021.html", "bottom", 203),
    ValidationSite("赴火蹈刃", "https://sqddimfu.evs71-kia2b-gshsdc.xyz:16677/topic/219850.html", "bottom", 203),
    ValidationSite("目治手营", "https://sqddimfu.evs71-kia2b-gshsdc.xyz:16677/topic/226259.html", "bottom", 203),
    ValidationSite("山海经", "https://mwztnor.vapgy-gskm7-sqbyej.work:17455/topic/564223.html", "top", 203),
    ValidationSite("风驰电掣", "https://qarppl.154bo-trld9-qppors.xyz:16677/topic/326551.html", "bottom", 203),
    ValidationSite("坚韧不拔", "https://lxbwvnfv.3gwtt-z9y8n-wsxdfy.xyz:16677/topic/458345.html", "bottom", 203),
    ValidationSite("碌碌庸才", "https://eolantz.v6nli-9yz71-rihyny.xyz:16677/topic/447895.html", "top", 203),
    ValidationSite("一点红", "https://kfkxqua.vohzh-s0pbh-vhwsal.xyz:16677/topic/246761.html", "bottom", 209),
    ValidationSite("傻傻熊二", "https://ihdfsxo.kgqq8-mbcz5-qpbkfh.xyz:16677/topic/258481.html", "bottom", 206),
    ValidationSite("翻本行动", "https://drxgkjt.uu1oc-eyjpt-uxyccu.xyz:29400/article/manager/6a33e58fdfa16552b923d27f?url=jyb", "bottom", 206),
    ValidationSite("淋漓尽致", "https://kulipur.l5paz-a0o8v-uozmmd.xyz:16677/topic/435507.html", "bottom", 206),
    ValidationSite("挥手乾坤", "https://pa4dwcnd64.772149.shop/bbs/topic.php?id=726", "bottom", 206),
    ValidationSite("财富高手论坛", "https://x1rvueyk50.669332.shop/bbs/", "bottom", 206),
    ValidationSite("皇家赐码", "https://wigrzse.3acpt-tc9xa-kzxasm.xyz:29444/article/manager/6a1570948be59b17287c6dd7?url=pg", "bottom", 209),
    ValidationSite("打造辉煌", "https://wigrzse.3acpt-tc9xa-kzxasm.xyz:29444/article/manager/6a1556f2d9d9fc2cea524224?url=pg", "bottom", 209),
    ValidationSite("夜黑风高", "https://wigrzse.3acpt-tc9xa-kzxasm.xyz:29444/article/manager/6a639071b3f65fed7d622154?url=pg", "bottom", 209),
    ValidationSite("陈年老酒", "https://wigrzse.3acpt-tc9xa-kzxasm.xyz:29444/article/manager/6a1aae2d0b8d229707ca93a8?url=pg", "bottom", 209),
    ValidationSite("澳彩之家", "https://buzsxio.821n4-hgj04-edkrft.xyz:29455/article/manager/6a1303be5eabe2c9e91d873a?url=bxj", "bottom", 209),
    ValidationSite("精英战队", "https://buzsxio.821n4-hgj04-edkrft.xyz:29455/article/manager/6a4e865857dc857ae1c13534?url=bxj", "bottom", 209),
    ValidationSite("皇家金堡", "https://buzsxio.821n4-hgj04-edkrft.xyz:29455/article/manager/6a1307a3741e3e91a04e53d4?url=bxj", "bottom", 209),
    ValidationSite("将遇良材", "https://qygfz.b9mav-ho5x7-zwckje.xyz/topic/222780.html", "bottom", 211),
)


def _formal_direction_periods(
    candidates: list[Candidate], pick: str
) -> tuple[set[int], int]:
    ordered = sorted(
        candidates,
        key=lambda candidate: (
            candidate.document_order,
            candidate.original_position,
            candidate.parser_id,
            candidate.document_id,
        ),
    )
    if not ordered:
        return set(), 1
    boundary = ordered[-1] if is_bottom_pick(pick) else ordered[0]
    return {boundary.record.period}, 1


def analyze_documents(
    site: ValidationSite,
    documents: list[str],
    extraction_error: str = "",
    authoritative_value: str = "",
) -> ValidationResult:
    """Report formal validation evidence; never choose among conflicting values."""
    rule = rule_for(site)
    unique_documents: list[str] = []
    seen_documents: set[str] = set()
    for document in documents:
        identity = re.sub(
            r"\s+",
            "",
            normalize_text(re.sub(r"<[^>]+>", " ", document)),
        )
        if identity and identity not in seen_documents:
            seen_documents.add(identity)
            unique_documents.append(document)
    candidates = collect_candidates(
        unique_documents,
        site.name,
        pick=site.pick,
        rule=rule,
        # Targeted diagnostics must expose the complete target-period block;
        # history-mode parser conflict checks are intentionally not used here.
        target_period=site.period,
    )
    target_candidates = [
        candidate for candidate in candidates if candidate.record.period == site.period
    ]
    target_values = tuple(
        sorted(
            {candidate.record.value() for candidate in target_candidates},
            key=lambda value: (len(value), value),
        )
    )
    direction_periods, _ = _formal_direction_periods(candidates, site.pick)
    direction_ok = site.period in direction_periods
    duplicate_tail = any(
        count > 1
        for count in Counter(
            candidate.record.value()
            for candidate in target_candidates
        ).values()
    )
    anchor_ok = bool(target_candidates) and all(
        normalize_text(candidate.record.site_name)
        == normalize_text(site.name)
        for candidate in target_candidates
    )
    keyword_ok = bool(target_candidates) and any(
        candidate.keyword or candidate.anchor for candidate in target_candidates
    )

    formal_records: list[Record] = []
    validation_error = ""
    formal_conflict = False
    reported_conflict_values: tuple[str, ...] = ()
    try:
        decision = validate_documents(
            documents,
            site.name,
            limit=0,
            pick=site.pick,
            rule=rule,
            target_period=site.period,
        )
        formal_records = list(decision.records)
    except Exception as exc:
        validation_error = f"{type(exc).__name__}: {exc}"
        # Same-block target rows are intentionally retained for diagnostics;
        # only the central validator's explicit cross-authority conflict is a
        # failure.  Do not re-create the old ``all target values`` conflict
        # decision in this reporting layer.
        formal_conflict = "存在多个候选且数据冲突" in str(exc)
        if formal_conflict:
            conflict_match = re.search(r"存在多个候选且数据冲突:\s*(.+)$", str(exc))
            if conflict_match:
                reported_conflict_values = tuple(
                    value.strip()
                    for value in conflict_match.group(1).split("、")
                    if value.strip()
                )

    conflict = formal_conflict

    actual_values = tuple(record.value() for record in formal_records) or target_values
    tail_ok = bool(formal_records) and all(
        is_valid_tail_record(record) or bool(record.value_text)
        for record in formal_records
    )
    consistency_error = ""
    if authoritative_value and formal_records and authoritative_value != actual_values[0]:
        consistency_error = (
            "正式抓取结果与统一验证结果不一致: "
            f"正式={authoritative_value}，验证={actual_values[0]}"
        )

    failure_reason = extraction_error or consistency_error
    if not failure_reason and not target_candidates:
        failure_reason = f"没有找到{site.period}期数据"
    if not failure_reason and not direction_ok:
        direction = "bottom" if is_bottom_pick(site.pick) else "top"
        boundary_period = next(iter(direction_periods), "无候选")
        failure_reason = (
            f"绝对{direction}边界是{boundary_period}期，不是指定{site.period}期"
        )
    if not failure_reason and validation_error:
        failure_reason = validation_error
    if not failure_reason and not anchor_ok:
        failure_reason = "站名/栏目锚点未通过"
    if not failure_reason and not keyword_ok:
        failure_reason = "专属关键词未通过"
    if not failure_reason and not tail_ok:
        failure_reason = "目标尾数字段未通过"

    passed = (
        not failure_reason
        and bool(formal_records)
        and direction_ok
        and anchor_ok
        and keyword_ok
        and tail_ok
        and not conflict
    )
    if not failure_reason and conflict:
        failure_reason = (
            f"{site.period}期存在多个候选且数据冲突: "
            f"{'、'.join(reported_conflict_values or target_values)}"
        )
    return ValidationResult(
        site=site,
        passed=passed,
        found_target=bool(target_candidates),
        actual_values=actual_values,
        actual_count=len(formal_records),
        direction_ok=direction_ok,
        anchor_ok=anchor_ok,
        keyword_ok=keyword_ok,
        tail_ok=tail_ok,
        conflict_values=reported_conflict_values if conflict else (),
        duplicate_tail=duplicate_tail,
        failure_reason=failure_reason or "无",
    )


def _collect_diagnostic_documents(site: ValidationSite, timeout: int) -> list[str]:
    rule = rule_for(site)
    documents = collect_documents(
        site.url, timeout, rule.follow_link_keywords, rule.follow_link_rendered,
        rule.follow_link_only, site.pick, site.name, site.period,
        rule.profile_parser, DIRECTION_BOUNDARY_WINDOW,
    )
    rendered = []
    if rule.prefer_rendered:
        rendered = render_browser_documents(site.url, timeout)
    return rendered + documents if rule.prefer_rendered else documents + rendered


def validate_site(site: ValidationSite, timeout: int = 8) -> ValidationResult:
    clear_fetch_cache(site.url)
    documents: list[str] = []
    errors: list[str] = []
    authoritative_value = ""
    try:
        current = crawl_current_site(
            1,
            1,
            site,
            site.period,
            timeout,
            retries=0,
        )
        if current.fail_line:
            errors.append(current.fail_line.split("原因:", 1)[-1].strip())
        elif current.ranking_value is not None:
            authoritative_value = current.ranking_value
        else:
            errors.append("完整手动抓取流程未返回成功或失败结果")
    except Exception as exc:
        errors.append(f"完整手动抓取流程异常({type(exc).__name__}: {exc})")
    try:
        documents = _collect_diagnostic_documents(site, timeout)
    except Exception as exc:
        errors.append(f"诊断文档读取失败({type(exc).__name__}: {exc})")

    return analyze_documents(
        site,
        documents,
        "；".join(errors),
        authoritative_value=authoritative_value,
    )


def format_result(result: ValidationResult) -> str:
    def yes_no(value: bool) -> str:
        return "是" if value else "否"

    conflict = "、".join(result.conflict_values) if result.conflict_values else "无"
    values = "、".join(result.actual_values) if result.actual_values else "无"
    return "\n".join((
        f"站点: {result.site.name}",
        f"网址: {result.site.url}",
        f"指定期数: {result.site.period}期",
        f"配置方向: {result.site.pick}",
        f"是否抓到指定期数: {yes_no(result.found_target)}",
        f"实际尾数: {values}",
        f"数量: {result.actual_count}",
        f"top/bottom 是否正确: {yes_no(result.direction_ok)}",
        f"锚点是否通过: {yes_no(result.anchor_ok)}",
        f"关键词是否通过: {yes_no(result.keyword_ok)}",
        f"尾数是否通过: {yes_no(result.tail_ok)}",
        f"同期冲突: {conflict}",
        f"重复尾数: {yes_no(result.duplicate_tail)}",
        f"失败原因: {result.failure_reason}",
        f"验证结论: {'通过' if result.passed else '失败'}",
    ))


def _file_fingerprint(path: Path) -> tuple[int, str]:
    content = path.read_bytes()
    return len(content), hashlib.sha256(content).hexdigest()


def snapshot_protected_artifacts(
    protected_files: tuple[Path, ...], output_dirs: tuple[Path, ...]
) -> dict[str, tuple[int, str]]:
    paths = [path for path in protected_files if path.exists()] + [
        path for output_dir in output_dirs if output_dir.exists() for path in output_dir.glob("*.txt")
    ]
    return {str(path.resolve()): _file_fingerprint(path) for path in paths if path.is_file()}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="只验证失败站点，不写缓存或正式TXT")
    parser.add_argument("--timeout", type=int, default=8, help="单站超时秒数，默认8，与正式BAT一致")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    protected_files = (
        RECENT_CACHE_PATH,
        SITES_JSON_PATH,
        SITE_HEALTH_PATH,
    )
    output_dirs = (OUTPUT_DIR, FAIL_OUTPUT_DIR)
    before = snapshot_protected_artifacts(protected_files, output_dirs)

    results = []
    for index, site in enumerate(TARGETED_FAILED_SITE_CHECKLIST, start=1):
        print(f"\n[{index}/{len(TARGETED_FAILED_SITE_CHECKLIST)}] 正在验证 {site.name} ...")
        result = validate_site(site, timeout=max(1, args.timeout))
        results.append(result)
        print(format_result(result))

    after = snapshot_protected_artifacts(protected_files, output_dirs)
    if before != after:
        print("\n保护检查失败: 正式配置、缓存、健康状态或成功/失败 TXT 发生变化。")
        return 2

    passed = sum(result.passed for result in results)
    print(f"\n汇总: 通过 {passed} 个，失败 {len(results) - passed} 个。")
    print("保护检查: 正式配置、缓存、健康状态和成功/失败 TXT 均未修改。")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
