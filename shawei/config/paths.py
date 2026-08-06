from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_SERIES_DIR = ROOT_DIR.parent
OUTPUT_DIR = DATA_SERIES_DIR / "七类数据统一归纳"
FAIL_OUTPUT_DIR = DATA_SERIES_DIR / "七类数据统一归纳失败"
SITES_CSV_PATH = ROOT_DIR / "sites.csv"
SITES_JSON_PATH = ROOT_DIR / "sites.json"
RECENT_CACHE_PATH = ROOT_DIR / "recent_10_cache.json"
SITE_HEALTH_PATH = ROOT_DIR / "shawei_site_health.json"
