"""전투 이름판 이슈의 수정·검증 결과를 기존 이미지 검수표 원천에 반영한다."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def read(path): return json.loads((ROOT / path).read_text(encoding='utf-8'))
def write(path, value):
    (ROOT / path).write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

def main():
    cfg = read('assets/images/remake/slg_plates.json')
    fields = {}
    for row in read('research/slg-layout-audit.json'):
        block = next(b for b in cfg['blocks'] if b['source'] == row['source'] and b['block'] == row['block'])
        chain = next(c for c in cfg['templates'][block['template']] if c['key'] == row['field'])
        for rect in chain['rects']:
            fields.setdefault((row['source'], row['block'], rect[0]), set()).add(row['field'])
    rows = read('assets/images/review/image_review.json')
    affected = []
    marker = ' [2026-10-22 이름판 자간 수정]'
    for row in rows:
        key = (row['source'], row['block'], row['texture'])
        if key not in fields:
            continue
        specific = '「시카 미」를 「시카미」로 수정. ' if row['id'] == 120 else ''
        row['note'] = row['note'].split(marker)[0] + marker + ' ' + specific + (
            '조각 경계에서 글자 하나를 밀어 단어 중간이 벌어지던 공통 배치를 수정. '
            '자간을 유지한 전체 이동·가로 축소로 경계를 피하며 실제 획과 그림자 유무로 폭을 계산한다. '
            f'이 텍스처의 점검 필드: {", ".join(sorted(fields[key]))}. '
            '재삽입·최종 DCP 검사 완료. 게임 화면 확인은 아직 하지 못함.')
        affected.append(row)
    write('assets/images/review/image_review.json', rows)
    updates_path = 'assets/images/review/image_review_updates.json'
    updates = read(updates_path) if (ROOT / updates_path).exists() else []
    updates = [r for r in updates if r.get('id') != 'battle-name-spacing-2026-10-22']
    updates.append({'id': 'battle-name-spacing-2026-10-22', 'date': '2026-10-22',
        'title': '전투 이름판의 단어 중간 간격 및 승리 자막 미번역 수정',
        'comparison': 'assets/images/remake/battle_issuefix/shikami-before-after.png',
        'notes': [
            f'이미지 검수표 {len(affected)}종(사본 포함 {sum(r["copies"] for r in affected)}장)에 후속 점검 메모를 추가했다. 시카미는 #120이다.',
            '원인: 이름판의 조각 경계에 걸린 글자 하나만 다음 조각으로 밀어내 「시카 미」처럼 단어가 갈라졌다. 같은 분할 배치 72곳을 검사·수정했고 인위적인 추가 자간은 0px이다.',
            '관련 텍스트 이슈: 승리 포즈 뒤 「決め!!」는 실행 파일이 아닌 LIPSYNC1~4에서 실제 문구 앞 프레임 데이터 f를 대사로 잘못 추출해 누락한 자막이었다. 6곳을 「결정!」으로 번역하고 프레임 데이터·포인터 표·파일 길이를 보존했다.',
            '검증: 테스트 13개 통과, 이미지 재삽입 및 최종 DCP 자막 확인 완료. Flycast emucap 어댑터 실행 파일이 없어 게임 안의 화면 확인은 하지 못했다.'
        ]})
    write(updates_path, updates)
    print('검수 메모 반영:', len(affected), '종 / 시카미 #120')

if __name__ == '__main__': main()
