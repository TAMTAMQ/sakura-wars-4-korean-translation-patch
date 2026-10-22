"""직접 읽은 고정 목록 범위에 한해 판정·교정을 기록한다. 자동 검수 도구가 아니다."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dialogue import load
from apply_dialogue_review import apply

def commit(start,end,edits,exceptions=None):
    entries=json.loads((ROOT/'work/qa/dialogue/single-review.json').read_text(encoding='utf-8'))
    catalogue,_,_=load();reviews={};plan={}
    for i in range(start,end):
        key=entries[i]['unit']
        reviews[key]={'status':'approved','note':'일본어 원문과 현재 한국어 문안을 읽고 인접 장면, 문장 의미·말투·관용 표현을 대조. 현 문안 유지.'}
    for i,(text,reason) in edits.items():
        key=entries[i]['unit']
        assert catalogue.text(key)!=text,(i,'무변경 계획')
        plan[key]={'text':text,'reason':reason}
    for i,decision in (exceptions or {}).items():reviews[entries[i]['unit']]=decision
    label=f'20261022-dialogue-finish-{start:05d}-{end:05d}'
    apply(label,plan,reviews)
    (ROOT/'assets/translation/review'/label/'read-range.json').write_text(json.dumps({'list':'work/qa/dialogue/single-review.json','start_inclusive':start,'end_exclusive':end,'method':'원문·현재 번역 직접 독해','edits':edits,'exceptions':exceptions or {}},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
