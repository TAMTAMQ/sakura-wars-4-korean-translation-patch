# 사쿠라 대전 4 한국어 패치 — 후속 작업 프로젝트

일본판 Dreamcast v1.003용 닉넴이다님 v0.5 개선판을 기준으로 기존 도구와 자료를 합친 작업 폴더다. 최신 템플릿 `c0e930286ccba37e6b83b9405a06e0b0ea4e6293`를 적용했다.

**이 폴더에서 작업을 시작한다.** 개선판의 번역·반각 공백·이미지·실행 파일 수정은 모두 통합되어 있다. 기존 저장소의 `translate_all.py`를 주 빌드로 실행하면 개선판을 되돌릴 수 있어, 새 빌드 진입점을 사용한다.

## 바로 시작하기

1. `assets/translation/segments/`에서 게임 경로에 대응하는 `.jsonl`을 연다. 각 줄의 `text`가 현재 개선판 문안이다. `text`와 `review`를 편집한다. `baseline_text`, `id`, `offset`, `raw_hex` 등 보호 필드는 그대로 둔다.
2. 이 폴더에서 `./build.ps1`을 실행한다. 일반 Python은 `python src/build.py`로 실행해도 된다. 빌드 자체는 Python 표준 라이브러리만 사용한다.
3. `out/sakura_wars_4_kr_dev.dcp`를 Universal Dreamcast Patcher로 지원 원본에 적용한다. 실행 확인 결과는 산출물 해시와 함께 기록한다.

현재 편집기는 **기존 문자열의 바이트 용량 이내 수정**을 지원한다. 길이 초과·기존 폰트에 없는 한글은 조용히 건너뛰지 않고 중단한다. 길이 확장과 신규 글리프 추가는 후속 구현 대상으로 남겼다. `@...`, `/`, `//` 등 제어 표기는 보존한다.

## 어디를 수정하는가

| 경로 | 내용 |
|---|---|
| `assets/translation/segments/` | 개선판에서 복원한 편집용 텍스트 40,338개. 본편·전투·음성 자막·메뉴를 게임 경로로 분류 |
| `assets/translation/index.json` | 주 빌드가 읽는 문안 파일 목록과 검토 상태 |
| `assets/images/native/` | 개선판 게임 내장 이미지·모델·관련 색인. 기존 Flycast 텍스처와 별개 |
| `assets/video/native/` | 개선판에 포함된 동영상 32개 |
| `assets/images/previews/`, `docs/images.html` | 구 추출물. 새 결과는 `assets/extracted/` 참고 |
| `assets/fonts/` | 개선판 글꼴 4종, 기존 글꼴 원천 및 매핑 |
| `src/build.py`, `build.ps1` | 개선판 기준선 + 현재 편집 내용을 합성하는 주 빌드 |
| `config/` | 입력 해시·보호 텍스트 경계·반각 인코딩 등 채택 설정 |
| `originals/v05/` | DCP에서 꺼낸 변경 불가 기준선 232개 파일 |
| `originals/disc/`, `originals/extracted/` | 기존 폴더의 원본 자료 사본. 실제 지원 이미지 검증은 별도 필요 |
| `research/legacy/` | 구 도구·번역 템플릿·원문·Flycast 텍스처·번역 지침. 참고 및 이식용 |
| `research/` | 비교표, 복원 근거, 제외 후보, 변환하지 못한 자산 목록 |
| `docs/status.md` | 현재 통합 상태와 남은 조건 |

이미지는 `native` 파일을 교체하면 다음 빌드에 반영한다. 미리보기 PNG를 바꾸는 것만으로 게임에 반영되지는 않는다. BPV1·모델 내부 이미지는 PNG로, 영상은 MP4로 추출했다. 열람 경로는 아래 이미지·영상 확인 절을 참고한다. PNG→게임 파일 재삽입기는 아직 통합하지 않았다.

## 확인된 범위

- 무편집 빌드의 DCP 내부 파일 232개가 지정한 개선판의 내부 파일과 전부 일치한다. ZIP 컨테이너 자체 해시는 압축 설정·메타데이터 때문에 달라진다.
- 기존 한글 1,200개 타일은 개선판의 네 글꼴과 모두 일치한다. 추가 글리프 8개를 타일과 문맥으로 복원했다.
- 입력 불일치, 보호 필드 변경, ID 누락·중복, 쓰기 겹침, 길이 초과, 미등록 변경을 중단한다.
- `python -m unittest discover -s tests -v`로 빌드 검증 테스트를 실행한다.

이는 **최신 결과물을 보존한 후속 개발 기준선**이다. 닉넴이다님이 작성한 원래 어셈블리/이미지 편집 원본까지 복원한 것은 아니다. 반각 표시와 기타 실행 코드 변경은 최신 `1ST_READ.BIN` 안에 보존되어 있으며, 해당 구현을 소스에서 재조립하는 작업은 별도로 필요하다. 정적 동일성은 플레이 검증이나 번역 검수를 대신하지 않는다.

텍스트의 `source`는 구 자료의 바이트를 CP932로 읽은 참고 값이다. 게임의 독자 글리프 배치 때문에 일본어처럼 보여도 실제 원문과 다를 수 있으므로 번역 원문으로 확정하지 않는다. 원문 확인에는 `research/legacy/original_txt/`와 기존 번역 지침을 함께 대조한다. 자동 스캔 잡음 19개는 편집 대상에서 제외하고 바이너리 그대로 보존했다.

## 출처

- 기존 프로젝트: TAMTAMQ/sakura-wars-4-korean-translation-patch
- 최신 입력: [v0.5 닉넴이다님 개선판](https://github.com/TAMTAMQ/sakura-wars-4-korean-translation-patch/releases/tag/v0.5-nickname)
- 기준 파일: `sakura_wars_4_kr_v0.5_nickname_improved.dcp` (v2/v3와 섞지 않음)
- 원작 게임·기존 패치·개선 작업의 권리와 크레딧은 원저작자에게 있다. 기존 프로젝트 라이선스는 `research/legacy/LICENSE`에 보존한다.

## 이미지·영상 확인 (2026-10-20 보완)

**[이미지·영상 목록 열기](assets/extracted/index.html)** — 파일명 검색, 변경 이미지 필터, 원본과 개선판 비교, MP4 재생.

- `assets/extracted/images/`: 66개 파일의 변경 블록에서 텍스처 313개 추출. 픽셀 변경 269개이며 모두 원본 대응 이미지를 확인했다. byte가 동일한 내부 블록 3,637개는 중복 추출하지 않았다.
- `assets/extracted/videos/`: 수정 SFD 32개를 오디오 포함 MP4로 변환. 각 영상에 12장 장면 요약과 스트림 메타데이터를 제공하며 전체 디코딩을 검증했다.
- `assets/extracted/fonts/`: 글꼴 4종의 전체 타일 PNG.
- `research/media-coverage.csv`: 기준선 232개 파일 전부의 처리 분류와 추출 수. `research/media-verification.json`: 검증 결과.

ADCG의 타일 좌표·상대 포인터와 Dreamcast twiddle 순서를 바로잡고, 압축/비압축 BPV1·ADCG 및 VQ를 처리했다. `.ESM` 내부 텍스처까지 포함한다. 이전 `assets/images/previews/`는 잘못된 배치를 포함하는 구 추출물이므로 새 `assets/extracted/`를 사용한다. PNG/MP4는 확인용이며 편집 내용을 native 게임 데이터로 되돌리는 작업은 별도다.
