"""只读核对本次定向正式结果，验收记录只写入本隔离目录。"""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
BEFORE = OUT / "before"
SUCCESS = ROOT.parent / "七类数据统一归纳" / "292期-尾.txt"
FAILURE = ROOT.parent / "七类数据统一归纳失败" / "292期-尾-失败.txt"
CACHE = ROOT / "recent_10_cache.json"
EXPECTED = {"小明哥上": "7", "可见一斑": "3", "故里春意": "0"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def data_lines(path):
    body = path.read_text(encoding="utf-8-sig").split("内容", 1)[0]
    return [line for line in body.splitlines() if re.match(r"^\d尾 ", line)]


def failure_lines(path):
    return [line for line in path.read_text(encoding="utf-8-sig").splitlines() if line.startswith("失败 ")]


def identity(item):
    url = guli["old_url"] if item["url"] == guli["mirror_url"] else item["url"]
    return item["name"], url, item["pick"]


guli = read_json(OUT / "mirror_guli_formal_audit.json")
formal_before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (SUCCESS, FAILURE, CACHE, ROOT / "sites.json")}
assert formal_before == guli["after_sha256"], "正式文件与最近正式写入审计不一致"
old_config = read_json(OUT / "before_guli_mirror" / "sites.json")
new_config = read_json(ROOT / "sites.json")
assert len(old_config) == len(new_config) == 297
config_changes = [(a, b) for a, b in zip(old_config, new_config) if a != b]
assert len(config_changes) == 1
a, b = config_changes[0]
assert a["name"] == b["name"] == "故里春意"
assert a["url"] == guli["old_url"] and b["url"] == guli["mirror_url"]
assert a == dict(b, url=guli["old_url"])

old_rows, new_rows = data_lines(BEFORE / SUCCESS.name), data_lines(SUCCESS)
assert len(old_rows) == 259 and len(new_rows) == 262
assert [row for row in new_rows if row.split()[-1] not in EXPECTED] == old_rows
for name, value in EXPECTED.items():
    assert new_rows.count(f"{value}尾 {name}") == 1

old_fail, new_fail = failure_lines(BEFORE / FAILURE.name), failure_lines(FAILURE)
assert len(old_fail) == 11 and len(new_fail) == 8
assert new_fail == [line for line in old_fail if line.split()[1] not in EXPECTED]
blocks = lambda path: [b.strip() for b in re.split(r"\r?\n\s*\r?\n", path.read_text(encoding="utf-8-sig")) if b.strip()]
assert blocks(FAILURE) == [b for b in blocks(BEFORE / FAILURE.name) if b.split()[1] not in EXPECTED]

old_cache, new_cache = read_json(BEFORE / CACHE.name), read_json(CACHE)
old_items = {identity(item): item for item in old_cache["sites"]}
new_items = {identity(item): item for item in new_cache["sites"]}
assert list(old_items) == list(new_items)
assert len(old_items) == len(old_cache["sites"]) == len(new_cache["sites"]) == len(new_items)
changed = [key for key in old_items if old_items[key] != new_items[key]]
assert {key[0] for key in changed} == set(EXPECTED) and len(changed) == 3
for key in changed:
    old, new = old_items[key], new_items[key]
    old_values = dict(zip(old["periods"], old["values"]))
    new_values = dict(zip(new["periods"], new["values"]))
    assert new_values[292] == EXPECTED[key[0]]
    assert {p: v for p, v in old_values.items() if p != 292} == {p: v for p, v in new_values.items() if p != 292}
    assert 292 not in new.get("failed_periods", [])
    assert "292" not in new.get("failure_reasons", {})
    assert [p for p in old.get("failed_periods", []) if p != 292] == new.get("failed_periods", [])
    assert {p: v for p, v in old.get("failure_reasons", {}).items() if p != "292"} == new.get("failure_reasons", {})
    mutable = {"periods", "values", "extended", "failed_periods", "failure_reasons"}
    if key[0] == "故里春意":
        assert old["url"] == guli["old_url"] and new["url"] == guli["mirror_url"]
        mutable.add("url")
    assert {k: v for k, v in old.items() if k not in mutable} == {k: v for k, v in new.items() if k not in mutable}
mutable_root = {"generated_at", "vector_count", "fail_count", "fail_lines", "sites", "config_fingerprint"}
assert {k: v for k, v in old_cache.items() if k not in mutable_root} == {k: v for k, v in new_cache.items() if k not in mutable_root}
assert new_cache["fail_lines"] == new_fail
assert new_cache["period"] == 292 and new_cache["window"] == 10
assert new_cache["config_fingerprint"] == "c9693ce06a9d5eeeef6b222202f7e74776fe65f6ad3f7ea3711e2d28a7e922ae"
active = [item for item in new_cache["sites"] if not item.get("archived")]
assert new_cache["vector_count"] == sum(not bool(item.get("failed_periods")) for item in active)
assert new_cache["fail_count"] == sum(bool(item.get("failed_periods")) for item in active)
historical_failures = [item["name"] for item in active if item.get("failed_periods") and 292 not in item["failed_periods"]]

live = read_json(OUT / "repaired_live_292.json")
assert len(live) == 2
assert {row["site"]["name"] for row in live} == {"小明哥上", "可见一斑"}
live.append({"site": {"name": "故里春意"}, "result": guli["live_result"]})
for row in live:
    result = row["result"]
    assert result["ranking_value"] == EXPECTED[row["site"]["name"]]
    assert result["success_line"] and result["fail_line"] is None
negative_checks = read_json(OUT / "mirror_guli_validation.json")["negative_checks"]
assert set(negative_checks) == {"adjacent", "missing", "direction"} and all(negative_checks.values())
mirror_review = read_json(OUT / "remaining_mirror_review.json")
assert mirror_review["period"] == 292 and mirror_review["new_successes_in_this_review"] == 0

hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (SUCCESS, FAILURE, CACHE, ROOT / "sites.json")}
assert hashes == formal_before, "隔离审计期间正式文件发生变化"

classifications = []
for line in old_fail:
    parts = line.split()
    name, url, pick = parts[1], parts[2], parts[4]
    if name == "故里春意":
        status, reason = "镜像修复成功", "真实目录链接及历史文档确认topic350485、作者及杀肖杀尾栏目；镜像292期bottom为0尾"
    elif name in EXPECTED:
        status, reason = "修复成功", f"292期{EXPECTED[name]}尾；滚动崩溃前已有正文，保留快照后经原解析及校验成功"
    elif name == "六玄网":
        status, reason = "无292数据/边界异常", "原线路、915577.cc及网页提供的bb5官方线路同一综合绝杀区首行145，下一行291，无292；不猜期、不取其他栏目"
    elif name == "昙花一现":
        status, reason = "来源异常", "原URL证书名称错误、HTTP404或域名停放页；指定名称和域名搜索未找到可验证镜像"
    elif name == "正气凛然":
        status, reason = "来源异常", "原topic身份丢失；aczj.cc同名候选是绝杀三尾，非原单尾，不采用"
    else:
        status, reason = "来源异常", "原topic跳其他论坛或线路页；真实目录和搜索候选尚未核实相同文章、作者与单尾栏目，保留失败"
    classifications.append(dict(name=name, original_url=url, url=guli["mirror_url"] if name == "故里春意" else url, pick=pick, period=292, status=status, reason=reason))

audit = {
    "verified_at": datetime.now().isoformat(timespec="seconds"),
    "period": 292,
    "scope": "仅原始失败TXT的11站；3站292期原实时服务成功；未全量",
    "counts": {"original_failures": 11, "repaired": 3, "source_errors": 7, "no_current_data": 1, "remaining_failures": 8, "success_before": 259, "success_after": 262},
    "classifications": classifications,
    "checks": {"non_target_success_and_order_preserved": True, "non_target_cache_entries_preserved": True, "target_history_preserved": True, "only_three_cache_entries_changed": True, "only_guli_config_url_changed": True, "remaining_failure_blocks_preserved": True, "formal_hashes_unchanged_during_audit": True},
    "cache_metadata": {"vector_count": new_cache["vector_count"], "fail_count": new_cache["fail_count"], "current_fail_lines": len(new_fail), "historical_failures_without_292_failure": historical_failures, "meaning": "vector_count/fail_count统计近10期内有无failed_periods，不是当期成功/失败TXT行数"},
    "tests": {"browser_tests_previous_run": "7 passed", "guli_affected_tests_previous_run": "43 passed", "python_compile_previous_run": "passed", "full_suite_previous_run": "306 passed, 1 failed", "remaining_failure": "test_audit_formal_config_contract.py::test_discuz_main_post_parser_reads_revealed_locked_tail；fixture无canonical/site_url，Discuz帖子URL/标题身份校验拒绝；名单外，未放松校验", "guli_negative_checks": negative_checks, "limitation": "本轮仅更新隔离证据和结构审计，没有重跑全套，全部负向场景未验收"},
    "mirror_review": "remaining_mirror_review.json",
    "sha256": hashes,
}
(OUT / "final_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
rows = ["| 站点 | 方向 | 分类 | 证据/处理 |", "|---|---|---|---|"]
for item in classifications:
    rows.append(f'| [{item["name"]}]({item["url"]}) | {item["pick"]} | {item["status"]} | {item["reason"]} |')
report = f'''# 292期杀尾失败白名单验收记录

本记录取代此前261成功/9失败的旧版结论。原失败11站逐站浏览器核验后：修复成功3站、来源异常7站、无292数据且边界异常1站。当前成功262项、失败8项，仅处理292期，未全量。

小明哥上（top）7尾、可见一斑（bottom）3尾、故里春意（bottom）0尾已写入正式成功TXT及三站292期缓存，并从失败TXT清除。成功259→262，失败11→8。三站均有原实时抓取、解析和统一校验流程成功记录，未使用旧缓存补值。

## 逐站分类

{chr(10).join(rows)}

## 修复与数据边界

修改shawei/fetch/browser.py的滚动异常处理：保存滚动前正文和HTML，异常时仅返回非空快照，之后仍经过原解析和统一校验；不以缓存、相邻期或其他来源补值。

故里春意的真实目录链接及历史文档确认同一topic350485、作者和杀肖杀尾栏目；验证镜像{guli["mirror_url"]}的292期bottom为0尾。sites.json仅此URL变化，URL规则登记相同专属解析。

结构审计通过：其他259条成功内容和顺序保留；缓存278项身份和顺序保留，仅三站entry变化，其中故里春意URL随验证镜像更新；三站历史值及历史失败信息保留，292失败状态清除；其余8条失败block原文保留。297项配置仅故里春意URL变化。正式文件哈希与mirror_guli_formal_audit.json一致，本轮未再次写正式文件。

缓存根vector_count={new_cache["vector_count"]}、fail_count={new_cache["fail_count"]}按近10期failed_periods统计；其中{len(historical_failures)}站仅有历史期失败，故不等于当期262/8。未擅改统计口径。

## 验证与限制

- 真实292期成功证据：repaired_live_292.json两站，mirror_guli_formal_audit.json一站。故里春意隔离负向验证拒绝相邻291、不存在999及反向top292。
- 前次浏览器相关测试7 passed、故里春意受影响测试43 passed，修改文件编译通过。本轮仅更新隔离证据和审计，没有重跑全套；全部负向验收场景未完成。
- 完整测试前次结果：306 passed、1 failed。未通过项为test_discuz_main_post_parser_reads_revealed_locked_tail，fixture缺canonical/site_url，严格Discuz身份校验拒绝；属于名单外，本次未放松身份要求。完整测试未全绿。
- 其他8站保持失败，不生成成功值。来源异常不能判作无数据；六玄网跟随网页真实bb5官方线路后仍无292，不将145期猜成292期。正气凛然同名三尾候选不能替代原单尾。镜像研究细节见remaining_mirror_review.json，未认定镜像不存在。
- probe_292.json为初探记录，其仅凭落地页含292的判断不能证明原站身份；最终分类以本报告逐站浏览器核验为准。iframe和script抓取仅为隔离诊断，未拼接为成功数据。
- 保留原有其他工作区改动，未提交或推送。正式文件哈希、逐项断言和完整URL见final_audit.json。
'''
(OUT / "验收记录.md").write_text(report, encoding="utf-8")
assert hashes == {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (SUCCESS, FAILURE, CACHE, ROOT / "sites.json")}, "隔离报告写入影响正式文件"
print(json.dumps({"audit": "passed", "success": len(new_rows), "failures": len(new_fail), "changed_cache_sites": [key[0] for key in changed], "historical_failures": historical_failures, "sha256": hashes}, ensure_ascii=False, indent=2))
