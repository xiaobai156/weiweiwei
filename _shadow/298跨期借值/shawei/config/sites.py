from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from shawei.config.paths import SITES_JSON_PATH
from shawei.domain.models import SiteConfig
from shawei.domain.text import canonical_pick


def load_site_rows(
    path: Path = SITES_JSON_PATH,
) -> list[tuple[str, str, str]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list) or not data:
        raise ValueError("正式站点配置必须是非空JSON数组")

    rows: list[tuple[str, str, str]] = []
    active_names: set[str] = set()
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"正式站点配置第{index}项不是对象")
        if "pick" not in item or not str(item.get("pick") or "").strip():
            raise ValueError(f"正式站点配置第{index}项缺少明确方向")
        if "archived" in item and not isinstance(item["archived"], bool):
            raise ValueError(f"正式站点配置第{index}项 archived 必须是布尔值")
        name = str(item.get("name") or "").strip()
        url = str(item.get("url") or "").strip()
        pick = canonical_pick(str(item["pick"]).strip())
        parsed = urlparse(url)
        if not name or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"正式站点配置第{index}项缺少有效名称或URL")
        if item.get("archived"):
            continue
        if name in active_names:
            raise ValueError(f"正式站点配置存在活动重名: {name}")
        active_names.add(name)
        rows.append((name, url, pick))

    if not rows:
        raise ValueError("正式站点配置没有活动站点")
    return rows


def load_sites(path: Path = SITES_JSON_PATH) -> list[SiteConfig]:
    return [SiteConfig(name, url, pick) for name, url, pick in load_site_rows(path)]
