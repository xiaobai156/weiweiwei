import sys,json,hashlib
from pathlib import Path
from dataclasses import replace,asdict
ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
from shawei.config import rules
from shawei.domain.models import Document,SiteConfig
from shawei.validation.validator import validate_documents
from shawei.services.crawl_site import crawl_current_site
OUT=ROOT/'_validation/292期失败复检_20261019'
OLD='https://zdwcig.iyo4d-81klf-udwkqg.work:16677/topic/350485.html'
NEW='https://bbjkbgbw.rqzf2-shxqn-jtrsyy.work:17488/topic/350485.html'
paths=[ROOT/'sites.json',ROOT/'recent_10_cache.json',ROOT.parent/'七类数据统一归纳/292期-尾.txt',ROOT.parent/'七类数据统一归纳失败/292期-尾-失败.txt']
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
data=json.loads((OUT/'mirror_guli_browser.json').read_text(encoding='utf8'))
rule=replace(rules.effective_rule_for(OLD,'故里春意'),site_url=NEW)
rules.STRICT_SITE_RULES[NEW]=rules.STRICT_SITE_RULES[OLD]
rules.SAME_PERIOD_RECORD_SELECTION_URLS=rules.SAME_PERIOD_RECORD_SELECTION_URLS | {NEW}
doc=Document(NEW,data['html'],'browser',record_id='350485',document_id='mirror-browser-350485')
result=validate_documents([doc],'故里春意',pick='bottom',rule=rule,target_period=292)
assert len(result.records)==1 and result.records[0].period==292 and result.records[0].value()=='0',result
checks={}
for label,pick,period in [('adjacent','bottom',291),('missing','bottom',999),('direction','top',292)]:
    try: validate_documents([doc],'故里春意',pick=pick,rule=rule,target_period=period)
    except LookupError as exc: checks[label]=str(exc)
    else: raise AssertionError(label+' should fail')
live=crawl_current_site(1,1,SiteConfig('故里春意',NEW,'bottom'),292,15,retries=0)
report={'old_url':OLD,'mirror_url':NEW,'browser_decision':asdict(result),'negative_checks':checks,'live_result':asdict(live),'formal_before':before}
(OUT/'mirror_guli_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},'正式文件意外变化'
print(json.dumps({'browser':asdict(result.records[0]),'checks':checks,'live':asdict(live)},ensure_ascii=False,indent=2),flush=True)
assert live.success_line=='0尾 故里春意' and live.ranking_value=='0'
