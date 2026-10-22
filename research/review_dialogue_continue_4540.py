"""고정 목록 4540–4939번의 실제 원문 대조 검수."""
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
    edit(4563,'확실히 짜증 나는 녀석이지만，//스미레가 그렇게 말하니，//오히려 내가 더 화가 나는데∈','奴는 작품 속 특정 인물을 가리키므로 근거 없는 복수 녀석들 교정')
    edit(4582,'오케이예～요∈//저한테//전부 맡기면 돼～요．','このわたしを 이 몸한테로 옮긴 한국어 존대의 부자연스러운 인칭 자연화')
    edit(4615,'굳이 불쾌한 것을//테마로 삼을 필요는//없겠지．','카에데가 오오가미에게 하던 반말에서 갑자기 바뀐 존댓말 어미 교정')
    edit(4722,'끈기를 가져라，홍란∈','낫토의 ネバネバ와 ネバーギブアップ 말장난을 끈적함과 끈기로 한국어화. 뒤 설명 대사와 함께 교정')
    edit(4748,'끈기를 가져라，홍란∈//힘내∈','같은 낫토 말장난의 음성 없는 확장 대사도 공통 뜻과 함께 현지화')
    edit(4750,'낫토는 끈적하고…//홍란은 끈기 있게∈//역시 오오가미 씨다∈','한국어로 성립하지 않던 일본어 발음 유사 농담을 끈적함·끈기로 현지화. 앞의 포기하지 말라는 격려 유지')
    edit(4868,'정말이지…//중위님은 참 말도 잘하시네요．','調子がいい는 상황에 맞게 말을 바꾸며 부탁을 떠넘기는 태도에 대한 핀잔. 속 편하다는 오역 교정')
    edit(4869,'하지만…오케이예요∈//제가，//음악 감독을 해 드릴게요～∈','このわたし를 이 제가라는 부자연스러운 대명사 결합에서 자연화')
    edit(4909,'아아，그렇구나．//벌써 늦었으니까，어서//방으로 돌아가．','늦은 시각에 早めに戻る라는 말을 일찍 돌아가라는 시간 모순에서 어서로 교정')
    edit(4937,'스미레 씨，생각이 많네요．//긍정적으로//생각해～요∈','ポジティブシンキングでいく를 긍정적으로 가다라는 직역에서 자연화')
    reviews={}
    for i in range(4540,4940):
        entry=entries[i];key=entry['unit']
        if current.text(key)!=entry['text'] and key not in plan:continue
        if 4598<=i<4620 and key not in plan:continue
        reviews[key]={'status':'approved','note':'원문과 번역을 읽고 공연 준비·순찰 장면, 어휘 의미, 말장난의 전달 가능성을 대조. 현 문안 유지.'}
    apply('20261022-dialogue-continue-4540',plan,reviews)

if __name__=='__main__':main()
