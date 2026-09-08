from __future__ import annotations

import re

from shawei.domain.defaults import (
    DIRECTION_BOUNDARY_WINDOW,
    DEFAULT_EXCLUDE_KEYWORDS,
    SECTION_KEYWORDS,
    SECTION_TAIL_KEYWORDS,
    STRICT_BOUNDARY_WINDOW,
    TABLE_TAIL_HEADERS,
)


__all__ = [
    "DIRECTION_BOUNDARY_WINDOW",
    "DEFAULT_EXCLUDE_KEYWORDS",
    "SECTION_KEYWORDS",
    "SECTION_TAIL_KEYWORDS",
    "STRICT_BOUNDARY_WINDOW",
    "TABLE_TAIL_HEADERS",
]


SCRIPT_SRC_RE = re.compile(r"""<script\b[^>]*\bsrc\s*=\s*(["'])(.*?)\1""", re.I | re.S)


DOCUMENT_WRITELN_RE = re.compile(
    r"""document\.writeln\s*\(\s*(["'])(.*?)\1\s*\)\s*;""", re.I | re.S
)


STRDECODE_RE = re.compile(r"""strdecode\s*\(\s*(["'])(.*?)\1\s*\)""", re.I | re.S)


DECODE_B64_RE = re.compile(r"""decodeB64\s*\(\s*(["'])(.*?)\1\s*\)""", re.I | re.S)


PAGE_DATA_RE = re.compile(r"""__PAGE_DATA__\s*=\s*(["'])(.*?)\1""", re.I | re.S)


PERIOD_RE = re.compile(r"(?<!\d)(\d{1,4})\s*期")


TAIL_RE = re.compile(r"(?<!\d)(\d{1,3})\s*尾")


DRAW_RE = re.compile(r"开\s*[:：?\uff1f]?\s*([^\s\[\]<>|，,\u3002\uff1b;]{1,24})")


WAVE_VALUE_RE = re.compile(r"(红波单|红波双|蓝波单|蓝波双|绿波单|绿波双|红单|红双|蓝单|蓝双|绿单|绿双)")


PERIOD_CHUNK_RE = re.compile(r"(?=(?<!\d)\d{1,4}\s*期)")


TAIL_ACTION_PATTERN = r"(?:绝\s*杀|精准\s*杀|稳\s*杀|狠\s*杀|主\s*杀|课\s*杀|杀\s*掉|禁|杀)"


USER_FEED_TAIL_RE = re.compile(
    rf"(?<!\d)(\d{{1,4}})\s*期\s*[:：]?\s*(?:x\s*)?{TAIL_ACTION_PATTERN}?\s*(?:一个|一|①|1)?\s*尾\s*[:：=]*\s*[\[\(【《]?\s*(\d{{1,3}})\s*(?:尾\s*[\]\)】》]?|[\]\)】》]?\s*)\s*开",
    re.S,
)


TAIL_PATTERNS = (
    re.compile(rf"{TAIL_ACTION_PATTERN}\s*(?:一|①|1|一个)?\s*尾[^\d]{{0,6}}(\d{{1,3}})", re.S),
    re.compile(rf"{TAIL_ACTION_PATTERN}\s*(?:一|①|1|一个)?\s*[:：]?\s*[\u3010\[\u300a\(\uff08]?\s*(\d{{1,3}})\s*[\u3011\]\u300b\)\uff09]?\s*尾", re.S),
    re.compile(rf"{TAIL_ACTION_PATTERN}\s*(?:一|①|1|一个)?\s*尾\s*[\u3010\[\u300a\(\uff08]?\s*(\d{{1,3}})\s*[\u3011\]\u300b\)\uff09]?", re.S),
    re.compile(rf"{TAIL_ACTION_PATTERN}\s*(?:一|①|1|一个)?\s*尾\s*[:：=]\s*(\d{{1,3}})", re.S),
    re.compile(r"(?:绝|精)\s*(?:一|①|1)\s*尾[^\d]{0,6}(\d{1,3})", re.S),
    re.compile(r"(?:绝|精)\s*(?:一|①|1)\s*[:：]?\s*[\u3010\[\u300a\(\uff08]?\s*(\d{1,3})\s*[\u3011\]\u300b\)\uff09]?\s*尾", re.S),
)


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


FORUM_API_BASES = (
    "https://tk.118tapi3.com:8443",
    "https://api.118tapi1.com:8443",
    "https://api.118tapi2.com:8443",
)


CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


TWO_TAIL_SITE_PARSERS = {
    "强烈招牌": "qvuu_qiangli_zhaopai_two_tail",
    "华丽恶梦": "qvuu_huali_emeng_two_tail",
    "专注凯子": "qvuu_zhuanzhu_kaizi_two_tail",
    "唯一火势": "qvuu_weiyi_huoshi_two_tail",
}


QVUU_TWO_TAIL_PROFILE_TOPICS = {
    "qvuu_qiangli_zhaopai_two_tail": "精杀二尾",
    "qvuu_huali_emeng_two_tail": "【稳杀二尾】",
    "qvuu_zhuanzhu_kaizi_two_tail": "精杀二尾",
    "qvuu_weiyi_huoshi_two_tail": "精杀两尾",
}


QVUU_TWO_TAIL_PATTERNS = {
    "qvuu_qiangli_zhaopai_two_tail": re.compile(
        r"精\s*杀\s*二\s*尾\s*专区\s*(\d)\s*[.．]\s*(\d)\s*尾\s*开"
    ),
    "qvuu_huali_emeng_two_tail": re.compile(
        r"绝\s*杀\s*二\s*尾\s*\[\s*(\d)\s*尾\s*(\d)\s*尾\s*\]\s*开"
    ),
    "qvuu_zhuanzhu_kaizi_two_tail": re.compile(
        r"精\s*杀\s*二\s*尾\s*专区\s*[◆◇]\s*(\d)\s*[.．]\s*(\d)\s*尾\s*开"
    ),
    "qvuu_weiyi_huoshi_two_tail": re.compile(
        r"\[\s*精\s*杀\s*二\s*尾\s*\]\s*[◆◇]\s*(\d)\s*[.．]\s*(\d)\s*尾\s*开"
    ),
}


TWO_TAIL_SITE_URLS = frozenset({
    "https://qvuuqqs.8imf7-hteuh-ylwuqv.xyz/#/users/1203",
    "https://qvuuqqs.8imf7-hteuh-ylwuqv.xyz/#/users/3753",
    "https://qvuuqqs.8imf7-hteuh-ylwuqv.xyz/#/users/46140",
    "https://qvuuqqs.8imf7-hteuh-ylwuqv.xyz/#/users/5976",
    "https://sxapnxtw.w9lkt-9vch6-idlact.work:17477/topic/470055.html",
    "https://sxapnxtw.w9lkt-9vch6-idlact.work:17477/",
    "https://ykeejph.z9koz-18xjn-pvglgy.xyz:16677/topic/677675.html",
    "https://ykeejph.z9koz-18xjn-pvglgy.xyz:16677/topic/682113.html",
    "https://ykeejph.z9koz-18xjn-pvglgy.xyz:16677/topic/682100.html",
    "https://4.48kk49.com:1888/Article/ar_content/id/1469/tid/82.html",
    "https://4.48kk49.com:1888/Article/ar_content/id/1452/tid/82.html",
    "https://aa.373785d.com:1888/",
    "https://aszmkf.c3z3l-qrlqm-mwgccr.work:29411/article/lottery/6a082c7108adb5ed7357ef3b?url=lhw",
    "https://aszmkf.c3z3l-qrlqm-mwgccr.work:29411/article/lottery/6a083d1308adb5ed7357f036?url=lhw",
    "https://knfoaep.ivqs8-1depw-yoirtw.xyz:29444/article/lottery/6a09527a291caff3edcb8a33?url=lf",
    "https://0130190827.673454.xyz/bbs/topic.php?id=20144",
    "https://67806780827.234535.xyz/bbs/topic.php?id=22163",
    "https://88888020827.833567.xyz/bbs/topic.php?id=22608",
    "https://88888020827.833567.xyz/bbs/topic.php?id=20522",
    "https://0130190827.657954.xyz/bbs/topic.php?id=20210",
    "https://jtrmhar.cwdc3-r5vqn-qzqasa.work:17455/topic/741190.html",
})


LIUXUAN_SITE_URL = "https://lx11.www87127b.com:8443/#87127"
