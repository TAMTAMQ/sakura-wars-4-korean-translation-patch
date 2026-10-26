"""완료한 정적 검사 결과로 이슈 #7 검수 문서를 갱신한다."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / 'work/issues/20261026-ending'


def main():
    verification = json.loads((CASE / 'static-verification.json').read_text(encoding='utf-8'))
    assert verification['ok']
    rows = [
        ('로고의 검은 대·전 상자', '이번 수정', '본문 크기의 보라색 대전으로 재제작. 원천 8종과 사본을 포함한 20개 텍스처를 최종 DCP에서 다시 디코딩해 대조.'),
        ('낫표', '수정 전으로 복원', '사용자 요청으로 비교표의 수정 전 글꼴 위치와 표시 폭을 모두 복원. 실행 파일과 글꼴 4종이 v0.8.7과 동일함을 대조.'),
        ('레니·제도 복구·레 미제라블 대사', '이번 수정', '내가 해야 할 말이야 / 모여든 사람들의 / 내가 모든 것을 맡은 으로 교정.'),
        ('무슈 호칭', '원래 표현 복원', '사용자 요청으로 공유 문안 45개·사용처 71곳의 무슈 호칭과 조사를 복원. 별개 오역인 고마워 → 천만에 교정은 유지.'),
        ('스태프 이름 열 정렬', '이번 수정', '77행의 둘째 이름 시작 칸 통일. 회사명 4곳의 선행 공백 제거. 파일 크기·바이트코드·스크롤 시점 보존.'),
        ('엔딩 시 14장·마지막 세로 문구', '기존 번역 재확인', 'v0.8.6부터 포함. 최종 DCP 재추출 15장을 번역 PNG와 대조. 이번 신규 번역으로 집계하지 않음.'),
        ('풍림화산', '원본 유지', '사용자 지정대로 風林火山 한자·연출 그대로. SLG/COM.BC는 패치에 미포함. 원본 해시 및 변경 방지 검사 추가.'),
        ('튜토리얼 제목·아사쿠사 표지판', '기존 수정 유지', '세로 제목 번역 및 표지판 연장·원래 글자 크기 유지.'),
        ('시카미 간격·승리 후 決め!!', '기존 수정 유지', '이름 조각 배치 수정 및 LIPSYNC1~4의 결정! 자막 유지.'),
        ('급할수록 돌아가라·말투·띄어쓰기', '기존 수정 유지', '일반/음성 공유 문안, 홍란 사투리, 레니 말투 및 호칭 검수 결과 유지.'),
        ('선택지·그란 마 대사 넘침', '기존 수정 유지', '선택지 폭 제한과 대사 3줄 배치 유지.'),
        ('옵션 정렬·승리 대사 높임말', '기존 수정 유지', '기존 실행 파일 문자열 패치와 대사 교정 유지.'),
        ('마작 이름·리치·짧은 외침', '기존 수정 유지', '마작 이름표와 누락 문자열 141곳 번역 유지.'),
        ('전투 컷인 이름·기술·쌍무', '기존 수정 유지', '이름판 26장, 기술판 13장 및 원래 조각 좌표에 맞춘 배치 유지.'),
        ('요키히코 다들·카야마 겁먹지', '기존 수정 유지', 'v0.8.7 교정 유지.'),
        ('엔딩 完', '기존 수정 유지', 'v0.8.7의 끝 번역 유지.'),
        ('숫자·물음표 굵기', '기존 수정 유지', '기존 글꼴 유지. 이번 글꼴 변경은 여는 낫표 타일 53·55뿐.'),
        ('저장 경고의 작은 글씨', '원본 규격 유지', '공용 시스템 글꼴의 크기를 임의 확대하지 않음.'),
        ('사랑과 미 표현', '기존 결정 유지', '문자열 용량에 맞춘 사랑과 미 표현 유지.'),
        ('얼굴 가로선·비율', '정적 확인 한계', '얼굴 컨테이너는 패치에 없음. 가로선은 기존 에뮬레이터 업스케일 설정 관련 안내 유지. 비율 문제 해결 판정은 하지 않음.'),
        ('엔딩 프레임·음악·나레이션 저하', '범위 제외', '2026-10-27 사용자 요청: 에뮬레이터 환경 문제로 보고 우선 무시. 성능 수정·동적 검사는 하지 않음.'),
        ('3막 이벤트 스킵', '기존 수정 유지', '제보자는 v0.8.3에서 해당 이벤트를 봤다고 답변. 이번 실행 검증은 하지 않음.'),
        ('디지커뮤 실행', '별도 게임', '사쿠라대전4 자산이 아닌 별도 프로젝트 대상. 이번 패치에 변경 없음.'),
    ]
    out = ['<!doctype html><html lang="ko"><meta charset="utf-8"><title>사쿠라대전4 이슈 #7 검수</title><style>body{font-family:system-ui;background:#edf0f5;color:#18202d;margin:24px;line-height:1.6}section{background:white;padding:20px;margin:16px 0}img{max-width:100%;image-rendering:pixelated}table{border-collapse:collapse;width:100%}td,th{border:1px solid #bdc6d0;padding:10px;text-align:left}code{overflow-wrap:anywhere}</style><h1>이슈 #7 검수 · 2026-10-27</h1><p>v0.8.8 릴리즈 · 정적 검사만 수행. 프레임 저하는 사용자 요청으로 이번 범위에서 제외했습니다.</p><section><h2>이슈 항목별 처리</h2><table><tr><th>항목</th><th>판정</th><th>내용</th></tr>']
    for row in rows:
        out.append('<tr>' + ''.join('<td>'+html.escape(x)+'</td>' for x in row) + '</tr>')
    out.append('</table></section><section><h2>로고 비교 · 기존 재제작본 / 이번 수정</h2><p>원래 재제작본을 보존하고 옆에 이번 수정본을 표시합니다. 원본 캔버스·조각 좌표를 유지합니다.</p>')
    for item in json.loads((ROOT / 'assets/images/remake/logo-daejeon-20261026/comparisons.json').read_text(encoding='utf-8')):
        out.append(f'<h3>{html.escape(item["source"])} b{item["block"]}</h3><img src="../../../{item["comparison"]}">')
    out.append('</section><section><h2>낫표 수정 전후</h2><p>실제 게임 글꼴과 표시 폭을 이용한 정적 재현입니다. 게임 실행 화면이 아닙니다. 현재 적용본은 위쪽 수정 전입니다. 아래쪽 수정 시안은 채택하지 않았습니다.</p><img src="brackets-comparison.png"></section><section><h2>스태프 이름 열</h2><p>최종 글꼴을 이용한 배치 재현입니다. 게임 실행 화면이 아닙니다.</p><img src="credits-comparison.png"></section><section><h2>기존 엔딩 번역 재추출</h2><img src="ending-quotes-1048.png">')
    for block in range(728, 742):
        out.append(f'<img width="320" src="ending-nc-{block}.png" title="b{block}">')
    out.append(f'</section><section><h2>정적 검증</h2><p>테스트 35개 통과. 로고 20개 텍스처 재삽입 대조, 번역 사용처 {verification["translated_text_readbacks"]:,}개 재추출 대조, 스태프 77행 포인터·문안 검증, 실행 파일 전체 및 글꼴 4종의 v0.8.7 동일성, 풍림화산 원본 보존을 확인했습니다.</p><p>최종 DCP SHA-256: <code>{verification["sha256"]}</code></p><a href="static-verification.json">정적 검증 결과</a> · <a href="../../../out/sakura_wars_4_kr_dev.dcp">개발 패치</a> · <a href="../../../assets/images/review/image_review.html">이미지 검수표</a> · <a href="../../../assets/images/remake/logo-daejeon-20261026/generation-notes.md">로고 제작 기록</a></section></html>')
    (CASE / 'review.html').write_text('\n'.join(out), encoding='utf-8')
    p = ROOT / 'assets/images/review/image_review_updates.json'
    updates = json.loads(p.read_text(encoding='utf-8'))
    for item in updates:
        if item['id'] == 'ending-issue7-2026-10-26':
            item['notes'][-1] = '2026-10-27 사용자 요청으로 프레임·음악·나레이션 저하는 이번 범위에서 제외했다. 정적 검사만 수행했다.'
    updates = [x for x in updates if x['id'] != 'issue7-logo-static-2026-10-27']
    updates.append(dict(id='issue7-logo-static-2026-10-27',date='2026-10-27',title='이슈 #7 로고 재제작·정적 검증 완료',comparison='assets/images/remake/logo-daejeon-20261026/ADVDATA_CG_ALL1.DAT_733-comparison.png',comparison_label='기존 재제작본 / 이번 수정',notes=[rows[0][2],rows[1][2],rows[3][2],rows[6][2],'개별 수정 칸에서 기존 재제작 보존본과 나란히 비교한다. 전체 항목별 처리표: work/issues/20261026-ending/review.html.','테스트 35개 통과. 프레임 저하는 사용자 요청으로 제외했으며 동적 검사를 하지 않았다.']))
    p.write_text(json.dumps(updates,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
    p = ROOT / 'docs/status.md'
    old = p.read_text(encoding='utf-8')
    current = old.index('# 현재 상태')
    p.write_text('# 이슈 #7 추가분 (2026-10-27, v0.8.8)\n\n' + '\n'.join('- '+a+': '+b+'. '+c for a,b,c in rows[:7]) + '\n- 정적 검증: 테스트 35개 통과. 최종 DCP 번역 사용처 16,643곳 재추출 대조 및 로고 20텍스처 대조 완료. 상세 결과는 work/issues/20261026-ending/static-verification.json.\n- 프레임 저하는 사용자 요청으로 이번 범위에서 제외한다. 동적 검사는 수행하지 않는다. 얼굴 비율은 정적 자료로 해결 여부를 판정하지 않는다.\n- 최종 개발 패치: out/sakura_wars_4_kr_dev.dcp. 전체 항목별 검수표: work/issues/20261026-ending/review.html. 사용자가 커밋·푸시·릴리즈·이슈 댓글 게시를 승인했다. 릴리즈: https://github.com/TAMTAMQ/sakura-wars-4-korean-translation-patch/releases/tag/v0.8.8\n\n'+old[current:],encoding='utf-8')
    p = ROOT / 'docs/decisions.md'
    marker = '## 2026-10-27: 정적 검사 및 로고·낫표'
    text = p.read_text(encoding='utf-8')
    if marker not in text:
        p.write_text(text+'\n\n'+marker+'\n\n사용자 요청으로 컴퓨터 조작 및 동적 검사를 하지 않는다. 프레임 저하는 에뮬레이터 환경 문제로 보고 이번 범위에서 제외한다. 풍림화산 원본 유지 결정을 계속 적용한다. 로고는 기존 검은 상자 대신 본문 크기의 대전으로 바꾸고 원래 조각 좌표를 유지한다. 제작 원천과 좌표는 assets/images/remake/logo-daejeon-20261026/generation-notes.md에 기록한다. 여는 낫표는 글리프 위치와 표시 폭을 함께 바꾸며 SH4 원천·역해석·재조립·독립 디스어셈블 검증을 거친다.\n',encoding='utf-8')
    print('검수 문서 갱신 완료')


if __name__ == '__main__':
    main()
