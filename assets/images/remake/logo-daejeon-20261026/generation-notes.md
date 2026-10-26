# 로고 제작 기록

- 방식: 내장 image_gen 편집. 원본 CG_ALL1 b733을 스타일 참조로 사용.
- 생성 원천: assets/images/remake/logo-daejeon-20261026/daejeon-generated.png
- 생성 원천을 고정 [140,90,1735,810]으로 자르고 마스터 [200,55,408,166]에 배치. 글자 외곽별 분할 없음.
- 128색 변환 후 원래 ARGB4444/RGB565 등 게임 형식에 양자화. 원본 타일 좌표 밖으로 나가지 않게 확인.
- 이전 로고 8개는 before/에 보존. 새 본문에 작은 읽기 상자를 사용하지 않는다.
- 풍림화산은 사용자 요청대로 원본 한자를 유지한다. 관련 시안은 폐기했고 주 빌드에 포함하지 않는다.

## 최종 생성 프롬프트

Use case: text-localization. Input image is a style reference for the original Sakura Wars 4 logo. Generate ONLY a standalone Korean lettering sprite reading exactly '대전' (two syllables, left 대 right 전). Do not generate 사쿠라, the numeral 4, Latin text, Japanese kanji, reading plaques, black rectangular boxes, backgrounds, or other words. The lettering must replace the original purple 大戦 as the MAIN title lettering, not as small captions. Match the reference's thick energetic brush-cut strokes, slightly slanted irregular silhouettes, rich violet/purple marbled glossy fill, thin black inner outline and narrow off-white outer outline. Make 대 and 전 equally prominent at the original kanji's visual scale, connected as a cohesive game wordmark with open counters and perfectly legible Hangul. Add a small pair of pink cherry blossom petals above the upper right of 전 as in the original reference. No large cast shadow, no gold bevels. Actual transparent RGBA background with generous clear margin around the complete outlines. Compose just these two lettering glyphs horizontally in a roughly 2:1 ratio suitable for reducing to 202x114 pixels. This is a clean isolated insert layer; everything outside the glyphs and small petals is transparent.
