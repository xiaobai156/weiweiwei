# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import re
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

import shawei_crawler as crawler
from shawei.domain.models import Candidate


@dataclass(frozen=True)
class ValidationSite:
    name: str
    url: str
    pick: str
    period: int
    rule: crawler.StrictRule


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
    conflict_resolved_by_rule: bool
    failure_reason: str


FAILED_SITE_CHECKLIST = (
    ValidationSite(
        name="六合宏图",
        url="https://fansiggg.jc2q8-whfmg-vajjui.xyz:29433/article/manager/6a096820291caff3edcb8b3c?url=dyj",
        pick="bottom",
        period=197,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="liuhehongtu_manager_tail",
            chunk_keywords=("六合宏图", "绝杀1尾"),
            prefer_rendered=False,
            require_site_keyword=True,
        ),
    ),
    ValidationSite(
        name="独占财经",
        url="https://fansiggg.jc2q8-whfmg-vajjui.xyz:29433/article/manager/6a096bc9291caff3edcb8bb8?url=dyj",
        pick="bottom",
        period=197,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="duzhancaijing_manager_tail",
            chunk_keywords=("独占财经", "绝杀一尾"),
            prefer_rendered=False,
            require_site_keyword=True,
        ),
    ),
    ValidationSite(
        name="挽歌半夏",
        url="https://vnxqseiu.ymm13-381iq-zcgmtu.xyz:29400/article/manager/6a081771e0d076537e1df83e?url=jdb",
        pick="bottom",
        period=197,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="wangebanxia_manager_tail",
            chunk_keywords=("挽歌半夏", "绝杀一尾"),
            prefer_rendered=False,
            require_site_keyword=True,
        ),
    ),
    ValidationSite(
        name="唯梦唯梦",
        url="https://h6.118t118.com:8443/user?userId=274001",
        pick="top",
        period=201,
        rule=crawler.StrictRule(
            allowed_sources=("user_feed",),
            chunk_keywords=("绝杀一尾", "绝杀一个尾", "绝1尾", "精准杀尾", "精1尾"),
            prefer_rendered=True,
            profile_parser="118_user_release",
        ),
    ),
    ValidationSite(
        name="笑歌戏舞",
        url="https://tcwsqrno.ril3o-7ghui-hiepuc.work:16633/topic/226021.html",
        pick="bottom",
        period=201,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="xiaoge_current_tail",
            chunk_keywords=("笑歌戏舞", "杀["),
            require_site_keyword=True,
            prefer_rendered=True,
        ),
    ),
    ValidationSite(
        name="百花齐放",
        url="https://tcwsqrno.ril3o-7ghui-hiepuc.work:16633/topic/205695.html",
        pick="bottom",
        period=201,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="baihua_current_tail",
            chunk_keywords=("百花齐放", "绝杀一尾"),
            require_site_keyword=True,
            prefer_rendered=True,
        ),
    ),
    ValidationSite(
        name="困难佛门",
        url="https://wcvwpj.mb4i3-vwk1b-cadppa.work/#/users/46821",
        pick="top",
        period=201,
        rule=crawler.StrictRule(
            allowed_sources=("user_feed", "compact"),
            chunk_keywords=("绝杀一尾",),
            prefer_rendered=False,
            profile_parser="spa_user_forums",
        ),
    ),
    ValidationSite(
        name="周易算算",
        url="https://qvuuqqs.8imf7-hteuh-ylwuqv.xyz/#/users/4606/references/15339511",
        pick="top",
        period=201,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="zhouyi_qvuu_tail",
            chunk_keywords=("绝杀一尾",),
            prefer_rendered=False,
            profile_parser="qvuu_reference_history",
        ),
    ),
    ValidationSite(
        name="曾氏",
        url="https://qvuuqqs.8imf7-hteuh-ylwuqv.xyz/#/forums/15340352",
        pick="top",
        period=201,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="zengshi_qvuu_tail",
            chunk_keywords=("曾氏每期绝杀一尾", "绝杀一尾"),
            prefer_rendered=False,
            profile_parser="qvuu_author_reference_history",
        ),
    ),
    ValidationSite(
        name="山海经",
        url="https://mwztnor.vapgy-gskm7-sqbyej.work:17455/topic/564223.html",
        pick="top",
        period=201,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="shanhaijing_current_tail",
            chunk_keywords=("精品好料", "绝杀一尾", "杀一尾"),
            prefer_rendered=True,
        ),
    ),
    ValidationSite(
        name="良辰美景",
        url="https://ztpqrap.m8sbq-na911-wmojzb.work:29444/article/admin/6a1450acbf0a6cb1dd38fbf8?url=gsw",
        pick="bottom",
        period=201,
        rule=crawler.StrictRule(
            allowed_sources=("compact",),
            chunk_keywords=("良辰美景", "绝杀一尾", "绝杀1尾", "杀一尾"),
            prefer_rendered=False,
        ),
    ),
    ValidationSite(
        name="两小无猜",
        url="https://estsghu.t7gsm-xl1x8-uohlna.xyz:16677/topic/357708.html",
        pick="bottom",
        period=201,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="liangxiao_current_tail",
            chunk_keywords=("两小无猜", "绝杀一尾"),
            require_site_keyword=True,
            prefer_rendered=True,
        ),
    ),
    ValidationSite(
        name="知名日历",
        url="https://zcphjs.ce83x-ms2rz-orwude.work:12277/#/users/1384",
        pick="top",
        period=201,
        rule=crawler.StrictRule(
            allowed_sources=("user_feed",),
            chunk_keywords=("绝杀一尾",),
            prefer_rendered=False,
            require_site_keyword=False,
            profile_parser="zcphjs_user_forums",
        ),
    ),
    ValidationSite(
        name="独特招牌",
        url="https://zcphjs.ce83x-ms2rz-orwude.work:12277/#/users/1676",
        pick="top",
        period=201,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="dute_zhaopai_profile_tail",
            chunk_keywords=("精杀一尾",),
            prefer_rendered=False,
            require_site_keyword=True,
            profile_parser="zcphjs_user_forums",
        ),
    ),
    ValidationSite(
        name="朱红豆浆",
        url="https://zcphjs.ce83x-ms2rz-orwude.work:12277/#/users/29645",
        pick="top",
        period=201,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="zhuhong_doujiang_profile_tail",
            chunk_keywords=("绝杀1尾",),
            prefer_rendered=False,
            require_site_keyword=True,
            profile_parser="zcphjs_user_forums",
        ),
    ),
    ValidationSite(
        name="老化针",
        url="https://zcphjs.ce83x-ms2rz-orwude.work:12277/#/users/1466",
        pick="top",
        period=201,
        rule=crawler.StrictRule(
            allowed_sources=("user_feed",),
            chunk_keywords=("绝杀一尾",),
            prefer_rendered=False,
            require_site_keyword=False,
            profile_parser="zcphjs_user_forums",
        ),
    ),
)


TARGETED_FAILED_SITE_CHECKLIST = (
    ValidationSite(
        name="笑歌戏舞",
        url="https://tcwsqrno.ril3o-7ghui-hiepuc.work:16633/topic/226021.html",
        pick="bottom",
        period=203,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="xiaoge_topic_main_tail",
            chunk_keywords=("笑歌戏舞", "杀["),
            prefer_rendered=True,
            require_site_keyword=True,
        ),
    ),
    ValidationSite(
        name="赴火蹈刃",
        url="https://sqddimfu.evs71-kia2b-gshsdc.xyz:16677/topic/219850.html",
        pick="bottom",
        period=203,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="fuhuo_topic_main_tail",
            chunk_keywords=("赴火蹈刃", "绝杀一尾"),
            prefer_rendered=True,
            require_site_keyword=True,
        ),
    ),
    ValidationSite(
        name="目治手营",
        url="https://sqddimfu.evs71-kia2b-gshsdc.xyz:16677/topic/226259.html",
        pick="bottom",
        period=203,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="muzhi_topic_main_tail",
            chunk_keywords=("目治手营", "绝杀一尾"),
            prefer_rendered=True,
            require_site_keyword=True,
        ),
    ),
    ValidationSite(
        name="山海经",
        url="https://mwztnor.vapgy-gskm7-sqbyej.work:17455/topic/564223.html",
        pick="top",
        period=203,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="shanhaijing_topic_main_tail",
            chunk_keywords=("精品好料", "绝杀一尾", "杀一尾"),
            prefer_rendered=True,
            require_site_keyword=False,
        ),
    ),
    ValidationSite(
        name="风驰电掣",
        url="https://qarppl.154bo-trld9-qppors.xyz:16677/topic/326551.html",
        pick="bottom",
        period=203,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="fengchi_topic_main_tail",
            chunk_keywords=("风驰电掣", "绝杀一尾"),
            prefer_rendered=True,
            require_site_keyword=True,
        ),
    ),
    ValidationSite(
        name="坚韧不拔",
        url="https://lxbwvnfv.3gwtt-z9y8n-wsxdfy.xyz:16677/topic/458345.html",
        pick="bottom",
        period=203,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="jianren_topic_main_tail",
            chunk_keywords=("坚韧不拔", "绝杀一尾"),
            prefer_rendered=True,
            require_site_keyword=False,
        ),
    ),
    ValidationSite(
        name="碌碌庸才",
        url="https://eolantz.v6nli-9yz71-rihyny.xyz:16677/topic/447895.html",
        pick="top",
        period=203,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="lulu_topic_main_tail",
            chunk_keywords=("碌碌庸才", "绝杀一尾"),
            prefer_rendered=True,
            require_site_keyword=False,
        ),
    ),
    ValidationSite(
        name="一点红",
        url="https://kfkxqua.vohzh-s0pbh-vhwsal.xyz:16677/topic/246761.html",
        pick="bottom",
        period=209,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="yidianhong_current_tail",
            chunk_keywords=("一点红", "绝杀一尾", "绝杀1尾", "杀一尾"),
            prefer_rendered=True,
            require_site_keyword=False,
        ),
    ),
    ValidationSite(
        name="傻傻熊二",
        url="https://ihdfsxo.kgqq8-mbcz5-qpbkfh.xyz:16677/topic/258481.html",
        pick="bottom",
        period=206,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="shashaxionger_current_tail",
            chunk_keywords=("傻傻熊二", "绝杀一尾", "绝杀1尾", "杀一尾"),
            prefer_rendered=True,
            require_site_keyword=False,
        ),
    ),
    ValidationSite(
        name="翻本行动",
        url="https://drxgkjt.uu1oc-eyjpt-uxyccu.xyz:29400/article/manager/6a33e58fdfa16552b923d27f?url=jyb",
        pick="bottom",
        period=206,
        rule=crawler.StrictRule(
            allowed_sources=("compact",),
            chunk_keywords=("翻本行动", "绝杀一尾", "绝杀1尾", "杀一尾", "精准杀尾", "精杀一尾"),
            prefer_rendered=True,
            require_site_keyword=False,
        ),
    ),
    ValidationSite(
        name="淋漓尽致",
        url="https://kulipur.l5paz-a0o8v-uozmmd.xyz:16677/topic/435507.html",
        pick="bottom",
        period=206,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="linlinjinzhi_current_tail",
            chunk_keywords=("淋漓尽致", "绝杀一尾", "绝杀1尾", "杀一尾", "精准杀尾", "精杀一尾"),
            prefer_rendered=True,
            require_site_keyword=False,
        ),
    ),
    ValidationSite(
        name="挥手乾坤",
        url="https://pa4dwcnd64.772149.shop/bbs/topic.php?id=726",
        pick="bottom",
        period=206,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="huishouqiankun_topic_tail",
            chunk_keywords=("挥手乾坤", "绝杀一尾"),
            require_site_keyword=True,
        ),
    ),
    ValidationSite(
        name="财富高手论坛",
        url="https://x1rvueyk50.669332.shop/bbs/",
        pick="bottom",
        period=206,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="caifu_gaoshou_kill_table",
            chunk_keywords=("财富高手论坛", "绝杀专区", "杀一尾"),
            require_site_keyword=True,
        ),
    ),
    ValidationSite(
        name="皇家赐码",
        url="https://wigrzse.3acpt-tc9xa-kzxasm.xyz:29444/article/manager/6a1570948be59b17287c6dd7?url=pg",
        pick="bottom",
        period=209,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="huangjia_cima_manager_tail",
            chunk_keywords=("皇家赐码", "绝杀一尾"),
            require_site_keyword=True,
        ),
    ),
    ValidationSite(
        name="打造辉煌",
        url="https://wigrzse.3acpt-tc9xa-kzxasm.xyz:29444/article/manager/6a1556f2d9d9fc2cea524224?url=pg",
        pick="bottom",
        period=209,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="dazao_huihuang_manager_tail",
            chunk_keywords=("打造辉煌", "绝杀1尾"),
            require_site_keyword=True,
        ),
    ),
    ValidationSite(
        name="夜黑风高",
        url="https://wigrzse.3acpt-tc9xa-kzxasm.xyz:29444/article/manager/6a639071b3f65fed7d622154?url=pg",
        pick="bottom",
        period=209,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="yehei_fenggao_manager_tail",
            chunk_keywords=("夜黑风高", "绝杀1尾"),
            require_site_keyword=True,
        ),
    ),
    ValidationSite(
        name="陈年老酒",
        url="https://wigrzse.3acpt-tc9xa-kzxasm.xyz:29444/article/manager/6a1aae2d0b8d229707ca93a8?url=pg",
        pick="bottom",
        period=209,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="chennian_laojiu_manager_tail",
            chunk_keywords=("陈年老酒", "绝杀一尾"),
            require_site_keyword=True,
        ),
    ),
    ValidationSite(
        name="澳彩之家",
        url="https://buzsxio.821n4-hgj04-edkrft.xyz:29455/article/manager/6a1303be5eabe2c9e91d873a?url=bxj",
        pick="bottom",
        period=209,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="aocai_zhi_jia_manager_tail",
            chunk_keywords=("澳彩之家", "绝杀1尾"),
            require_site_keyword=True,
        ),
    ),
    ValidationSite(
        name="精英战队",
        url="https://buzsxio.821n4-hgj04-edkrft.xyz:29455/article/manager/6a4e865857dc857ae1c13534?url=bxj",
        pick="bottom",
        period=209,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="jingying_zhandui_manager_tail",
            chunk_keywords=("精英战队", "绝杀一尾"),
            require_site_keyword=True,
        ),
    ),
    ValidationSite(
        name="皇家金堡",
        url="https://buzsxio.821n4-hgj04-edkrft.xyz:29455/article/manager/6a1307a3741e3e91a04e53d4?url=bxj",
        pick="bottom",
        period=209,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="huangjia_jinbao_manager_tail",
            chunk_keywords=("皇家金堡", "绝杀一尾"),
            require_site_keyword=True,
        ),
    ),
    ValidationSite(
        name="将遇良材",
        url="https://qygfz.b9mav-ho5x7-zwckje.xyz/topic/222780.html",
        pick="bottom",
        period=211,
        rule=crawler.StrictRule(
            allowed_sources=("dedicated",),
            dedicated_parser="jiangyu_bottom_cycle_tail",
            chunk_keywords=("将遇良材", "绝杀一尾"),
            prefer_rendered=True,
            require_site_keyword=True,
        ),
    ),
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
    boundary = ordered[-1] if crawler.is_bottom_pick(pick) else ordered[0]
    return {boundary.record.period}, 1


def _extract_source_records(
    document: str,
    site: ValidationSite,
    source: str,
) -> list[crawler.Record]:
    """Expose formal parser candidates for diagnostics without revalidating them."""
    source_rule = replace(site.rule, allowed_sources=(source,))
    candidates = crawler.collect_candidates(
        [document],
        site.name,
        pick=site.pick,
        rule=source_rule,
        target_period=None,
    )
    return [candidate.record for candidate in candidates]


def extract_trial_records(
    documents: list[str], site: ValidationSite
) -> list[crawler.Record]:
    """Compatibility name; all decisions come from the formal validator."""
    decision = crawler.validate_documents(
        documents,
        site.name,
        limit=0,
        pick=site.pick,
        rule=site.rule,
        target_period=site.period,
    )
    return list(decision.records)


def analyze_documents(
    site: ValidationSite,
    documents: list[str],
    authoritative_records: list[crawler.Record],
    extraction_error: str = "",
    authoritative_value: str = "",
) -> ValidationResult:
    """Report formal validation evidence; never choose among conflicting values."""
    unique_documents: list[str] = []
    seen_documents: set[str] = set()
    for document in documents:
        identity = re.sub(
            r"\s+",
            "",
            crawler.normalize_text(re.sub(r"<[^>]+>", " ", document)),
        )
        if identity and identity not in seen_documents:
            seen_documents.add(identity)
            unique_documents.append(document)
    candidates = crawler.collect_candidates(
        unique_documents,
        site.name,
        pick=site.pick,
        rule=site.rule,
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
        crawler.normalize_text(candidate.record.site_name)
        == crawler.normalize_text(site.name)
        for candidate in target_candidates
    )
    keyword_ok = bool(target_candidates) and any(
        candidate.keyword or candidate.anchor for candidate in target_candidates
    )

    formal_records: list[crawler.Record] = []
    validation_error = ""
    formal_conflict = False
    reported_conflict_values: tuple[str, ...] = ()
    try:
        decision = crawler.validate_documents(
            documents,
            site.name,
            limit=0,
            pick=site.pick,
            rule=site.rule,
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
        crawler.is_valid_tail_record(record) or bool(record.value_text)
        for record in formal_records
    )
    authoritative_values = tuple(record.value() for record in authoritative_records)
    consistency_error = ""
    if authoritative_values and formal_records and authoritative_values != tuple(
        record.value() for record in formal_records
    ):
        consistency_error = (
            "正式抓取结果与统一验证结果不一致: "
            f"正式={','.join(authoritative_values)}，验证={','.join(actual_values)}"
        )
    if authoritative_value and formal_records and authoritative_value != actual_values[0]:
        consistency_error = (
            "正式抓取结果与统一验证结果不一致: "
            f"正式={authoritative_value}，验证={actual_values[0]}"
        )

    failure_reason = extraction_error or consistency_error
    if not failure_reason and not target_candidates:
        failure_reason = f"没有找到{site.period}期数据"
    if not failure_reason and not direction_ok:
        direction = "bottom" if crawler.is_bottom_pick(site.pick) else "top"
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
        conflict_resolved_by_rule=False,
        failure_reason=failure_reason or "无",
    )


def _collect_diagnostic_documents(site: ValidationSite, timeout: int) -> list[str]:
    rule = site.rule
    documents = crawler.collect_documents(
        site.url, timeout, rule.follow_link_keywords, rule.follow_link_rendered,
        rule.follow_link_only, site.pick, site.name, site.period,
        rule.profile_parser, crawler.DIRECTION_BOUNDARY_WINDOW,
    )
    rendered = []
    if crawler.is_root_page_url(site.url) or rule.prefer_rendered:
        rendered = crawler.render_browser_documents(site.url, timeout)
    return rendered + documents if rule.prefer_rendered else documents + rendered


def validate_site(site: ValidationSite, timeout: int = 8) -> ValidationResult:
    crawler.clear_fetch_cache(site.url)
    documents: list[str] = []
    errors: list[str] = []
    authoritative_value = ""
    try:
        current = crawler.crawl_current_site(
            1,
            1,
            site,
            site.period,
            timeout,
            retries=0,
            missing_retries=2,
            missing_retry_delay=2,
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
        [],
        "；".join(errors),
        authoritative_value=authoritative_value,
    )


def format_result(result: ValidationResult) -> str:
    def yes_no(value: bool) -> str:
        return "是" if value else "否"

    conflict = "、".join(result.conflict_values) if result.conflict_values else "无"
    values = "、".join(result.actual_values) if result.actual_values else "无"
    resolved = "（URL专属方向规则已处理）" if result.conflict_resolved_by_rule else ""
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
        f"同期冲突: {conflict}{resolved}",
        f"重复尾数: {yes_no(result.duplicate_tail)}",
        f"失败原因: {result.failure_reason}",
        f"验证结论: {'通过' if result.passed else '失败'}",
    ))


def _file_fingerprint(path: Path) -> tuple[int, str]:
    content = path.read_bytes()
    return len(content), hashlib.sha256(content).hexdigest()


def snapshot_protected_artifacts(cache_path: Path, output_dirs: tuple[Path, ...]) -> dict[str, tuple[int, str]]:
    paths = ([cache_path] if cache_path.exists() else []) + [
        path for output_dir in output_dirs if output_dir.exists() for path in output_dir.glob("*.txt")
    ]
    return {str(path.resolve()): _file_fingerprint(path) for path in paths if path.is_file()}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="只验证失败站点，不写缓存或正式TXT")
    parser.add_argument("--timeout", type=int, default=8, help="单站超时秒数，默认8，与正式BAT一致")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cache_path = crawler.SCRIPT_DIR / "recent_10_cache.json"
    output_dirs = (crawler.OUTPUT_DIR, crawler.FAIL_OUTPUT_DIR)
    before = snapshot_protected_artifacts(cache_path, output_dirs)

    results = []
    for index, site in enumerate(TARGETED_FAILED_SITE_CHECKLIST, start=1):
        print(f"\n[{index}/{len(TARGETED_FAILED_SITE_CHECKLIST)}] 正在验证 {site.name} ...")
        result = validate_site(site, timeout=max(1, args.timeout))
        results.append(result)
        print(format_result(result))

    after = snapshot_protected_artifacts(cache_path, output_dirs)
    if before != after:
        print("\n保护检查失败: recent_10_cache.json 或正式成功/失败 TXT 发生变化。")
        return 2

    passed = sum(result.passed for result in results)
    print(f"\n汇总: 通过 {passed} 个，失败 {len(results) - passed} 个。")
    print("保护检查: recent_10_cache.json 和正式成功/失败 TXT 均未修改。")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
