"""고정 목록 4140–4539번의 원문 독해·검수 결과."""
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
    edit(4149,'그만하세요，오리히메 씨．//오오가미 씨도//곤란해하는 것 같고…','곤란한 사람에게 그만 추궁하자는 いいじゃないですか를 괜찮잖아요로 옮긴 화행 교정')
    edit(4156,'알려 주세요，오오가미 씨∈//말해도 닳는 건 아니잖아요∈','減るもんでもない는 말해도 손해 없다는 뜻. 무엇이 닳는지 불명확한 직역 보완')
    edit(4216,'뭐，연례행사나//마찬가지예요～．//그냥 두는 게 좋아요～．','恒例行事 같은 다툼이라는 농담을 한국어 구어로 자연화')
    edit(4223,'뭐，그렇긴 하지．//스미레 따위를 상대해 줄 만큼//나도 한가하진 않으니까 말이야．','사람을 상대한다는 말에서 스미레 같은 애랑 상대하다는 조사 오류 교정')
    edit(4322,'마리아군요．//그녀가 그랬다니…//믿기지 않네요．','떼를 썼다는 말에 놀라는 대사를 그런 짓이라는 과도한 비난 표현에서 자연화')
    edit(4433,'아아，약속할게．//다음엔 같이 가자．','헤어진 이후 또 떠날 때 동행하자는 今度의 미래 방문 의미 반영')
    edit(4515,'하지만…대장．//내가 무언가에 막혀서，//멈춰 서게 됐을 때는…','인생에서 어려움을 겪는다는 つまづく를 걸려 넘어지다라는 물리적 동작 중심의 직역에서 자연화')
    reviews={}
    for i in range(4140,4540):
        entry=entries[i];key=entry['unit']
        if current.text(key)!=entry['text'] and key not in plan:continue
        if 4174<=i<4221:continue # 별도 보관 원문 복원 배치에서 이미 원문과 문안을 대조해 판정함
        reviews[key]={'status':'approved','note':'원문·번역을 읽고 인접 대화와 대답의 방향, 인물별 말투, 관용 표현을 대조. 현 문안 유지.'}
    apply('20261022-dialogue-continue-4140',plan,reviews)

if __name__=='__main__':main()
