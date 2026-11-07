from __future__ import annotations


TABLE_TAIL_HEADERS = ("杀一尾", "绝杀一尾", "禁1尾", "禁尾", "尾数", "杀码尾")

SECTION_KEYWORDS = ("综合绝杀区", "绝杀专区", "杀尾专区", "澳门综合全杀", "香港综合全杀")

SECTION_TAIL_KEYWORDS = (
    "绝杀一尾",
    "杀一尾",
    "稳杀一尾",
    "狠杀一尾",
    "主杀一尾",
    "禁一尾",
    "绝杀一个尾",
    "精准杀尾",
    "精杀一尾",
    "绝杀1尾",
    "绝杀①尾",
    "课杀一尾",
    "绝杀半波",
)

DEFAULT_EXCLUDE_KEYWORDS = (
    "平特一尾",
    "平特二尾",
    "二尾中特",
    "三尾中特",
    "四尾中特",
    "五尾中特",
    "六尾中特",
    "七尾中特",
    "尾数统计",
    "高手榜",
    "规律一尾",
    "公式平尾",
)

STRICT_BOUNDARY_WINDOW = 3
DIRECTION_BOUNDARY_WINDOW = 3

# 期面时间词：用来判断一个尾值属于本期还是上期/回顾。
# 只在取值匹配点之前这么近的距离内查找，避免把整块的开头词当成每个值的归属。
PRIOR_PERIOD_MARKERS = (
    "上一期",
    "上期",
    "上周",
    "上回",
    "上轮",
    "上届",
    "前期",
    "前一",
    "往期",
    "往届",
    "昨日",
    "昨天",
)

CURRENT_PERIOD_MARKERS = ("本期", "今期", "当期", "最新", "这期")

PRIOR_PERIOD_LOOKBEHIND = 12
