"""원문·문맥 대조로 선택한 문장만 수정한다. --apply 없이는 길이만 확인한다."""
import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from build import encode

# 원문이 완전히 같은 사본은 같은 문안으로 함께 처리한다.
SOURCE_EDITS = [
    ('古人曰く、//「急いては事を仕損じる」', '옛말에，//「급할수록 돌아가라」', '사용자 제안: 익숙한 한국어 속담으로 현지화.'),
    ('古人⊇く、//「急いてはことをしそんじる」', '옛말에，//「급할수록 돌아가라」', '같은 장면의 일반 대사와 음성 자막 표현 통일.'),
    ('「急いてはことをしそんじる」', '「급할수록 돌아가라」', '카야마 격언을 묻는 퀴즈 선택지도 본편과 일치.'),
    ('少しは、//手加減してあげたらどうですか？', '조금은，//봐주시면 어떨까요？', '상대에게 조금 봐주라고 권하는 자연스러운 존댓말로 통일.'),
    ('大神よ……//今回はお前の大手柄だな。', '오오가미…//이번엔 네 공이 컸구나．', '네 큰 공로구나라는 어색한 명사 직역을 자연스러운 칭찬으로 수정.'),
    ('はい、了解です∈//ドーンと//まかせちゃってください∈', '네，알겠습니다∈//저만 믿으세요∈', '팍 하고·확이라는 의성어 직역을 자신 있게 맡기라는 뜻으로 수정.'),
    ('しょうがないな……//この貸しは高くつくぜ。', '할 수 없지…//이 빚은 톡톡히 갚으라고．', '도움을 받은 상대에게 보답을 요구하는 로벨리아의 능청스러운 말투를 명확히 함.'),
    ('ええ……本当にすごいですね。//ニッポンのことわざで言えば……//下手の横好きですね！', '네…정말 대단하네요．//일본 속담처럼…//솜씨는 없어도 열성은 있네요∈', '일본 속담이라는 언급과 어설픈 칭찬의 농담은 살리고 뜻을 자연스럽게 전달.'),
    ('そういう時は……胸を張り、//堂々と人々の喝采に//応えるのだ。', '그럴 때는…가슴을 펴고，//사람들의 환호에//당당히 화답하는 거다．', '갈채에 답한다는 직역을 자연스러운 한국어로 정리.'),
    ('どうした？//なにを考える必要がある。//答えは一つであろう。', '왜 그러지？//뭘 그리 망설이나．//답은 하나일 터다．', '결단을 촉구하는 반문을 생각할 필요라는 직역 대신 망설임으로 표현.'),
    ('どうした、隊長。//なにを考える必要がある？', '왜 그러나，대장．//뭘 그리 망설이나？', '동료를 남기고 갈지 고민하는 장면의 결단 촉구. 글리신의 단호한 말투 유지.'),
    ('大神さんに会って……//人を好きになるってことが//どういうことかわかったんです。', '오오가미 씨를 만나서…//누군가를 좋아하는 마음이//어떤 건지 알게 됐어요．', '좋아한다는 것이 무엇인지라는 명사화 직역을 구어로 정리.'),
    ('そういうもんか……//なんか、わかった気がする。', '그런 건가…//왠지，알 것 같아．', '알 것 같은 기분이 든다는 중복 표현 정리.'),
    ('文化の良さというものは、//触れた瞬間にわかるものだ。', '문화의 가치는，//직접 접하면 알 수 있는 법이다．', '문화에 닿는다는 물리적 직역을 문맥에 맞는 접하다로 수정.'),
    ('気合は十分だ∈//あとは、本番を待つのみ！//よし……いくぞ！', '의욕은 넘쳐∈//이제 공연만 기다리면 돼∈//좋아…간다∈', '공연을 앞둔 문맥의 本番을 전투 실전이 아닌 공연으로 수정.'),
    ('あ、ああ……ありがとう。//なんだかすごく//悪い気がするけど……', '아，아아…고마워．//왠지 정말//미안해지는데…', '마지막 푸딩을 양보받는 장면. 죄책감이라는 과한 표현을 미안함으로 수정.'),
    ('ミカサを失った帝都は、//大量の蒸気を使えなくなり、//以前の便利さを失った……', '미카사를 잃은 제도는，//증기를 충분히 쓰지 못해，//예전처럼 편리하지 않았다…', '이전의 편리함을 잃었다는 명사 직역을 자연스러운 서술로 수정.'),
    ('そして……それを//なつかしいと思う私がいる……//とてもすばらしいです。', '그리고…그게//그립게 느껴져요…//정말 멋진 일이에요．', '그립다고 느끼는 제가 있다는 번역투를 하나비의 차분한 말투로 정리.'),
]

ID_EDITS = {
    'MINIGAME/JT15KAYA.SBN#0007': ('옛말에…//「이겼어도 방심하지 마라∈」//아직 날 이기긴 멀었군，오오가미∈', '투구끈 속담을 승리 뒤에도 방심하지 말라는 뜻으로 현지화.'),
    'ADVDATA/LIPSYNC1.LIP#0665': ('그래？//이치로는//여전히 사양도 많네．', '사양을 많이 한다는 번역투를 친근한 구어로 수정.'),
    'ADVDATA/SCRIPT/S0130.SBX#2662': ('그래？//이치로 씨는//여전히 사양도 많네．', '음성 자막과 같은 표현으로 정리하되 기존 호칭은 유지.'),
    'ADVDATA/LIPSYNC2.LIP#0338': ('반년이라 해도…//만나지 못하는 게，//이토록 괴로울 줄은 몰랐다．', '만나지 못한다는 것이라는 번역투 정리. 글리신의 절제된 어미 유지.'),
    'ADVDATA/SCRIPT/S0210.SBX#0641': ('반년이라 해도…//만나지 못하는 게，//이토록 괴로울 줄은 몰랐다．', '동일 장면의 음성 자막과 자연스러운 표현 통일.'),
    'ADVDATA/LIPSYNC3.LIP#1222': ('도시란 말이다…//사람과 사람이 어울려//만들어 가는 거 아이가', '사람과 사람의 이어짐이라는 직역을 풀고 홍란의 기존 사투리 유지.'),
    'ADVDATA/SCRIPT/S0310.SBX#1513': ('급히 배워서 될지 모르겠군…//우리는 연극에는//문외한이니까．', '付け焼刃의 급히 익힌 솜씨라는 뜻을 살려 벼락치기 수준이라는 어색한 표현 정리.'),
}


def main(apply=False):
    if json.loads((ROOT / 'assets/translation/index.json').read_text(encoding='utf-8')).get('schema'):
        raise SystemExit('이관 이전 일회성 수정 도구입니다. 현재 문안은 src/dialogue.py로 검색하여 units/에서 수정하세요.')
    codes = json.loads((ROOT / 'config/encoding.json').read_text(encoding='utf-8'))
    source_edits = {s: (t, why) for s, t, why in SOURCE_EDITS}
    changes, pending = [], {}
    matched_sources, matched_ids = set(), set()
    for path in sorted((ROOT / 'assets/translation/segments').rglob('*.jsonl')):
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]
        touched = False
        for row in rows:
            choice = ID_EDITS.get(row['id']) or source_edits.get(row.get('source'))
            if not choice:
                continue
            if row['id'] in ID_EDITS: matched_ids.add(row['id'])
            if row.get('source') in source_edits: matched_sources.add(row['source'])
            new, reason = choice
            if row['text'] == new:
                continue
            before = row['text']
            encoded = encode(new, codes)
            lengths = [len(encode(part, codes)) for part in new.split('//')]
            # 공백은 렌더러에서 반각 폭. 보수적으로 인코딩 글자 수(최대 전각 폭)로
            # 각 수동 줄바꿈 구간을 16칸 이내에 제한한다.
            visual_lines = sum(max(1, (n + 31) // 32) for n in lengths)
            controls = lambda s: re.findall(r'⟦[^⟧]+⟧|@[A-Za-z]+[0-9,]*', s)
            assert controls(new) == controls(before), row['id']
            for symbol in ['∈', '〓', '「', '」']:
                assert new.count(symbol) == before.count(symbol), (row['id'], symbol)
            if len(encoded) > row['capacity'] or visual_lines > 3:
                print('NG', row['id'], len(encoded), '/', row['capacity'], 'lines', lengths)
                pending[row['id']] = new
            changes.append({'id': row['id'], 'path': path.relative_to(ROOT).as_posix(),
                            'source': row.get('source'), 'before': before, 'after': new,
                            'reason': reason, 'encoded_bytes': len(encoded), 'capacity': row['capacity'],
                            'line_bytes': lengths, 'max_fullwidth_lines': visual_lines})
            row['text'] = new
            row['review'] = '교차 검토 필요'
            touched = True
        if touched:
            pending[path] = rows
    assert matched_sources == set(source_edits), ('미발견 원문', set(source_edits) - matched_sources)
    assert matched_ids == set(ID_EDITS), ('미발견 ID', set(ID_EDITS) - matched_ids)
    errors = [key for key in pending if isinstance(key, str)]
    print('선택 변경', len(changes), '행 / 길이 초과', len(errors))
    for change in changes:
        print(change['id'], change['before'], '→', change['after'])
    if errors or not apply:
        assert not errors, errors
        return
    if not changes:
        return
    # 직전 산출물을 기준으로 이번 문안 영역 밖 무변경을 확인할 근거를 남긴다.
    bounds = {}
    for change in changes:
        row = next(r for r in pending[ROOT / change['path']] if r['id'] == change['id'])
        bounds.setdefault(row['file'], []).append([row['offset'], row['offset'] + row['capacity'] + 1])
    previous = {}
    with zipfile.ZipFile(ROOT / 'out/sakura_wars_4_kr_dev.dcp') as z:
        for name in z.namelist():
            data = bytearray(z.read(name))
            previous[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}
            for start, end in bounds.get(name, []):
                data[start:end] = bytes(end - start)
            previous[name]['protected_sha256'] = hashlib.sha256(data).hexdigest()
            previous[name]['allowed_ranges'] = bounds.get(name, [])
    snapshot = ROOT / 'work/issues/localization-20261022/before-dcp.json'
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(json.dumps(previous, indent=2) + '\n', encoding='utf-8')
    # 전체 사전 검증을 통과한 뒤에만 문안 파일을 저장한다.
    for path, rows in pending.items():
        path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    index_path = ROOT / 'assets/translation/index.json'
    index = json.loads(index_path.read_text(encoding='utf-8'))
    for seg in index['segments']:
        path = ROOT / seg['path']
        if path in pending:
            seg['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    index['release_approved'] = False
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'research/localization-20261022.json').write_text(
        json.dumps({'changes': changes, 'runtime_verified': False,
                    'scope': '추출 문안의 속담·관용구·직역투 후보 대조. 전 대사 수동 검수 완료를 의미하지 않음.'},
                   ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    main(parser.parse_args().apply)
