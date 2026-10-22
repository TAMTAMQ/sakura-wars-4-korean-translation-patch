# 복원과 참고 자료

`file-comparison.csv`는 개선판·기존 DISC·구 output의 파일별 해시다. `migration-summary.json`은 정리 결과, `coverage.json`은 최초 추출 범위, `image-index.json`은 PNG와 미변환 자산 목록이다. 현재 문안 모집단은 `assets/translation/index.json`이 소유한다.

`rejected-text-candidates.json`은 이진 제어 바이트가 들어 있어 편집 대상에서 제외한 19개 스캔 후보다. 해당 byte는 기준선에 그대로 남아 있다. `unknown-glyphs.png`는 기존 매핑에 없던 타일의 눈으로 확인한 근거다.

`legacy/`는 구 작업 전체의 참고 소스다. `translate_all.py`를 이 프로젝트 루트로 복사해 주 빌드로 사용하지 않는다. 현재 문안은 `assets/translation/units/`에서 관리하며, 출현 위치인 `segments/`에는 문안을 복사하지 않는다. 구 템플릿에서 문안을 옮길 때는 `src/dialogue.py find`로 기존 공유 문안과 모든 사용처를 먼저 확인한다. 상세는 `docs/dialogue-management.md`를 참고한다.

`src/prepare_workspace.py`, `src/finalize_recovery.py`는 초기 이관 도구다. 주 빌드에서 자동 실행하지 않는다. 보호 기준선이나 현재 문안 편집을 덮어쓸 수 있으므로 통상 작업에서는 다시 실행하지 않는다.
