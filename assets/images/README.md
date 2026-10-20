# 이미지 작업

`native/`의 게임 파일이 빌드 입력이다. 이미 번역된 최신 이미지가 게임 데이터 안에 통합되어 있다. `previews/` 및 `docs/images.html`은 확인용이며 빌드 입력이 아니다.

복원한 원본은 `originals/v05/`에 있다. 작업 중 native 파일을 바꿨다가 되돌리려면 같은 상대 경로의 기준선을 복사한다.

현재 확인용 추출 결과는 `assets/extracted/images/`에 있다. BPV1, GRCT, BC, CSD와 ESM 내부 텍스처까지 추출했다. 전체 목록과 원본 비교는 `assets/extracted/index.html`, 파일별 처리 범위는 `research/media-coverage.csv`를 사용한다. 이전 `previews/`와 `research/image-index.json`은 구 ADCG 해석으로 만든 과거 자료이며 잘못된 배치를 포함할 수 있다.

구 Flycast 텍스처는 `research/legacy/texture/` 참고 자료다. 현재 빌드에 중복 주입하지 않는다. 이미지 편집 원본(레이어 등)은 DCP에서 복원되지 않는다.
