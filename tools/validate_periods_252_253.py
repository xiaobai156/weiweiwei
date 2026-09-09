from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from shawei.config.sites import load_sites
from shawei.fetch.http_client import clear_fetch_cache
from shawei.services.crawl_site import crawl_current_site

PERIODS = (253, 252)
TIMEOUT = 12
RETRIES = 1
MAX_WORKERS = 4
REPORT_PATH = Path("periods_252_253_report.json")
PRINT_LOCK = threading.Lock()


def _attempt(index: int, total: int, site, period: int) -> dict:
    clear_fetch_cache(site.url)
    result = crawl_current_site(
        index,
        total,
        site,
        period,
        TIMEOUT,
        retries=RETRIES,
    )
    return {
        "period": period,
        "ok": result.fail_line is None and result.ranking_value is not None,
        "value": result.ranking_value,
        "success_line": result.success_line,
        "fail_line": result.fail_line,
        "failure_stage": result.failure_stage,
        "failure_reason": result.failure_reason,
        "messages": list(result.messages),
    }


def _validate_site(index: int, total: int, site) -> dict:
    attempts: list[dict] = []
    hit = None
    for period in PERIODS:
        attempt = _attempt(index, total, site, period)
        attempts.append(attempt)
        if attempt["ok"]:
            hit = attempt
            break

    row = {
        "index": index,
        "name": site.name,
        "url": site.url,
        "pick": site.pick,
        "success": hit is not None,
        "hit_period": hit["period"] if hit else None,
        "value": hit["value"] if hit else None,
        "attempts": attempts,
    }
    with PRINT_LOCK:
        if hit:
            print(
                f"PASS {index}/{total} {site.name} {site.pick} "
                f"{hit['period']}期={hit['value']}",
                flush=True,
            )
        else:
            reasons = " | ".join(
                f"{item['period']}期:{item['failure_reason'] or item['fail_line'] or '未知失败'}"
                for item in attempts
            )
            print(
                f"FAIL {index}/{total} {site.name} {site.pick} {reasons}",
                flush=True,
            )
    return row


def main() -> int:
    sites = load_sites()
    total = len(sites)
    rows: list[dict] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(_validate_site, index, total, site): index
            for index, site in enumerate(sites, start=1)
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                site = sites[index - 1]
                rows.append(
                    {
                        "index": index,
                        "name": site.name,
                        "url": site.url,
                        "pick": site.pick,
                        "success": False,
                        "hit_period": None,
                        "value": None,
                        "attempts": [],
                        "runner_error": f"{type(exc).__name__}: {exc}",
                    }
                )
                with PRINT_LOCK:
                    print(
                        f"ERROR {index}/{total} {site.name} {site.pick} "
                        f"{type(exc).__name__}: {exc}",
                        flush=True,
                    )

    rows.sort(key=lambda item: item["index"])
    passed = sum(1 for row in rows if row["success"])
    failed = total - passed
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rule": "保持每站配置pick；253或252任意一期正确命中即成功；两期都失败才失败",
        "periods": list(PERIODS),
        "timeout": TIMEOUT,
        "retries": RETRIES,
        "max_workers": MAX_WORKERS,
        "total": total,
        "passed": passed,
        "failed": failed,
        "results": rows,
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"SUMMARY total={total} passed={passed} failed={failed}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
