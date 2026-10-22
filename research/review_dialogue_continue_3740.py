"""고정 목록 3740–4139번의 원문 대조 결과."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from apply_dialogue_review import apply
from dialogue import load

def main():
    entries=json.loads((ROOT/'work/qa/dialogue/single-review.json').read_text(encoding='utf-8'))
    current,_,_=load();plan={}
    def edit(i,text,reason):plan[entries[i]['unit']]={'text':text,'reason':reason}
    edit(3774,'다음에는 우리가，//파리에 놀러 갈 거야∈//꼭 갈 거야∈','이별하면서 미래 방문을 약속하는 今度를 다음에로 교정')
    edit(4005,'오오가미 씨，//잠깐만…괜찮나？','시간을 잠시 내 달라는 홍란의 요청을 의미가 드러나게 표현')
    edit(4010,'울적한 건//별로 안 좋아하니까…//이런 기 낫겠제．','이별 장면의 しめっぽい는 물리적으로 축축하다는 뜻이 아닌 침울한 분위기')
    edit(4061,'뭐든 좋으니，//맹세해 주지 않으면//어엿한 수녀가 못 된다니까요．','一人前になる는 일의 몫을 다한다는 뜻이 아닌 어엿한 수녀가 된다는 뜻')
    edit(4114,'깨끗한 몸이…//되고 싶잖아．//그러니까…말이야．','되어 두고 싶다는 일본어 보조동사 직역 자연화')
    edit(4118,'내 몸매는，//전에 만났을 때부터，//변하지 않았어．','같은 화자의 앞선 プロポーション 교정과 몸매 표기 통일')
    reviews={}
    for i in range(3740,4140):
        entry=entries[i];key=entry['unit']
        if current.text(key)!=entry['text'] and key not in plan:continue
        reviews[key]={'status':'approved','note':'이별·개인 결말의 원문과 번역을 읽고 인물 관계, 미래 시점, 관용구의 의미를 대조. 현 문안 유지.'}
        if i==4083:reviews[key]={'status':'needs_source','note':'원문 心の￢의 깨진 글자 확인이 필요. 현 번역 유대는 유지하되 원문 복호화 근거 확인 전 합격 처리하지 않음.'}
    apply('20261022-dialogue-continue-3740',plan,reviews)

if __name__=='__main__':main()
