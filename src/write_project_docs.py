from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DOCS={
'README.md':'''# 사쿠라 대전 4 한국어 패치 — 후속 작업 프로젝트

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
| `assets/images/previews/`, `docs/images.html` | 변경 ADCG 이미지 65개 열람용 PNG 및 목록. 일부 부분 이미지의 배치는 미확정 |
| `assets/fonts/` | 개선판 글꼴 4종, 기존 글꼴 원천 및 매핑 |
| `src/build.py`, `build.ps1` | 개선판 기준선 + 현재 편집 내용을 합성하는 주 빌드 |
| `config/` | 입력 해시·보호 텍스트 경계·반각 인코딩 등 채택 설정 |
| `originals/v05/` | DCP에서 꺼낸 변경 불가 기준선 232개 파일 |
| `originals/disc/`, `originals/extracted/` | 기존 폴더의 원본 자료 사본. 실제 지원 이미지 검증은 별도 필요 |
| `research/legacy/` | 구 도구·번역 템플릿·원문·Flycast 텍스처·번역 지침. 참고 및 이식용 |
| `research/` | 비교표, 복원 근거, 제외 후보, 변환하지 못한 자산 목록 |
| `docs/status.md` | 현재 통합 상태와 남은 조건 |

이미지는 `native` 파일을 교체하면 다음 빌드에 반영한다. 미리보기 PNG를 바꾸는 것만으로 게임에 반영되지는 않는다. BPV1·모델·영상도 최신 바이너리는 모두 포함했으며 각 형식의 PNG→게임 파일 재삽입기는 아직 통합하지 않았다.

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
''',
'docs/status.md':'''# 현재 상태

2026-10-20. 대상은 Dreamcast 『사쿠라 대전 4』 일본판 v1.003. 작업 목적은 닉넴이다님 개선판을 이어 개발할 통합 프로젝트 확보다.

- 템플릿 최신 pull 완료: `c0e930286ccba37e6b83b9405a06e0b0ea4e6293`.
- 개선판 232개 게임 파일을 기준선에 채택. 구 소스는 참고 자료로 합쳤으며 최신 결과물을 덮어쓰는 구 빌드와 구분했다.
- 텍스트 40,338개 항목(134개 파일)을 편집 입력으로 등록. 반각 공백 플래그를 문안의 실제 공백으로 복원. 스캔 잡음 19개 제외.
- 이미지·영상·글꼴을 주 빌드에 함께 통합. ADCG PNG 65개를 열람용으로 추출. 모든 이미지의 변환·재삽입이 구현된 상태는 아니다.
- 무편집 재빌드: 232개 내부 파일 전부 기준선 byte 일치. 자세한 결과는 `out/build-report.json`.
- 검증 테스트 9개 통과. 에뮬레이터/실기 실행, 문안 사람 검수, 릴리스 승인은 하지 않았다.

남은 조건: 코드 수정의 어셈블리 원천 복원, 문자열 길이 확장, 신규 글리프 공급, BPV1 등 이미지 편집·재삽입기, 부분 ADCG의 정확한 배치. 이들이 없어도 기존 용량 이내 문안 수정과 네이티브 자산 교체를 시작할 수 있다.

다음 판별은 수정하려는 실제 문장이나 이미지 1개를 선택해 빌드·게임 소비까지 확인하는 것이다. 실제 원본 GDI/CDI의 해시는 아직 채택하지 않았으며, 로컬 DISC 사본의 존재만으로 지원 이미지 검증 완료를 주장하지 않는다.
''',
'docs/decisions.md':'''# 채택 결정

- 사용자 요청: 구 소스가 아닌 닉넴이다님 v0.5 개선판을 최신 기준으로 삼고, 최신 템플릿에 맞춰 후속 작업 프로젝트를 별도 폴더로 만든다.
- 지정한 `sakura_wars_4_kr_v0.5_nickname_improved.dcp`만 채택한다. 함께 있던 Region Free v3 등의 별도 후보를 혼합하지 않는다.
- 문안의 최신 값과 이미지/반각 구현은 DCP를 우선한다. 기존 소스와 자료는 삭제하지 않고 참고 위치에 보존한다.
- 원래 구현 소스가 없는 부분은 바이너리를 보존한다. 추정으로 기존 실행 코드를 대체하지 않는다.
- 이 작업은 새 번역이나 새 릴리스 승인을 포함하지 않는다. 내용 검수 상태는 교차 검토 필요로 시작한다.
''',
'config/README.md':'''# 채택 입력과 경계

`baseline.json`은 DCP SHA-256, 템플릿 커밋, 232개 기준 파일의 크기·SHA-256과 구 자료 비교 해시를 소유한다. 주 빌드는 매번 기준 파일 크기와 해시를 확인한다.

`text-bindings.json`은 복원한 문자열의 ID, 위치, 원본 raw byte, 가용 길이와 현재 문안 기준선을 소유한다. 정상 문안 편집에서는 수정하지 않는다. 새로운 경계 채택은 근거를 남기고 별도로 갱신한다. BIN 텍스트 경계는 기존 스캐너의 후보이므로 전체 모집단이 확정된 것으로 간주하지 않는다.

`encoding.json`은 글자→개선판 코드다. 기존 한글은 구 코드의 첫 바이트에 0x68을 더한 F0~F7 영역으로 옮겨졌으며, 첫 바이트의 0x08 비트는 그 글자 뒤 공백이다. 예: `사쿠라 군` = `f0a6 f0a7 f8a8 f0a9`. 이는 반복된 대사·레이블의 원문과 일치한다. 추가 타일 `f7ca~f7d1`은 `쭉 눴 엠 훙 멧 섞 뤼 …`다. `f7d1`은 공백이 아닌 말줄임표다. 타일 근거는 `research/unknown-glyphs.png`.

빌드는 무편집 항목을 재인코딩하지 않는다. 동일한 표시가 여러 원시 코드로 존재하므로 raw byte를 보존하는 것이 기준이다. 편집 시 등록 한글과 CP932 문자를 인코딩하고 기존 용량 안에서 NUL 패딩한다. 해당 슬롯 밖의 쓰기는 허용하지 않는다.

실행 파일은 기준선 그대로 소비한다. 데이터 슬롯 편집으로 실행 명령을 생성·이동하지 않으며, 원래 반각 구현의 어셈블리 원천은 아직 없다. 새로운 기계어 변경에는 별도 ISA 명세와 검산이 필요하다.

현재 적용 범위는 지정 DCP 하나다. 다른 수정본이나 폰트가 들어오면 해시·경계·인코딩 명세를 재검토한다.
''',
'assets/images/README.md':'''# 이미지 작업

`native/`의 게임 파일이 빌드 입력이다. 이미 번역된 최신 이미지가 게임 데이터 안에 통합되어 있다. `previews/` 및 `docs/images.html`은 확인용이며 빌드 입력이 아니다.

복원한 원본은 `originals/v05/`에 있다. 작업 중 native 파일을 바꿨다가 되돌리려면 같은 상대 경로의 기준선을 복사한다. PNG 변환기는 구 ADCG 해석을 사용하므로 일부 부분 타일의 배치는 틀릴 수 있다. BPV1, GRCT, BC, CSD 등 미변환 파일도 사라진 것이 아니라 네이티브로 보존되어 있다. 목록은 `research/image-index.json`.

구 Flycast 텍스처는 `research/legacy/texture/` 참고 자료다. 현재 빌드에 중복 주입하지 않는다. 이미지 편집 원본(레이어 등)은 DCP에서 복원되지 않는다.
''',
'assets/fonts/README.md':'''# 글꼴

`native/SKFONT*.CG` 4개가 최신 빌드 입력이다. `hangul_map.json`은 구 매핑의 타일 번호를 보존한 참고 원천이고 현재 문자열 코드는 `config/encoding.json`을 사용한다.

NotoSansKR-subset.ttf 및 라이선스를 함께 보존한다. 주 빌드는 폰트를 자동 재생성하지 않아 개선판 추가 글리프가 사라지지 않는다. 등록하지 않은 한글을 사용하면 빌드가 실패한다. 신규 글리프 추가는 네 폰트와 인코딩을 함께 갱신하는 후속 구현이 필요하다.
''',
'research/README.md':'''# 복원과 참고 자료

`file-comparison.csv`는 개선판·기존 DISC·구 output의 파일별 해시다. `migration-summary.json`은 정리 결과, `coverage.json`은 최초 추출 범위, `image-index.json`은 PNG와 미변환 자산 목록이다. 현재 문안 모집단은 `assets/translation/index.json`이 소유한다.

`rejected-text-candidates.json`은 이진 제어 바이트가 들어 있어 편집 대상에서 제외한 19개 스캔 후보다. 해당 byte는 기준선에 그대로 남아 있다. `unknown-glyphs.png`는 기존 매핑에 없던 타일의 눈으로 확인한 근거다.

`legacy/`는 구 작업 전체의 참고 소스다. `translate_all.py`를 이 프로젝트 루트로 복사해 주 빌드로 사용하지 않는다. 구 템플릿에서 문안을 복사할 때 최신 `text`를 먼저 대조한다. 기존 번역 수정은 하지 않았으며 최신 바이너리를 우선해 복원했다.

`src/prepare_workspace.py`, `src/finalize_recovery.py`는 초기 이관 도구다. 주 빌드에서 자동 실행하지 않는다. 보호 기준선이나 현재 문안 편집을 덮어쓸 수 있으므로 통상 작업에서는 다시 실행하지 않는다.
'''
}
def main():
    for path,text in DOCS.items():
        dest=ROOT/path; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_text(text,encoding='utf-8')
    with (ROOT/'.gitignore').open('a',encoding='utf-8') as f:
        f.write('\n# 로컬 게임 자산과 구 작업 백업\n/assets/images/native/\n/assets/images/previews/\n/assets/video/native/\n/assets/fonts/native/\n/research/legacy/\n*.dcp\n*.partial\n')
    video=ROOT/'assets/video/native'
    for path in (ROOT/'assets/images/native').rglob('*.SFD'):
        dest=video/path.relative_to(ROOT/'assets/images/native'); dest.parent.mkdir(parents=True,exist_ok=True); path.rename(dest)
if __name__=='__main__': main()
