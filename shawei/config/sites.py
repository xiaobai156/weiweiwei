from __future__ import annotations

import csv
import json
import sys
from collections.abc import Iterable
from pathlib import Path

from shawei.config.paths import SITES_CSV_PATH, SITES_JSON_PATH
from shawei.domain.models import SiteConfig
from shawei.domain.text import canonical_pick


def load_site_rows(
    default_rows: Iterable[tuple[str, str, str]],
    path: Path = SITES_JSON_PATH,
) -> list[tuple[str, str, str]]:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            rows = []
            for item in data:
                if not isinstance(item, dict) or item.get("archived"):
                    continue
                name = str(item.get("name") or "").strip()
                url = str(item.get("url") or "").strip()
                pick = canonical_pick(str(item.get("pick") or "top").strip())
                if name and url:
                    rows.append((name, url, pick))
            if rows:
                return rows
        except json.JSONDecodeError as exc:
            print(f"JSON站点表读取失败: {exc}", file=sys.stderr)
        except ValueError:
            raise
        except Exception as exc:
            print(f"JSON站点表读取失败: {exc}", file=sys.stderr)

    if SITES_CSV_PATH.exists():
        try:
            with SITES_CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
                rows = [
                    (
                        str(row.get("name") or "").strip(),
                        str(row.get("url") or "").strip(),
                        canonical_pick(str(row.get("pick") or "top").strip()),
                    )
                    for row in csv.DictReader(file)
                ]
            rows = [row for row in rows if row[0] and row[1]]
            if rows:
                return rows
        except ValueError:
            raise
        except Exception as exc:
            print(f"CSV站点表读取失败: {exc}", file=sys.stderr)
    return [
        (name, url, canonical_pick(pick))
        for name, url, pick in default_rows
    ]


def load_sites(path: Path = SITES_JSON_PATH) -> list[SiteConfig]:
    return [SiteConfig(name, url, pick) for name, url, pick in load_site_rows((), path)]
