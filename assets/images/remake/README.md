# 원본 디자인 재제작

> 저작권: 이 폴더의 PNG·비교 시트·`slg_compare.html`은 게임 원본 그림에서 나온 것이라 git에 올리지 않는다(.gitignore). 저장소에는 재제작 명세(JSON)와 스크립트만 둔다. PNG는 `build.ps1`이 로컬 원본(`originals/`)에서 다시 만든다. 단 `logo_sakura_mask.png`(사쿠라 한글 글자 모양)는 생성물이 아닌 입력 파일이라 로컬에 따로 보관해야 한다.

v0.5 개선판에서 원본 디자인이 사라진 이미지를 원본 모양으로 다시 그린 결과다. **게임 파일에는 아직 넣지 않았다**(PNG → BPV1 재삽입기 없음).

## SLG 컷인 이름판 (`slg/`)

- 입력 `slg_plates.json`: 블록별 한국어 문구(v0.5 이미지에서 옮겨 적음)와 글자 띠 배치 템플릿.
- 생성 `python src/remake_slg_plates.py`: 원본 텍스처 위에 글자 띠만 다시 칠한다. 반투명 검은 판(알파 136), 명조(Noto Serif KR 600), 오른쪽 아래 그림자, 불투명 검은 상자를 쓰고 ARGB4444 단계로 양자화한다.
- 비교 `slg_compare.html`(이미지 내장, 배율 선택) / `slg_compare.png`: 원본 · v0.5 · 재제작 3단.
- 텍스처 70장. 같은 그림을 쓰는 UNITS의 GRCT 등 32곳은 시트에 "같은 이미지"로 표시한다.

한 chain의 조각들은 게임에서 이어 붙여 보이는 것으로 보고 글자를 조각 경계에서 잘라 이어 그렸다(원본과 같은 방식). 적·오브젝트 판(G02~G05)의 표시 영역은 원본과 v0.5 배치로 추정했으며 실기 확인 전이다.

## 게임 데이터 재삽입 (`python src/inject_images.py`)

재제작 PNG(slg → staffroll → ui → logo 순, 뒤가 앞을 덮음)를 BPV1/ADCG로 다시 인코딩해 `assets/images/native/`에 쓴다. 매번 `originals/v05`에서 다시 만들고, 같은 그림을 쓰는 사본(검수표 members)에도 똑같이 넣는다. 그 뒤 `python src/build.py`로 DCP를 만든다.

- 픽셀: ARGB4444/RGB565/ARGB1555, twiddle·선형·VQ(2×2 k-평균, 기존 코드북에서 시작). ADCG는 64×64 타일 단위, 같은 타일은 공유.
- 압축: `src/prs_compress.py`의 최적 경로 PRS(원본보다 약 5% 작음). 원래 자리(다음 태그 앞)까지만 쓴다.
- CG_ALL1.DAT: 레코드는 2048 정렬이고 옮기지 않는다. 자리가 모자라면 실패한다(`--allow-move`를 주면 파일 끝으로 옮기고 GR.IDX 섹터를 고친다). 스태프롤은 `remake_staff_roll.py`가 자리에 맞을 때까지 단순화한다. 길이가 늘어난 레코드는 `ADVDATA/GR.IDX`(0x128부터 16바이트 항목: 섹터, 길이, 번호, 0)의 길이를 늘린다.
- 검증: 다시 디코딩해 PNG와 비교(VQ 외에는 반올림 1단계 이내, VQ는 평균 차이 6 이하), 대상 아닌 블록 byte 동일, 기존 블록 위치 동일, GR.IDX 항목이 가리키는 레코드 확인. 결과는 `inject_report.json`.
