"""별도 잔여 목록의 원문·모든 변형 조회 및 직접 읽은 범위 판정 기록."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dialogue import load
from apply_dialogue_review import apply

def entries():
    return json.loads((ROOT/'work/qa/dialogue/final-review.json').read_text(encoding='utf-8'))

def show(start,end):
    c,r,_=load();e=entries()
    for i in range(start,end):
        u=c.units[e[i]['unit']]
        texts=[f+': '+c.text(u['id'],f) for f in ['default']+list(u.get('variants',{}))]
        print(i,u['source'],'=>',' | '.join(texts),'@',','.join(o['id'] for o in u['occurrences'][:2]))

def commit(start,end,edits=None,notes=None):
    e=entries();plan={};reviews={};edits=edits or {};notes=notes or {}
    for i in range(start,end):
        reviews[e[i]['unit']]={'status':'approved','note':notes.get(i,'원문과 모든 사용 문안을 직접 읽고 의미·말투·사용처를 대조. 문맥 또는 고정 용량에 필요한 변형은 유지하며 현 문안 확정.')}
    for i,(t,reason) in edits.items():plan[e[i]['unit']]={'text':t,'reason':reason}
    label=f'20261022-dialogue-final-{start:05d}-{end:05d}'
    apply(label,plan,reviews)
    (ROOT/'assets/translation/review'/label/'read-range.json').write_text(json.dumps({'list':'work/qa/dialogue/final-review.json','start_inclusive':start,'end_exclusive':end,'method':'원문과 모든 변형 직접 독해','edits':edits,'notes':notes},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':show(int(sys.argv[1]),int(sys.argv[2]))
