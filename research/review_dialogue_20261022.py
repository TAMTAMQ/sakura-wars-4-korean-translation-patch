"""읽고 대조한 문안의 명시적 교정안만 적용한다. 자동 번역/일괄 문체 치환을 하지 않는다."""
import copy
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from dialogue import Catalogue, digest, load, read_jsonl
from build import encode


def run():
    catalogue, rows, hashes = load()
    focus = json.loads((ROOT / 'work/qa/dialogue/variant-focus.json').read_text(encoding='utf-8'))
    plan = {}

    def change(key, text, reason):
        assert key not in plan, key
        plan[key] = {'text': text, 'reason': reason}

    def edit(i, text, reason):
        change(focus[i]['unit'], text, reason)

    def choose(i, n, reason):
        edit(i, focus[i]['texts'][n], reason)

    edit(6, '하나비인가…//그 아이는 얌전해 보여도，//심지가 굳으니까 말이야．', '静かな中にも芯の強さ: 조용한 성격과 굳은 심지를 자연스럽게 표현')
    choose(26, 1, '본인에게도 낯설었던 감정이라는 의미 복원')
    choose(27, 1, 'サポート를 지원으로 표현하고 대장 지원 제안이라는 의미 보존')
    change('dialogue:06c3160bdb7aacef', '오빠，축하해．//아이리스도 열심히 할 테니까，//오빠도 힘내．', '축하와 격려 문장: 의문형으로 바뀐 음성 대응 번역 교정')
    edit(48, '대장님…괜찮으신가요？//지금 홍란이 냉정한 판단을//내릴 수 있을 것 같지 않습니다．', '일본어 명사화 구문을 자연스러운 한국어로 표현')
    edit(49, '대장，데려가 줘．//홍란이 저렇게까지 말하잖아．//…알겠지？', 'ここまで言う의 정도 의미: 장소처럼 들리는 여기까지 교정')
    edit(59, '…좋은 장면이군요．//하지만…올바른 길을 가르치며//물건으로 꾀는 건 좀 그렇네요．', 'どうかと: 물건으로 회유하는 것에 대한 비판을 제안형으로 옮긴 오역 교정')
    change('dialogue:e85798a4626c3846', '나는 도쿄에 왔다．//귀공을 데리러 말이다．//대장…생각해 보았나？', '迎えに: 찾아와 데려가려는 상황으로, 맞이하러 왔다는 오역 교정')
    change('dialogue:8fd169634855feec', '결투를 받아들일 수 없다면，//내 사위가 되겠다고 맹세해라∈//자，어느 쪽을 택할 테냐∈', '바로 앞 결투 신청 문맥 확인. 私のムコ는 여성 화자의 남편이므로 사위는 부적절')
    # 글리신은 여성이므로 私のムコ의 자연스러운 표현은 나와 결혼하는 것.
    plan['dialogue:8fd169634855feec']['text'] = '결투를 받아들일 수 없다면，//나와 결혼할 것을 맹세해라∈//자，어느 쪽을 택할 테냐∈'
    choose(103, 1, '積もる話를 못다 한 이야기로 자연스럽게 표현')
    choose(108, 1, '자기만의 원칙을 저버린다는 의미를 자연스럽게 표현')
    choose(109, 1, '레이더 화면에 긴자만 흐릿하게 나온다는 관측 보고 표현')
    choose(110, 1, '鎮める를 원령을 달래다로 표현')
    choose(115, 1, '멜이 동료 시에게 말하는 장면의 친구 사이 말투 유지')
    choose(117, 1, '부부 역할 장면의 あなた를 여보로 현지화')
    choose(121, 1, '보는 내가 부끄럽다는 관용 표현 자연화')
    choose(124, 1, '전후 방 청소 문맥 확인: 옷장에 넣으라는 충고로 통일')
    edit(127, '어쩔 수 없네요．//제가 내일 다시 오도록//말을 잘해 두고 올게요．', 'ノージンジャー는 しょうがない 말장난. 무의미한 노진저 음역 대신 뜻 전달')
    choose(145, 1, 'マジメくさい의 놀리는 어감을 고지식하다로 표현')
    choose(153, 1, '心に決めた方를 마음에 둔 분으로 자연스럽게 표현')
    edit(157, '일본식 방이니까，//「천장 함정」이나//「다다미 뒤집기」도 있겠네요．', 'つり天井는 천장에서 내려오는 함정. 매달린 천장이라는 직역 교정')
    choose(159, 1, 'よろしくて는 여기서 허락 질문이 아닌 상대에게 확인을 요구하는 말')
    edit(160, '남이 들으면 곤란하다고//생각하는 것부터，//찔리는 구석이 있다는 증거예요．', '聞かれて困る의 주체를 명확히 하고 やましい를 자연스럽게 표현')
    choose(161, 1, '開き直る는 잘못을 인정하지 않고 뻔뻔하게 나오는 태도')
    choose(168, 1, '청각을 닫다라는 직역 표현 교정')
    edit(170, '…자기 몸을 해치면서까지，//아이의 행복을//위해 애쓸 가치가 있나？', '親が体を壊す를 부모 자신이 몸을 해치는 의미로 자연화')
    edit(173, '아이의 행복은，//가난해도 부모와 함께 사는 데//있지 않을까요？', '아이의 행복이 부모와 함께 사는 것에 있다는 원문 의미 자연화')
    choose(192, 1, '도와줄 수 있는 일이라는 중첩 구문 간결화')
    choose(193, 1, '何のために働く의 반문 의미를 왜 일하는가로 표현')
    choose(194, 1, 'わかってるじゃないか의 호의적인 반응을 말이 통하네로 표현')
    choose(197, 1, '테이블에 꽃을 장식하라는 동작 표현 자연화')
    choose(198, 1, '불필요한 명사화 교정')
    choose(199, 1, '카야마가 친구 오오가미를 부르는 호칭 유지')
    choose(201, 1, '와사비의 코끝 찡한 느낌을 자연스럽게 표현')
    choose(222, 1, '명령을 들을 수 없다를 따를 수 없다로 교정')
    for i in [224,234,235,294,312,313,324,325,328,333,334,336,338,339,345,346,347,348,349,354,361,365]:
        choose(i, 1, '제도/도쿄 및 대도시를 가리키는 町: 마을로 축소된 번역을 도시로 교정. 각 원문 대조')
    choose(237, 1, '서로 등을 밀어 주자는 제안 구문 자연화')
    choose(249, 1, '두려움받다라는 비문 교정')
    choose(254, 1, '함께하고 싶다고 생각하니까의 중복 완화')
    edit(255, '안 됩니다∈//강력한 방해 전파 때문에，//어떤 통신도 할 수 없습니다∈', '일체 통신이라는 어색한 부사구 교정')
    choose(258, 1, '외벽을 따라 이동한다는 경로 표현 자연화')
    choose(260, 1, '평생 지켜 나가고 싶다는 의사 표현 자연화')
    edit(262, '…생각해 보면，//언제나 오오가미 씨가//저를 지켜 주셨네요．', '振り返る와 守ってくれた의 회고 구문 자연화')
    choose(268, 1, '제국과 파리를 구분할 때가 아니라는 의미를 명확히 전달')
    edit(270, '아무것도 안 하고 죽긴 싫다．//끝까지 발버둥 쳐서，//놈들을 울려 주겠어∈', 'ほえ面をかかせる의 위협 어조를 자연스럽게 전달')
    edit(273, '귀공에게 배웠으니까…//정의를 지키는 데는//제도와 파리를 가릴 게 없다는 걸…', '국가 구분 없이 정의를 지킨다는 뜻을 자연스럽게 표현')
    edit(284, '츠바키∈미카사 낙하 지점 예측과//주변 지역 대피 권고，//바로 처리해 줘∈', '추락하는 전함의 着弾予想: 포탄 착탄으로 읽히는 직역 교정')
    choose(287, 1, '영상 解析를 분석으로 표현')
    choose(301, 1, '해야 할 일을 해야 할 시간이라는 중복 완화')
    choose(315, 1, '잘못에 대한 행동과 책임을 묻는 문장 자연화')
    choose(327, 1, '불필요한 명사화 완화')
    edit(350, '어른에게서 아이에게…//그렇게 생명을 이어 가며，//도시를 만들어 가는 거야．', '생명의 이어짐이라는 직역 명사화와 제도의 마을 표기 교정')
    edit(353, focus[353]['texts'][0].replace('이 마을이', '이 도시가'), '제도는 도시로 교정하되 원문 黙って보다 강한 욕설성 변형은 채택하지 않음')
    choose(358, 1, '하나비의 자기 고백을 자연스러운 존댓말로 표현')
    edit(360, '그건 아니라고 생각합니다．//도시에 성공과 실패가//따로 있는 건 아닐 겁니다．', '도시의 성공/실패를 구분할 수 없다는 논지 자연화')
    edit(362, '굳이 나눈다면，//사랑받는 도시인지 아닌지，//그뿐이지 않을까요？', '구별 기준을 제시하는 원문 구문 자연화')
    choose(370, 1, '抱きしめちゃいましょう의 함께 하자는 권유 의미 복원')
    choose(371, 1, '말을 남겼는가가 아닌 하고 싶은 말을 다 했는가의 의미')
    edit(374, '음…왜 그러세요？//그렇게 웃으시다니…//저，이상한 말이라도 했나요？', '상대 반응을 보고 자기 발언을 되묻는 구문 자연화')
    choose(386, 1, '혼자라고 생각했다는 인용을 이유처럼 옮긴 구문 교정')
    choose(398, 1, '당황한 반응 そんな의 어감 보존')
    edit(400, '친구의 첫 무대를 지켜본다…//남자의 우정은 좋네∈//…좀 땀 냄새 나지만．', '극장 첫 연출 무대 문맥의 初仕事를 첫 무대로 표현')
    edit(402, '오오가미 씨가 그런 표정이면，//화조 대원들도 불안해해요．//자，웃어요，웃어요∈', '표정 때문에 대원도 불안해진다는 문장 자연화')
    choose(405, 1, '失礼しちゃうわ는 상대에게 무례하다고 항의하는 말. 실례하겠다는 미래형 오역 교정')
    choose(410, 1, '대본에 담긴 마음을 연기한다는 문장 자연화')
    edit(413, '나를 놓아주는 게 옳다고//네가 믿는다면，//그건 죄가 아니야∈', '행위가 옳다고 믿는다는 문장을 인물이 정의라고 믿는다는 오역과 구별')
    choose(426, 1, '次回를 뜻하는 今度를 다음에는으로 교정')
    choose(428, 1, '두 사람의 궁합을 말하는 문장 자연화')
    choose(430, 1, '종합 연출을 맡은 사람의 입장에서 하는 발언 자연화')
    choose(436, 1, '이미 함께 여행한 경험을 완료형으로 표현')
    choose(437, 1, '不謹慎의 자책을 경솔했다로 자연스럽게 표현')
    choose(442, 1, 'お礼의 행동을 말로만 한정하지 않고 답례로 표현')
    choose(451, 1, '부대 전체가 一人前라는 말은 어엿한 부대가 되었다는 뜻')
    choose(453, 1, '늘 일손이 부족하다는 상태 표현 자연화')
    choose(455, 1, '여행 후 お疲れでしょう를 피곤하시죠로 표현')
    choose(475, 1, '먼저 말을 꺼내야 하나 고민하는 구문 자연화')
    edit(483, '맞아．//나도 종합 연출을 맡게 됐으니，//긍정적으로 생각해 보려고 해．', '역할을 맡았다는 표현과 前向き의 긍정적 태도 모두 보존')
    edit(491, '저래 보여도…여린 아이예요．//누군가 힘이 되어 주지 않으면，//마음이 무너지고 말 거예요．', '정서적 支える를 물리적인 받쳐 주다에서 힘이 되다로 교정')
    edit(501, '음…뭐，됐어．//급한 용건도 아니고…//다른 방으로 갈까．', '독백의 어색한 종결 됐나 교정')
    choose(504, 1, '일본인과 파리 사람과는의 조사 중복 교정')
    choose(508, 1, '작전 発動時刻를 개시 시각으로 자연스럽게 표현')

    # 위에서 원문/모든 대응 문안을 개별 출력해 읽은 공연 용어 17개.
    for key, unit in catalogue.units.items():
        if 'レビュー' in unit.get('source', ''):
            change(key, catalogue.text(key).replace('리뷰', '레뷰'), '샤노와르의 노래·춤 공연 revue. 비평을 뜻하는 리뷰와 구별하여 레뷰로 표기')

    # 각 사용처의 최소 용량에 맞춰 직접 다듬은 문안. 자동 축약을 하지 않는다.
    fitted = {
        48: '대장님…괜찮으신가요？//지금 홍란이 냉정한 판단을//할 수 있을 것 같지 않습니다．',
        117: '결혼하면…이렇게//「여보」라고//맞이하는 걸까…싶어서요．',
        127: '어쩔 수 없네요．//제가 내일 다시 오도록//말을 해 두고 올게요．',
        145: '저런 고지식한 사람과는，//궁합이 안 맞아서//불편해 죽겠다고．',
        157: '일본식 방이니，//「천장 함정」이나//「다다미 뒤집기」도 있겠네요．',
        161: '뻔뻔하게 나오다니，//일본 남자로서//부끄럽지도 않으신가요？',
        168: '훈련으로 청각을 차단해，//외부 소리를 안 듣는 것도//…가능해．',
        199: '오오가미에게 알려야겠군．//사건도 끝났으니，//필요 없을지도 모르지만…',
        255: '안 됩니다∈//강력한 방해 전파로，//어떤 통신도 할 수 없습니다∈',
        268: '제국도 파리도 따로 없다．//평화를 지켜라∈//오오가미 화격단이여∈',
        273: '귀공에게 배웠으니까…//정의를 지키는 데//제도와 파리를 가릴 게 없다는 걸…',
        287: '그럼…//제도 상공 영상을 보내겠습니다．//분석，부탁드릴까요？',
        294: '제도 사람들은//이 도시를 사랑해요∈//그래서 필사적으로 지키는 거예요∈',
        313: '이 도시를 위해 싸우고…//웃고…울고 있는…//그런 사람들의 거잖아∈',
        315: '아버지도 말씀하셨지…//잘못된 건…//잘못을 바로잡지 않는 거야．',
        333: '무책임하군∈//네놈이 이 도시를 만들었다면，//앞날을 지켜봐라∈',
        336: '도시는 백성의 것이다…//설령 귀족이라도，//마음대로 할 수는 없다∈',
        339: '네놈도 도시를 만들었다면…//도시를…백성을 지켜라∈//상처 입히는 건 용서 못 한다∈',
        347: '고집불통이라니까∈//다른 도시에서 왔으니까，//좋은 점이 보이는 거잖아∈',
        350: '어른에게서 아이에게…//그렇게 생명을 이으며，//도시를 만드는 거야．',
        353: '그러니까…잠자코 지켜봐．//네 말대로，//이 도시가 실패작이라면…',
        354: '당연한 거 아니냐．//도시도 결국，//사람들이 모여 만들어지는 거라고．',
        360: '그건 아니라고 생각합니다．//도시에는//성공도 실패도 없을 겁니다．',
        370: '오노히코，본색이 나오네．//…어쩔 수 없네．//우리가 안아 버리자．',
        371: '…작별 인사는 다 끝난 모양이네．//오오가미 군…이제，//할 말은 다 했지？',
        374: '음…왜 그러세요？//그렇게 웃으시다니…//이상한 말 했나요？',
        400: '친구의 첫 무대를 본다…//남자의 우정은 좋네∈//…좀 땀 냄새 나지만．',
        430: '그래…//그게 종합 연출로서//오오가미 군의 의견이라는 거구나．',
        483: '맞아．//나도 종합 연출을 맡았으니，//긍정적으로 생각해 보려고 해．',
        491: '저래 보여도…여린 아이예요．//누군가 힘이 되어 줘야//마음이 무너지지 않아요．',
        501: '음…됐어．//급한 일도 아니고…//다른 방으로 갈까．',
    }
    for i, text in fitted.items():
        plan[focus[i]['unit']]['text'] = text
    plan['dialogue:8fd169634855feec']['text'] = '결투를 거절한다면，//나와 결혼할 것을 맹세해라∈//자，어느 쪽을 택할 테냐∈'

    evidence = ROOT / 'assets/translation/review/20261022-dialogue'
    if evidence.exists():
        raise RuntimeError('이미 적용한 검수 기록입니다. 중복 실행하지 마세요.')
    before = {key: copy.deepcopy(catalogue.units[key]) for key in plan}
    units = copy.deepcopy(list(catalogue.units.values()))
    proposed = Catalogue(units)
    changed_ids = set()
    for key, item in plan.items():
        unit = proposed.units[key]
        assert 'parts' not in unit, key
        for field in ['variants', 'breaks']:
            unit.pop(field, None)
        unit['text'] = item['text']
        unit['review'] = '원문 대조 교정 · 2026-10-22'
        for occurrence in unit['occurrences']:
            changed_ids.add(occurrence['id'])
            occurrence.pop('form', None)
    index_path = ROOT / 'assets/translation/index.json'
    index = json.loads(index_path.read_text(encoding='utf-8'))
    segments = {}
    all_rows = []
    for descriptor in index['segments']:
        records = read_jsonl(ROOT / descriptor['path'])
        for row in records:
            if row['id'] in changed_ids:
                row.pop('form', None)
        segments[descriptor['path']] = records
        all_rows.extend(records)
    resolved = proposed.resolve(all_rows)
    codes = json.loads((ROOT / 'config/encoding.json').read_text(encoding='utf-8'))
    errors = []
    for oid in changed_ids:
        row = resolved[oid]
        size = len(encode(row['text'], codes))
        if size > row['capacity']:
            errors.append((oid, size, row['capacity'], row['text']))
        old = rows[oid]['text']
        # 미해석 제어 명령이 있는 문안은 자동 적용 대상에 포함하지 않는다.
        import re
        if re.findall(r'@[A-Za-z]+[0-9,]*|⟦[^⟧]*⟧', old):
            errors.append((oid, '제어문안 수동 확인 필요'))
    if errors:
        print(json.dumps(errors, ensure_ascii=False, indent=2))
        raise RuntimeError('저장 전 검증 실패')
    evidence.mkdir(parents=True)
    with zipfile.ZipFile(evidence / 'before.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(index_path, index_path.relative_to(ROOT))
        for path in hashes:
            archive.write(ROOT / path, path)
    for descriptor in index['units']:
        path = descriptor['path']
        records = [proposed.units[u['id']] for u in read_jsonl(ROOT / path)]
        (ROOT / path).write_text(''.join(json.dumps(u, ensure_ascii=False) + '\n' for u in records), encoding='utf-8')
    for descriptor in index['segments']:
        path = descriptor['path']
        if any(r['id'] in changed_ids for r in segments[path]):
            (ROOT / path).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in segments[path]), encoding='utf-8')
        descriptor['sha256'] = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    final, final_rows, _ = load()
    records = []
    pending = {240,462,463,494}
    for i, entry in enumerate(focus):
        key = entry['unit']
        unit = final.units[key]
        texts = {form: final.text(key, form) for form in ['default'] + list(unit.get('variants', {}))}
        status = 'approved' if key in plan else 'compared'
        note = plan.get(key, {}).get('reason', '原文と一般・音声の各訳を対照。表現差を保存し、統一判断は未確定。')
        note = note.replace('原文と一般・音声の各訳を対照。表現差を保存し、統一判断は未確定。', '원문과 일반·음성 번역을 대조함. 기존 표현 차이는 보존했으며 통일 여부는 미확정.')
        if i in range(466,472):
            status = 'needs_source'
            note = '원문이 전용 글리프 코드로 깨져 있어 의미 검수 보류. 일본어 원문 복원 필요.'
        elif i in pending:
            status = 'needs_context'
            note = '원문/번역 대조함. 화자별 호칭·어미 또는 행동 주체를 주변 장면과 추가 확인해야 함.'
        records.append({'unit': key, 'status': status, 'content_sha256': digest(json.dumps({'source':unit['source'],'texts':texts}, ensure_ascii=False, sort_keys=True)), 'note': note, 'date':'2026-10-22'})
    keys = {r['unit'] for r in records}
    for key in plan.keys() - keys:
        unit = final.units[key]
        texts = {'default': final.text(key)}
        records.append({'unit':key,'status':'approved','content_sha256':digest(json.dumps({'source':unit['source'],'texts':texts},ensure_ascii=False,sort_keys=True)), 'note':plan[key]['reason'],'date':'2026-10-22'})
    ledger_path = ROOT / 'assets/translation/review/decisions.jsonl'
    existing = read_jsonl(ledger_path) if ledger_path.exists() else []
    existing = [r for r in existing if r['unit'] not in {r['unit'] for r in records}]
    ledger_path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in existing+records),encoding='utf-8')
    changes = [{'unit':key,'source':before[key]['source'],'before':before[key], 'after':final.units[key],'reason':item['reason']} for key,item in plan.items()]
    (evidence / 'changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'changed_units':len(plan),'changed_occurrences':len(changed_ids),'compared_units':len(records)},ensure_ascii=False))


if __name__ == '__main__':
    run()
