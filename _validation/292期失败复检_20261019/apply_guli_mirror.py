"""One verified mirror, one current-period update; never a full crawl."""
import copy
import hashlib
import json
import sys
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shawei.config import rules
from shawei.domain.models import SiteConfig
from shawei.persistence import cache_repository, txt_writer
from shawei.persistence.atomic_file import file_lock, _atomic_write_text_unlocked
from shawei.services.crawl_site import crawl_current_site
from shawei_failed_site_recheck import _failure_blocks, _read_existing_successes_strict, FAIL_RE

OUT = Path(__file__).resolve().parent
OLD = 'https://zdwcig.iyo4d-81klf-udwkqg.work:16677/topic/350485.html'
NEW = 'https://bbjkbgbw.rqzf2-shxqn-jtrsyy.work:17488/topic/350485.html'
NAME = '故里春意'
CONFIG = ROOT / 'sites.json'
CACHE = ROOT / 'recent_10_cache.json'
SUCCESS = ROOT.parent / '七类数据统一归纳/292期-尾.txt'
FAILURE = ROOT.parent / '七类数据统一归纳失败/292期-尾-失败.txt'
paths = [CONFIG, SUCCESS, FAILURE, CACHE]
raw = {p: p.read_bytes() for p in paths}
digest = lambda b: hashlib.sha256(b).hexdigest()
before_hash = {str(p): digest(b) for p, b in raw.items()}
assert before_hash[str(CONFIG)] == '87225e85b4887fdae987716ede576e9a142f4b90ed3c6defa427906296ad831d'
assert before_hash[str(CACHE)] == '1581c2f5c75676bc8eaf26ab7aa44cb49dd382f1dc8864bea0c047127412724f'
config_text = raw[CONFIG].decode('utf-8-sig')
assert config_text.count(OLD) == 1 and NEW not in config_text
old_config = json.loads(config_text)
new_config = json.loads(config_text.replace(OLD, NEW))
index = next(i for i, s in enumerate(old_config) if s['name'] == NAME)
assert old_config[index] == dict(new_config[index], url=OLD)
assert old_config[index]['pick'] == 'bottom'
assert all(a == b for i, (a, b) in enumerate(zip(old_config, new_config)) if i != index)
sites = [SiteConfig(**s) for s in new_config]
assert rules.effective_rule_for(NEW, NAME).dedicated_parser == 'gulichunyi_topic_tail'
live = crawl_current_site(index + 1, len(sites), sites[index], 292, 15, retries=0)
assert live.success_line == '0尾 故里春意' and live.ranking_value == '0' and live.fail_line is None, live
old_success = _read_existing_successes_strict(SUCCESS)
assert len(old_success) == 261 and NAME not in old_success
success = dict(old_success)
success[NAME] = (live.success_line, live.ranking_value)
success_text = '\n'.join(txt_writer.format_ranking([v[0] for v in success.values()], [v[1] for v in success.values()])) + '\n'
blocks = _failure_blocks(FAILURE)
assert len(blocks) == 9
def target(block):
    m = FAIL_RE.match(block.splitlines()[0])
    return bool(m and (m['name'], m['url'], m['pick'], int(m['period'])) == (NAME, OLD, 'bottom', 292))
assert sum(map(target, blocks)) == 1
kept = [b for b in blocks if not target(b)]
failure_text = txt_writer.format_failure_records(kept)
old_cache = json.loads(raw[CACHE].decode('utf-8-sig'))
cache = copy.deepcopy(old_cache)
items = [s for s in cache['sites'] if s['name'] == NAME and s['url'] == OLD and s['pick'] == 'bottom']
assert len(items) == 1 and not items[0].get('archived')
items[0]['url'] = NEW
cache['fail_lines'] = [line.replace(OLD, NEW) if line.startswith('失败 '+NAME+' '+OLD+' 方向: bottom ') else line for line in cache['fail_lines']]
cache['config_fingerprint'] = cache_repository.configuration_fingerprint(sites)
candidate = OUT / 'mirror_guli_cache_candidate.json'
candidate.write_text(json.dumps(cache, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
assert cache_repository.update_recent_cache_for_targeted_sites(candidate, 292, sites, [live])
new_cache = json.loads(candidate.read_text(encoding='utf-8'))
changed = [(a, b) for a, b in zip(old_cache['sites'], new_cache['sites']) if a != b]
assert len(old_cache['sites']) == len(new_cache['sites']) and len(changed) == 1
a, b = changed[0]
assert a['name'] == b['name'] == NAME and a['url'] == OLD and b['url'] == NEW
history = lambda s: {p: v for p, v in zip(s['periods'], s['values']) if p != 292}
assert history(a) == history(b)
assert dict(zip(b['periods'], b['values']))[292] == '0'
assert 292 not in b.get('failed_periods', []) and '292' not in b.get('failure_reasons', {})
assert {p: v for p, v in a.get('failure_reasons', {}).items() if p != '292'} == b.get('failure_reasons', {})
mutable = {'url', 'periods', 'values', 'extended', 'failed_periods', 'failure_reasons'}
assert {k:v for k,v in a.items() if k not in mutable} == {k:v for k,v in b.items() if k not in mutable}
assert new_cache['fail_lines'] == [b.splitlines()[0] for b in kept]
root_mutable = {'sites','config_fingerprint','generated_at','vector_count','fail_count','fail_lines'}
assert {k:v for k,v in old_cache.items() if k not in root_mutable} == {k:v for k,v in new_cache.items() if k not in root_mutable}
snap = OUT / 'before_guli_mirror'
snap.mkdir(exist_ok=True)
for p, content in raw.items():
    (snap / p.name).write_bytes(content)
prepared = {CONFIG:(config_text.replace(OLD,NEW),'utf-8'), SUCCESS:(success_text,'utf-8-sig'), FAILURE:(failure_text,'utf-8-sig'), CACHE:(candidate.read_text(encoding='utf-8'),'utf-8')}
with ExitStack() as stack:
    for p in sorted(paths, key=str): stack.enter_context(file_lock(p))
    assert all(p.read_bytes() == raw[p] for p in paths), '正式文件已变化，拒绝覆盖'
    for p in paths:
        text, encoding = prepared[p]
        _atomic_write_text_unlocked(p, text, encoding)
assert len(_read_existing_successes_strict(SUCCESS)) == 262
assert list(_read_existing_successes_strict(SUCCESS).items())[:-1] == list(old_success.items())
assert _failure_blocks(FAILURE) == kept and len(kept) == 8
assert json.loads(CACHE.read_text(encoding='utf-8')) == new_cache
assert json.loads(CONFIG.read_text(encoding='utf-8')) == new_config
report = {'period':292, 'site':NAME, 'old_url':OLD, 'mirror_url':NEW, 'live_result':asdict(live), 'success_count':262, 'failure_count':8, 'only_changed_cache_site':NAME, 'history_preserved':True, 'other_success_rows_and_order_preserved':True, 'other_cache_entries_preserved':True, 'before_sha256':before_hash, 'after_sha256':{str(p):digest(p.read_bytes()) for p in paths}}
(OUT/'mirror_guli_formal_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
