# 사쿠라 대전 4 한국어 번역 패치

드림캐스트용 『사쿠라 대전 4 사랑하라 소녀여』(사쿠라대전4) 팬 한글화 패치 프로젝트입니다.

- 스토리 본편, 전투(SLG) 이벤트, 미니게임, 시스템 메시지/메뉴, 음성 대사 자막(LIPSYNC)까지 게임 내 텍스트 약 3만 줄 이상을 다룹니다.
- 완성형 한글 2,350자를 게임 폰트(SKFONT.CG~4.CG)의 한자 영역에 새로 그려 넣는 방식으로 한글을 표시합니다.
- 번역 반영, 리포인팅, 폰트 생성까지 스크립트 한 번 실행으로 처리됩니다.

### 프로젝트 담당자

| 역할 | 담당 |
|---|---|
| 번역 | gemma-4-26b-a4b-it-qat |
| 검수 | Claude Sonnet 5, 나 |

## 1. 원본 확인

패치 대상: 일본판 드림캐스트 『사쿠라 대전 4 ~사랑하라 소녀여~』(サクラ大戦４ 〜恋せよ乙女〜), 버전 v1.003이어야 합니다. 다른 버전(리전/리비전이 다른 이미지)에서는 오프셋이 맞지 않아 패치가 정상 적용되지 않을 수 있습니다.

- `DISC/` 폴더에 이미지에서 추출한 원본 파일 구조를 그대로 보관합니다(참고/추출용, 저장소에는 포함되지 않음 — `.gitignore` 참고).
- 패치는 이 원본 데이터 트랙 안의 파일들을 번역본으로 교체하는 방식으로 동작하며, GDI 빌드는 `output_공백없음 [GDI]/` 같은 폴더에 디스크 이미지를 재구성해 만듭니다.

## 2. 패치 적용

1. [Releases](../../releases)에서 `sw4.dcp`를 받습니다.
2. Universal Dreamcast Patcher의 Apply Patch에 `sw4.dcp`를 지정해 원본 GDI/CDI에 적용합니다.
3. 반드시 "1. 원본 확인"에 명시된 버전(일본판, v1.003)의 정당하게 소유한 정품 이미지에만 적용하세요. 게임 파일 자체(ISO/GDI, BIOS 등)는 이 저장소에 포함되어 있지 않습니다.

직접 빌드한 패치를 적용하고 싶다면 "4. 직접 빌드하기"를 참고하세요.

## 3. 패치 내용

| 영역 | 파일 수 | 대사량 |
|---|---|---|
| ADVDATA/SCRIPT (스토리 본편) | 14개 | 24,289줄 |
| ADVDATA/APPEND, EBG_VIEWER | - | 176줄 |
| MINIGAME (가위바위보 등) | 26개 | 1,415줄 |
| SLG/G01~G05/E (전투 이벤트) | 84개 | 약 3,000줄 |
| SLG_ESM (SMAP01~05, 전투 개시 대사) | 5개 | 1,040줄 |
| 1ST_READ.BIN (시스템 메시지/메뉴) | - | 214개 |
| APPEND.BIN / MGJT.BIN (엔딩·마작 UI) | - | 518개 |
| LIPSYNC1~4.LIP (음성 자막) | 4개 | 7,944줄 |

- 위 항목은 전부 번역 텍스트가 존재하며 자동 반영됩니다.
- SYSDATA의 CBD 이미지(타이틀/아이캐치 등)는 그래픽 데이터로 텍스트가 없어 번역 대상이 아닙니다. RGB565, 64×64 Morton(Z-order) 타일 포맷임을 확인했습니다(추출: `tools/extract_cbd_images.py`, `tools/extract_cg_all.py`).
- 대사 대부분은 원문보다 길게 번역해도 자동으로 리포인팅되어 화면에 그대로 반영됩니다(아래 "개발 내역" 참고). 여전히 원문 바이트 길이 제한이 남아있는 극소수 항목은 실행 후 `길이초과_건너뜀_목록.txt`에 정리됩니다.

## 4. 직접 빌드하기

**요구 사항**: Python 3, Pillow(`pip install Pillow`)

`translation_templates/`와 `tools/`만 있다고 바로 빌드되지 않습니다. `translate_all.py`가 실제로 읽는 입력 기준으로 아래 4가지가 전부 갖춰져야 합니다.

| 항목 | 출처 |
|---|---|
| `translate_all.py` | 이 저장소 (루트) |
| `tools/` (스크립트 전체) | 이 저장소 |
| `translation_templates/` (번역 텍스트) | 이 저장소 |
| `original_files/` | **직접 준비** — 정품 디스크에서 재추출 (아래 0단계) |
| `tools/1ST_READ.BIN`, `tools/SKFONT.CG~4.CG` | **직접 준비** — 정품 디스크에서 복사 (아래 0단계) |

`original_files/`와 `tools/1ST_READ.BIN`, `SKFONT*.CG`는 저작권이 있는 원본 게임 데이터라 이 저장소(`.gitignore` 참고)에는 포함되어 있지 않습니다. 정품 디스크를 정당하게 소유한 상태에서 직접 준비해야 합니다.

**0) 원본 게임 파일 준비**

정품 디스크 이미지의 데이터 트랙에서 아래 파일들을 받아와야 합니다.

- `tools/1ST_READ.BIN`, `tools/SKFONT.CG`, `tools/SKFONT2.CG`, `tools/SKFONT3.CG`, `tools/SKFONT4.CG` — 디스크 루트에서 그대로 복사
- `original_files/` — `python3 tools/extract_original_text_all.py` 등 `tools/extract_*.py` 스크립트로 디스크 원본에서 재추출 (ADVDATA/MINIGAME/SLG/SLG_ESM의 SBX/SBN/LIP/ESM 원본 바이너리)

**작업 순서**:

1. `translation_templates/` 안의 `.txt` 파일들을 디스크 경로 그대로 찾아 `[번호]` 뒤에 한글 번역을 씁니다.
2. 저장소 루트에서 다음을 실행합니다.
   ```bash
   python3 translate_all.py
   ```
   내부적으로 아래 순서로 처리됩니다.
   1) 대사(SBX/SBN) 반영 (`tools/rebuild_sbx.py`)
   2) SRPG 전투 대사(ESM/CTPA·ASCR) 반영 (`tools/patch_esm.py`)
   3) 이미 번역해둔 SBX/SBN 대사를 LIPSYNC 템플릿에 자동으로 채우고 반영 (`tools/auto_fill_lipsync.py`, `tools/patch_lipsync.py`)
   4) 오버레이 실행 파일(APPEND.BIN, MGJT.BIN) 반영 (`tools/patch_ovlm_binary.py`)
   5) 1ST_READ.BIN 반영, 리포인팅 포함 (`tools/patch_1st_read_repoint.py`)
   6) 한글 폰트(SKFONT.CG~4.CG) 생성 (`tools/hangul_font_map.py`)
3. 공백 표현 방식을 선택할 수 있습니다.
   ```bash
   python3 translate_all.py --spacing=skip   # 공백을 아예 넣지 않고 단어를 붙여씀 (기본값)
   python3 translate_all.py --spacing=tile   # 빈 한자 타일 자리를 빌려 공백을 그림
   ```
   `tile` 모드에서 폭이 부족해 들어가지 않는 항목은 해당 항목만 자동으로 `skip` 방식으로 재시도한 뒤, 그래도 안 들어가는 항목만 길이초과 목록에 남습니다.
4. 결과 검증: `python3 tools/check_translation.py`로 원문 대비 줄 수/인덱스 일치, 잔여 일본어, 특수문자(∈, 〓) 손상, 라벨 오염 등을 점검할 수 있습니다.
5. `output/` 폴더 내용을 그대로 zip으로 압축한 뒤 확장자를 `.dcp`로 바꾸면(`sw4.dcp`) Universal Dreamcast Patcher의 Apply Patch로 바로 적용할 수 있습니다.

## 5. 번역문 고치기

`translation_templates/` 하위 폴더별 담당 영역:

- `ADVDATA/SCRIPT`, `ADVDATA/APPEND` — 스토리 본편/부가 대사
- `MINIGAME` — 미니게임 대사 (마작 딜러 표기는 "딜러"로 통일)
- `SLG` — 전투 중 이벤트 대사
- `SLG_ESM` — 전투 개시 시 외치는 대사
- `1ST_READ`, `OVLM` — 시스템 메시지/메뉴/엔딩·마작 UI (원문 바이트 길이 제한 있음, 리포인팅 가능한 항목은 자동으로 길게 써도 됨)
- `LIPSYNC` — 음성이 나오는 장면의 화면 표시 자막 (원문 바이트 길이 제한 있음)

용어 통일 예: "아아, 무정" → "레 미제라블"(원작 인용구 그대로 번역).

`translation_io.py`가 모든 패치 도구에 공통으로 적용하는 자동 정리:
- `//` 앞뒤 공백 제거(전각 공백 `　`은 원문 서식이므로 보존)
- 항목 사이 빈 줄 무시
- 한글 포함 줄의 연속 말줄임표(`……`)를 `…`로 자동 축약(일본어 원문 줄은 미적용)
- `·`, `–`/`—` 등 서양식 문장부호를 일본어(JIS)에 있는 문자(`・`, `―`)로 자동 치환

원본 일본어 원문과 대조하려면 `python3 tools/extract_original_text_all.py`로 원본 디스크에서 순수 텍스트를 다시 뽑아 `original_txt/`에 생성할 수 있습니다(저장소에는 포함되어 있지 않음).

## 6. 개발 내역

- **한글 폰트**: SKFONT.CG(26×26), SKFONT2.CG(24×24), SKFONT3/4.CG(22×22) 네 파일의 Shift-JIS 한자 코드 영역에 완성형 한글 음절과 단독 자모(ㄱ~ㅣ)를 새로 그려 넣는 방식으로 매핑했습니다(`tools/hangul_font_map.py`).
- **LIPSYNC(ALPD) 자막 구조**: 대사별 `off_a`/`off_b`(오프셋+1 인코딩) 포인터 테이블이 있고, `pre_text`+`text`가 메모리상 연속으로 이어지는 구조입니다. 포인터 값을 바꿔 재배치(리포인팅)하면 실기에서 자막 타이핑(한 글자씩 표시되는) 연출이 깨지는 것을 실기 테스트로 확인했습니다. 이 때문에 테이블 값은 절대 건드리지 않고, `pre_text` 시작 지점부터 `text` 끝까지의 공간(`combined_space`) 안에서만 제자리로 교체하는 방식을 사용합니다(`tools/lipsync_format.py`).
- **1ST_READ.BIN / APPEND.BIN / MGJT.BIN 리포인팅**: 실행 코드가 각 문자열의 절대 메모리 주소(로드 베이스 `0x8c010000` + 파일 오프셋)를 참조하는 포인터 테이블 형태로 몰려있는 경우가 많아, 코드를 디스어셈블하지 않고도 파일을 스캔해 포인터를 찾아 자동으로 재배치할 수 있었습니다(1ST_READ.BIN 기준 214개 중 206개, 96% 자동 탐지). 포인터를 못 찾은 나머지는 원문 바이트 길이 이내로 제한됩니다.
- **SMAP0X.ESM(전투 개시 대사)**: 3D 맵 데이터(NJCM, 세가 닌자 포맷) 안에 CTPA/ASCR 텍스트 청크가 흩어져 있는 구조라, 목차 없이 파일 전체를 스캔해 헤더 정합성과 가나/한자 포함 여부로 유효한 청크만 골라내는 방식으로 찾았습니다.
- **SYSDATA CBD/ADCG 이미지 포맷**: RGB565, 64×64 Morton(Z-order) 트위들 타일 저장 방식이며, 세로 방향으로 저장되어 있어 시계방향 90도 회전 + 좌우 반전을 해야 정상적으로 보입니다. PSP판 사쿠라대전 팬번역 자료의 자기상관 분석 기법을 참고해 규명했습니다.
- 그 외 상세 변경 이력(공백 처리 옵션, 문장부호 자동 치환, 길이초과 처리 등)은 [README.txt](README.txt)에 시간순으로 기록되어 있습니다.

## 7. 저장소 구성

- `tools/` — 추출/번역 반영/폰트 생성/검증용 파이썬 스크립트 전체, 이미지 추출 결과(`cbd_extracted/`, `sysdata_extracted/`)
- `translation_templates/` — 번역 작업용 텍스트 템플릿 (이 폴더의 `.txt` 파일을 편집하는 것이 번역 작업의 전부입니다)
- `translate_all.py` — 메인 실행 스크립트
- `사쿠라대전4_번역_시스템프롬프트.md` — 번역 작업 시 참고하는 톤/용어 가이드

저장소에 포함되지 않는 것들(`.gitignore` 참고, 직접 빌드 시 준비 필요, 전부 `tools/extract_*.py`로 원본 디스크에서 재추출 가능):

- `DISC/` — 원본 디스크 데이터 트랙 (스크립트에서 사용하지 않는 순수 참고용)
- `original_files/`, `original_txt/`, `tools/1ST_READ.BIN`, `tools/SKFONT*.CG` — 원본 게임에서 추출한 바이너리/원문 텍스트 (저작권 있는 원본 데이터, "직접 빌드하기" 참고)
- `output/`, `output_공백없음 [GDI]/`, `패치파일.dcp` — 빌드 결과물 (재생성 가능)

## 8. 라이선스 / 권리

- **도구 소스코드** (`tools/*.py`, `translate_all.py`): [MIT 라이선스](LICENSE). 자유롭게 쓰거나 수정하셔도 됩니다.
- **번들 폰트** (`tools/NotoSansKR-subset.ttf`): 구글 Noto Sans KR의 서브셋이며 [SIL Open Font License 1.1](tools/NotoSansKR-LICENSE.txt)을 따릅니다.
- **번역 텍스트** (`translation_templates/`): 이 프로젝트 참여자들이 직접 작성한 번역입니다. 비영리 팬 번역 목적으로 자유롭게 공유/수정하실 수 있으나, 게임을 직접 판매하거나 상업적으로 이용하는 용도로는 사용하지 말아주세요.
- **게임 원본 데이터**: 『사쿠라 대전 4』의 저작권은 SEGA 및 Red Entertainment에 있습니다. 이 저장소는 원본 게임 파일(디스크 이미지, 실행 파일, 폰트, 대사 바이너리 등)을 포함하거나 배포하지 않으며(`.gitignore` 참고), 패치는 반드시 정식 발매된 게임을 정당하게 소유한 상태에서 개인적으로 적용하는 용도로만 사용해주세요.
