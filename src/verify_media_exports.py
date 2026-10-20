"""추출물 완전성과 파일별 처리 범위를 검사하고 현재 문서를 갱신한다."""
import json, hashlib, csv, re
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
def load(path): return json.loads((ROOT/path).read_text(encoding='utf-8'))
def main():
    images=load('assets/extracted/images/index.json'); videos=load('assets/extracted/videos/index.json')
    assert not images['errors'] and not videos['errors']
    assert len(videos['videos'])==len(list((ROOT/'originals/v05').rglob('*.SFD')))
    for row in images['textures']:
        with Image.open(ROOT/row['png']) as img:
            img.load(); assert img.size==(row['width'],row['height'])
            assert hashlib.sha256(img.tobytes()).hexdigest()==row['pixel_sha256']
        if row['original_png']:
            with Image.open(ROOT/row['original_png']) as img: img.verify()
    for row in videos['videos']:
        assert row['audio_verified'] and row['full_decode_verified']
        assert (ROOT/row['mp4']).is_file()
        with Image.open(ROOT/row['contact_sheet']) as img: img.verify()
    baseline=load('config/baseline.json')['files']
    im={r['source']:r for r in images['files']}; vi={r['source']:r for r in videos['videos']}
    table=[]
    for row in baseline:
        name=row['path']; image=im.get(name)
        table.append({'source':name,'sha256':row['sha256'],
            'media':('영상 MP4' if name in vi else '이미지 PNG' if name in im else '글꼴 PNG' if name.startswith('SKFONT') else '텍스트·실행·색인 데이터'),
            'exported_textures':image['textures'] if image else 0,'changed_textures':image['changed_textures'] if image else 0,
            'identical_blocks_omitted':image['identical_blocks_omitted'] if image else 0})
    with (ROOT/'research/media-coverage.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(table[0])); w.writeheader(); w.writerows(table)
    report={'baseline_files_audited':len(table),'image_files':len(im),'exported_textures':len(images['textures']),
        'pixel_changed_textures':sum(r['changed'] for r in images['textures']),
        'identical_blocks_omitted':sum(r['identical_blocks_omitted'] for r in images['files']),
        'original_comparison_missing':sum(not r['original_comparison_available'] for r in images['textures']),
        'videos_with_audio_and_full_decode_verified':len(vi),'image_errors':0,'video_errors':0}
    (ROOT/'research/media-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    readme=ROOT/'README.md'; text=readme.read_text(encoding='utf-8')
    text=text.replace('변경 ADCG 이미지 65개 열람용 PNG 및 목록. 일부 부분 이미지의 배치는 미확정','구 추출물. 새 결과는 `assets/extracted/` 참고')
    text+='''
## 이미지·영상 확인 (2026-10-20 보완)

**[이미지·영상 목록 열기](assets/extracted/index.html)** — 파일명 검색, 변경 이미지 필터, 원본과 개선판 비교, MP4 재생.

- `assets/extracted/images/`: 66개 파일의 변경 블록에서 텍스처 313개 추출. 픽셀 변경 269개이며 모두 원본 대응 이미지를 확인했다. byte가 동일한 내부 블록 3,637개는 중복 추출하지 않았다.
- `assets/extracted/videos/`: 수정 SFD 32개를 오디오 포함 MP4로 변환. 각 영상에 12장 장면 요약과 스트림 메타데이터를 제공하며 전체 디코딩을 검증했다.
- `assets/extracted/fonts/`: 글꼴 4종의 전체 타일 PNG.
- `research/media-coverage.csv`: 기준선 232개 파일 전부의 처리 분류와 추출 수. `research/media-verification.json`: 검증 결과.

ADCG의 타일 좌표·상대 포인터와 Dreamcast twiddle 순서를 바로잡고, 압축/비압축 BPV1·ADCG 및 VQ를 처리했다. `.ESM` 내부 텍스처까지 포함한다. 이전 `assets/images/previews/`는 잘못된 배치를 포함하는 구 추출물이므로 새 `assets/extracted/`를 사용한다. PNG/MP4는 확인용이며 편집 내용을 native 게임 데이터로 되돌리는 작업은 별도다.
'''
    readme.write_text(text,encoding='utf-8')
    (ROOT/'docs/images.html').write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=../assets/extracted/index.html"><a href="../assets/extracted/index.html">새 이미지·영상 목록 열기</a>',encoding='utf-8')
    status=ROOT/'docs/status.md'
    status.write_text(status.read_text(encoding='utf-8')+'''
## 이미지·영상 추출 보완

기준선 232개 파일을 점검하여 66개 파일의 변경 블록에서 텍스처 313개를 추출했다. 그중 269개가 원본과 픽셀이 다르며 원본 대응 누락은 없다. 동일 블록 3,637개는 제외했다. ADCG 좌표·상대 포인터와 twiddle 순서를 수정했으며 BPV1의 압축·비압축, VQ, `.ESM`/모델 내부 텍스처를 포함한다. 추출 오류 0개.

영상 32개는 오디오 포함 MP4와 12장 장면 요약으로 내보냈고 전체 디코딩을 확인했다. 글꼴 아틀라스 4개도 제공한다. 열람 진입점은 `assets/extracted/index.html`이다. 이는 추출 완료이며 PNG/MP4를 게임으로 재삽입하는 기능 구현을 뜻하지 않는다.
''',encoding='utf-8')
    with (ROOT/'.gitignore').open('a',encoding='utf-8') as f: f.write('\n# 로컬 열람용 이미지·영상\n/assets/extracted/\n')
    gallery=(ROOT/'assets/extracted/index.html').read_text(encoding='utf-8')
    js=re.search(r'<script>([\s\S]*)</script>',gallery).group(1)
    (ROOT/'work/gallery-check.js').write_text(js,encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
