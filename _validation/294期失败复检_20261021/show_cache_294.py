import json
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\每天工具\爬虫合集\杀尾-修复版2")
cache = json.loads((ROOT / "recent_10_cache.json").read_text(encoding="utf-8-sig"))
targets = [
    "坚持战斗", "无量寿佛", "再度归来", "童颜鹤发", "一心为民",
    "怪咖小生", "澳彩碼王", "寻宝探码", "财源滚滚", "海角天涯", "昙花一现",
]
for item in cache["sites"]:
    if item["name"] in targets:
        print(
            f"{item['name']:6s} periods={item['periods'][:4]} "
            f"values={item['values'][:4]} failed={item.get('failed_periods')}"
        )
print("cache period", cache["period"], "site_count", cache["site_count"])
