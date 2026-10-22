# 전투 이름판과 승리 자막 수정 — 2026-10-22

## 「시카 미」처럼 이름이 갈라지는 문제

문안은 「시카미」로 공백이 없다. CMAP02.GRCT 블록 6의 B 칸은 48px·24px 두 조각으로 저장되어 있고, 기존 `remake_slg_plates.py`는 경계에 걸린 글자 하나만 다음 조각으로 밀었다. 그 결과 「시카」와 「미」 사이에 일반 자간보다 큰 틈이 생겼다.

공통 배치 함수를 고쳤다. 각 글자의 획이 조각 경계를 넘지 않는 공통 원점을 찾아 문자열 전체를 이동한다. 불가능하면 전체의 가로 배율을 함께 줄이며, 글자 하나만 따로 밀지 않는다. 실제 잉크 경계로 계산하고, 그림자가 없는 검은 이름 상자에는 그림자 여유를 예약하지 않아 불필요한 가로 축소도 줄였다.

같은 코드를 쓰는 분할 필드 72곳을 전부 재생성·검사했다. 이름판 PNG는 70장이고, 일부는 기존 v0.5 배치를 유지하는 턴 시작 이름 띠다. 사본은 기존 이미지 검수 색인의 members를 따라 함께 반영했다. UI·스태프롤·로고 생성기는 이 개별 글자 이동 코드를 사용하지 않는 것을 확인했다.

- 기계 검사: 글자 원점 간격이 원래 자간과 일치하고, 인위적인 추가 간격 0px.
- 비교 시트: `assets/images/remake/battle_issuefix/layout-01.png` ~ `layout-06.png`.
- 시카미 비교: `assets/images/remake/battle_issuefix/shikami-before-after.png`.
- 배치 근거: `research/slg-layout-audit.json`.

## 「승리의 포즈」 뒤 「決め∈」 미번역

이번 누락은 실행 파일이 아닌 `ADVDATA/LIPSYNC1~4.LIP`에 있었다. 표의 off_b가 가리키는 자리에 프레임 데이터 끝의 `66 00`(ASCII `f` + NUL)이 있고, 그 다음에 실제 `決め∈` 자막이 있었다. 기존 추출기는 `f`를 대사로 등록하고 실제 문구는 편집 입력에서 놓쳤다.

해당 안정 ID의 보호 경계를 실제 자막 위치로 교정하고 6건을 「결정∈」로 번역했다. ∈(81b8)는 이 게임에서 기존부터 쓰는 느낌표 코드다. 기존 「승리의 포즈…결정∈」 번역과 표현을 맞췄다.

| 파일 | 표 행 | 실제 자막 위치 |
|---|---|---|
| LIPSYNC1.LIP | 823 / 1475 | 0x20DD1 / 0x2D13A |
| LIPSYNC2.LIP | 2418 | 0x51F21 |
| LIPSYNC3.LIP | 1044 / 2133 | 0x2D57D / 0x49AC4 |
| LIPSYNC4.LIP | 1710 | 0x3818E |

원래 `8c88 82df 81b8` → 번역 `f2ab f18e 81b8`. 앞뒤 프레임 정보, NUL, 포인터 표와 파일 길이는 바꾸지 않았다.

## 검증과 재생성

```powershell
python src/remake_slg_plates.py
python src/remake_individual.py
python src/inject_images.py --source-prefix SLG/
python -m unittest discover -s tests -v
python src/build.py
python research/verify_battle_issuefix.py
```

주 빌드 출력은 `out/sakura_wars_4_kr_dev.dcp`다. ZIP CRC, 등록된 쓰기, 이미지 재디코딩, 실제 DCP 안의 자막 6건과 LIP 표 무변경을 검증했다. 테스트는 13개다.

Flycast의 emucap 어댑터 실행 파일이 없어 게임 안의 실행 확인은 하지 못했다. 실행 계획의 진단은 `adapter binary is unavailable`이다. 정적 이미지와 DCP 검증을 실기 확인으로 간주하지 않는다.

## 이미지별 후속 검수와 비교 보존 (2026-10-22)

공통 배치의 가로 압축을 모든 이미지의 최종 해결로 보지 않는다. 원본과 기존 재제작을 각각 대조하여 확인한 10종만 `src/remake_individual.py`에서 수정한다. #121~#123은 세로 な/し를 세로 없/음으로 배치하고, #120·#132는 원본 ???를 복원한다. #132는 제목과 검은 이름칸도 자연 비율로 다시 배치했다. #127·#134·#136·#138·#140의 F2는 원본 픽셀로 복원했다. 다른 이미지에 이 배치 규칙을 일괄 적용하지 않는다.

기존 재제작 154종은 `assets/images/review/remake_baseline/`에 보존하며 SHA-256 목록은 `remake_baseline.json`이다. 새 수정층은 `assets/images/remake/individual/`이고, 재삽입에서 마지막으로 합성한다. 검수표는 원본 / v0.5 / 재제작 보존본 / 개별 수정의 순서로 보여 준다. 수정이 있는 이미지에만 네 번째 칸과 사유가 나타난다. 검수표 생성은 `python src/write_image_review.py`다.

`python research/verify_individual_review.py`는 기존 재제작과 보존본의 해시, 수정 영역 밖 픽셀 무변경, 원본 기호의 완전 일치, HTML 비교 순서를 검증한다. 다른 긴 이름·필살기에서 남아 있는 압축 배치는 이번 10종의 수정 완료에 포함하지 않는다. 턴 시작 띠는 여전히 v0.5 배치이며 게임 내 합성 확인이 필요하다.
