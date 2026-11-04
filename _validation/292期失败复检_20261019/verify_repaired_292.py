"""只验证原失败名单中已修复两站292期；不写正式输出或缓存。"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shawei.config.sites import load_sites
from shawei.services.crawl_site import crawl_current_site
from shawei_failed_site_recheck import _targets

out = Path(__file__).resolve().parent
sites = load_sites()
original = _targets(out / "before" / "292期-尾-失败.txt", 292, sites)
expected = {"小明哥上": "7", "可见一斑": "3"}
selected = [site for site in original if site.name in expected]
assert len(selected) == 2
results = []
for site in selected:
    result = crawl_current_site(sites.index(site) + 1, len(sites), site, 292, 15, retries=1)
    results.append({"site": asdict(site), "result": asdict(result)})
    (out / "repaired_live_292.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(site.name, result.success_line or result.fail_line, flush=True)
assert all(row["result"]["ranking_value"] == expected[row["site"]["name"]] for row in results)
