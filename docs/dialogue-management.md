# 공유 대사 편집

이관 이후 대사 교정 및 미검수 범위는 [2026-10-22 대사 검수 기록](dialogue-review-20261022.md)을 참고한다. 아래의 ‘문안 변경 없음’과 DCP 동일성 검사는 구조 이관 당시의 기록이며, 이후 번역 교정까지 문안이 같아야 한다는 뜻이 아니다.

일반 대사·음성 자막·전투 대사의 같은 원문을 하나의 공유 문안으로 관리한다. `assets/translation/units/`가 편집 권위본이고, `segments/`는 파일별 적용 위치·원본 byte·용량·공유 문안 참조만 보관한다. 파일별 번역 사본을 동기화하는 준비 단계 없이 주 빌드가 공유 문안을 직접 읽는다.

갤럭시엔젤의 `assets/translation/battle/battle_unique.json`과 `battle_units.json`에서 사용한 문안/출현 위치 분리 방식을 참고했다. 템플릿의 `assets/translation/README.md`는 의미 단위 관리와 ID·참조·모집단 검증 원칙을 제공하며, 사쿠라대전의 실제 형식 연결은 이번에 추가했다.

## 검색하고 수정하기

```powershell
python src/dialogue.py find '급할수록'
python src/dialogue.py show 'ADVDATA/LIPSYNC2.LIP#1993'
python src/dialogue.py show 'phrase:kayama-haste'
```

검색 결과의 `path`에서 `text`와 `review`를 편집하거나 다음 명령으로 저장한다.

```powershell
python src/dialogue.py edit 'phrase:kayama-haste' --text '급할수록 돌아가라'
python src/dialogue.py validate
python src/build.py
```

카야마의 속담은 `units/phrases.jsonl`의 `phrase:kayama-haste` **한 곳에서만** 편집한다. 일반 대사 S0210 #0181과 음성 자막 LIPSYNC2 #1993은 같은 문안을 참조한다. 후반 퀴즈 S0510 #1381도 같은 속담 구절을 조합한다. 부모 문안의 `parts`는 문장 틀과 `ref`로 이루어지므로 인용 구절을 따로 복사하지 않는다.

`segments/`의 `baseline_text`는 v0.5 byte를 해석한 보호 기준선이다. 현재 번역이 아니며 수정하지 않는다. `source`는 추출 당시 참고 원문, `prior_review`는 이관 전의 사용처별 검수 메모다. 일부 원문은 독자 글리프 때문에 정확한 일본어가 아니므로, 단순히 비슷해 보인다는 이유로 다른 문안을 합치지 않는다.

## 같은 원문인데 말투나 배치가 다른 경우

원문의 줄바꿈·공백 및 확인된 `⊇`/`曰`, `∈`/`！` 표기 차이는 동일 원문 판별에서 제외했다. 카야마의 속담은 직접 대조한 한자/가나 표기 차이도 명시적으로 연결했다. 의미 유사도만으로 다른 문장을 병합하지 않는다. 원문을 복원하지 못한 항목은 개별 ID로 유지한다.

‘了解！’처럼 같은 원문도 화자에 따라 ‘알았어’와 ‘알겠습니다’가 필요할 수 있다. 같은 공유 대사 안의 `variants`로 기존 차이를 보존한다. 같은 번역을 쓰는 사용처는 같은 변형을 참조한다. 줄바꿈만 다른 변형은 번역문을 복사하지 않고 `breaks`로 분리한다.

변형의 `base_text_sha256`는 이 변형이 어느 대표 문안을 기준으로 했는지 나타낸다. 사람 검수 승인 표시가 아니다. 대표 문안이나 참조 구절이 달라지면 빌드는 기존 변형을 조용히 유지하지 않고 **관련 변형 재검토 필요**로 중단한다. 문맥과 모든 사용처를 확인한 후 지정한 변형을 수정한다.

```powershell
python src/dialogue.py show 'dialogue:공유ID'
python src/dialogue.py edit 'dialogue:공유ID' --variant v001 --text '확인한 변형 문안'
# 줄바꿈 전용 변형이라면 대표 문안에서 //를 뺀 글자 인덱스를 지정한다.
python src/dialogue.py edit 'dialogue:공유ID' --variant v001 --breaks '8,16'
```

`edit`는 대표 문안이나 명시한 변형만 변경하며 검토 상태를 ‘교차 검토 필요’로 둔다. 변형을 편집하면 그때의 대표 문안 지문도 함께 갱신한다. `find`와 `show`는 재검토가 필요한 상태에서도 열 수 있다. 사용처 한 곳이라도 가용 바이트를 넘으면 전체 빌드가 실패하며, 정상 패치로 부분 반영하지 않는다.

## 이관 결과와 남은 검토

- 기존 출현 ID 40,338개 → 공유 문안 23,029개. 실제 게임 파일의 모든 ID·offset·raw byte·가용 길이는 유지했다.
- 공유 문안 7,617개가 여러 사용처 24,927곳에 연결된다.
- 기존 번역 차이가 있는 공유 문안 1,727개는 변형으로 보존했다. 이 중 1,692개는 어휘·말투 차이 등이 있어 문맥 검토가 필요하고, 35개는 줄바꿈 차이만 있다. 이관이 이 번역 차이들의 검수 완료를 뜻하지 않는다.
- 이번 이관에서는 표시 문안을 한 글자도 바꾸지 않았다. 직전 개발 DCP와 최종 DCP 전체 SHA-256이 같아야 한다.

검증 명령:

```powershell
python -m unittest discover -s tests
python research/verify_shared_dialogue.py
```

검증기는 이전 문안 40,338개·보호 메타데이터·검수 메모 보존, 최종 DCP 전체 동일성, 빌드가 읽은 권위본/위치 파일 해시, 속담 한 곳 편집 시 일반 대사·음성 자막·퀴즈 세 사용처 동시 변경을 확인한다. 일반 대사·음성 대사·선택지의 여러 위치 재삽입, 용량 초과 시 출력 차단, 참조 누락·중복·순환, 파일별 사본 재도입, 오래된 변형 차단은 독립된 테스트로 확인한다.

전체 이관 수치: `research/shared-dialogue-migration.json`. 번역 차이 검토 목록: `research/dialogue-variant-review.json`. 이관 전 파일은 로컬 `work/issues/shared-dialogue/before-migration.zip`에 보존한다.

초기 복원 및 파일별 문안 편집 도구는 현재 권위본을 덮어쓰지 않도록 중단시켰다. 새 문안은 위 경로에서 편집한다.
