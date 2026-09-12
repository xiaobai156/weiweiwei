# 杀尾-修复版2：项目规则

本文件只记录本项目差异；父目录 `C:\Users\Administrator\Desktop\每天工具\爬虫合集\AGENTS.md` 负责通用授权、来源隔离、数据正确性、缓存事务、输出安全和验收规则。

## 范围与身份

- 项目根目录：`C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2`；核心代码在 `shawei\`。
- 正式输出在项目外：`七类数据统一归纳\` 和 `七类数据统一归纳失败\`。
- 新增或修复只处理用户点名的站点、规范化 URL、期数、方向和字段；普通全站运行须由用户明确要求。
- 站点身份由名称、URL、topic/文章 ID、栏目和方向共同确认，不能只凭名称、截图、缓存或旧 TXT。

## 数据和规则

- 普通结果是一个 `0` 至 `9` 的尾数；双尾 URL 必须在 `shawei\config\constants.py` 的 `TWO_TAIL_SITE_URLS` 中授权，并返回两个合法尾数。
- `top`/`bottom` 必须在同一权威文档、同一区块的有效记录中按配置窗口取值；不得跨文档、跨方向、猜期或用相邻记录补值。
- 同期冲突、栏目/作者/ID 不匹配、字段无效、占位行违反专属规则时保持失败。
- URL 级规则唯一维护在 `shawei\config\rules.py`；通用窗口和排除规则在 `shawei\domain\defaults.py`。专属解析失败不得回退通用解析。
- `https://156.225.88.144:12098/#234432` 的“开奖发财【综合杀料】”规则允许精确 `?尾` 未发布行不作为 bottom 边界；其他无效值仍按专属规则处理。
- 同期多记录站点使用 `SAME_PERIOD_RECORD_SELECTION_URLS`：扫描专属区、去除完全重复展示、保留区块顺序，再按方向选择。

## 抓取和写入

- 抓取层只取原始文档；解析器只生成候选和证据；`shawei\validation\validator.py` 独占期数、方向、栏目、数量、合法值、边界和冲突裁决。
- 动态 `/article/admin/`、`/article/manager/`、`/article/lottery/` 页面先按 URL 中的记录 ID 使用专属接口；仅在接口 404/空壳且规则允许时浏览器兜底，并再次核对同一 ID、作者、栏目和正文。
- 单期实时结果只来自本次抓取文档。成功 TXT、失败 TXT 和健康状态定稿后，才可滚动更新缓存；缓存不能改判本期结果。
- 定向修复成功 TXT 只更新指定站点并保留其他站点及原顺序，排行榜随后重算；失败 TXT 只清理或保留指定站点的当期记录；缓存只更新指定站点当期数据。
- 正式文件必须使用项目现有锁、同目录临时文件和原子替换，不得遗留旁路锁文件。

## 入口和文件

- 单期：`shawei_crawler.py --period <期数>`
- 多期：`shawei_multi_period_crawler.py --periods <期数...>`（不更新正式缓存）
- 失败站验证：`shawei_failed_site_validator.py`；它只处理代码内固定的 `TARGETED_FAILED_SITE_CHECKLIST`，不是通用任意站点验证器。
- 失败站定向重抓：`shawei_failed_site_recheck.py --period <期数>`；失败 TXT 是唯一白名单，禁止转为全站抓取。
- 新增站判重：`shawei_duplicate_checker.py` 的 `evaluate_new_site_admission(...)`；连续判重：`shawei_consecutive_duplicate_checker.py`。
- 正式配置：`sites.json`；正式缓存：`recent_10_cache.json`；健康记录：`shawei_site_health.json`。
- 成功文件：`七类数据统一归纳\<期数>期-尾.txt`；失败文件：`七类数据统一归纳失败\<期数>期-尾-失败.txt`。

对应 BAT：`爬虫-每天杀尾.bat`、`爬虫-每天杀尾-多期不更新缓存.bat`、`爬虫-每天杀尾 - 检测重复.bat`。

## 修复和验收

- 失败站修复：用户说“开始验证”时只做真实隔离验证；用户明确“开始正式更新”后，才写正式 TXT、缓存或配置。
- 封存站点不抓取、不写缓存、不写正式输出；恢复或删除须点名授权。
- 代码修改至少运行受影响测试、Python 编译/静态检查和指定站点真实流程；共享抓取、校验、缓存、存储或入口变化再运行完整测试。
- 报告必须分别说明真实验证、抓取失败、缓存更新失败和未完成，不能把局部测试或计划当成正式成功。
