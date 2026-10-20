import json, html
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/extracted'
def main():
    images=json.loads((OUT/'images/index.json').read_text(encoding='utf-8'))
    videos=json.loads((OUT/'videos/index.json').read_text(encoding='utf-8'))
    fonts=json.loads((OUT/'fonts/index.json').read_text(encoding='utf-8'))
    items=images['textures']; changed=[r for r in items if r['changed']]
    summary={'image_files':len(images['files']),'image_textures':len(items),'changed_textures':len(changed),
             'image_errors':len(images['errors']),'videos':len(videos['videos']),'video_errors':len(videos['errors']),
             'font_atlases':len(fonts)}
    payload=json.dumps({'images':items,'videos':videos['videos'],'fonts':fonts,'errors':images['errors']},ensure_ascii=False).replace('</','<\\/')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>사쿠라 대전 4 — 이미지·영상 확인</title>
<style>body{background:#16191d;color:#eee;font:16px 'Malgun Gothic',sans-serif;margin:24px}button,input,select{padding:10px;margin:5px;background:#292e36;color:white;border:1px solid #667}article{border:1px solid #555;padding:12px;margin:12px 0;overflow:auto}h3{overflow-wrap:anywhere}img{max-width:640px;max-height:480px;object-fit:contain;background:repeating-conic-gradient(#ddd 0% 25%,#aaa 0% 50%) 50%/16px 16px}figure{display:inline-block;vertical-align:top;margin:8px}video{max-width:640px;max-height:480px}a{color:#9fcaff}small{color:#c0c9d5}.bar{position:sticky;top:0;background:#16191df0;padding:8px}figcaption{padding:6px}</style>
<h1>사쿠라 대전 4 개선판 — 이미지·영상 확인</h1><p id="summary"></p>
<p>기본 목록은 원본과 픽셀이 달라진 이미지입니다. 원본이 없거나 대응하지 못한 항목은 비교 불가로 표시합니다. PNG·MP4는 열람용이며 주 빌드는 native 게임 파일을 사용합니다.</p>
<div class="bar"><select id="type"><option value="images">이미지</option><option value="videos">영상</option><option value="fonts">글꼴</option><option value="errors">추출 오류</option></select><input id="search" placeholder="파일명 검색"><label><input type="checkbox" id="changed" checked>변경 이미지만</label><button id="prev">이전</button><button id="next">다음</button><span id="count"></span></div><main id="list"></main>
<script>const data=PAYLOAD;let page=0;const size=20;const el=id=>document.getElementById(id);const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const path=p=>'../../'+p;function draw(){const kind=el('type').value,q=el('search').value.toLowerCase();let rows=data[kind].filter(r=>(r.source||'').toLowerCase().includes(q));if(kind==='images'&&el('changed').checked)rows=rows.filter(r=>r.changed);page=Math.min(page,Math.max(0,Math.ceil(rows.length/size)-1));el('count').textContent=`${rows.length}개 · ${page+1}/${Math.max(1,Math.ceil(rows.length/size))} 페이지`;el('list').innerHTML=rows.slice(page*size,(page+1)*size).map(r=>{if(kind==='videos')return `<article><h3>${escape(r.source)}</h3><p>${r.duration.toFixed(2)}초 · 오디오 ${r.audio_verified?'확인':'없음'} · 전체 디코딩 확인</p><video controls preload="none" src="${path(r.mp4)}"></video><p><a href="${path(r.mp4)}">MP4 열기</a></p><img loading="lazy" src="${path(r.contact_sheet)}"></article>`;if(kind==='fonts')return `<article><h3>${escape(r.source)}</h3><p>${r.tiles}개 타일 · 변경 ${r.changed_tiles.length}개</p><a href="${path(r.atlas)}"><img loading="lazy" src="${path(r.atlas)}"></a></article>`;if(kind==='errors')return `<article><h3>${escape(r.source)}</h3><pre>${escape(JSON.stringify(r,null,2))}</pre></article>`;return `<article><h3>${escape(r.source)} / 블록 ${r.block} / 텍스처 ${r.texture}</h3><small>${r.signature} · ${r.width}×${r.height} · ${r.original_comparison_available?(r.changed?'픽셀 변경':'픽셀 동일'):'원본 대응 없음 · 비교 불가'}</small><div>${r.original_png?`<figure><a href="${path(r.original_png)}"><img loading="lazy" src="${path(r.original_png)}"></a><figcaption>기존 원본</figcaption></figure>`:''}<figure><a href="${path(r.png)}"><img loading="lazy" src="${path(r.png)}"></a><figcaption>v0.5 개선판</figcaption></figure></div></article>`}).join('')}['type','search','changed'].forEach(id=>el(id).addEventListener('input',()=>{page=0;draw()}));el('prev').onclick=()=>{page=Math.max(0,page-1);draw()};el('next').onclick=()=>{page++;draw()};el('summary').textContent=SUMMARY;draw();</script></html>'''
    page=page.replace('PAYLOAD',payload).replace('SUMMARY',json.dumps(f"이미지 {len(items):,}개 / 변경·비교대상 {len(changed):,}개 / 영상 {len(videos['videos'])}개 / 글꼴 {len(fonts)}개 / 이미지 추출 오류 {len(images['errors'])}개",ensure_ascii=False))
    (OUT/'index.html').write_text(page,encoding='utf-8')
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'README.md').write_text('''# 이미지·영상 추출 결과

`index.html`을 브라우저로 열면 파일명 검색, 변경 이미지 필터, 원본 비교, 영상 재생을 할 수 있다.

- `images/`: DCP의 ADCG/BPV1 이미지. 컨테이너 경로 / 블록 번호 / 텍스처 번호로 저장. `*_patched.png`는 최신 이미지, `*_original.png`는 대응하는 기존 원본이다. 변경하지 않은 내부 텍스처도 보관한다.
- `videos/`: SFD 32개의 소리 있는 MP4, 12장 장면 요약, 스트림 정보. MP4를 끝까지 디코딩해 검증했다. 원래 해상도를 보존했다.
- `fonts/`: 최신 글꼴 4종의 전체 타일 PNG 및 변경 타일 번호.
- 각 `index.json`과 `summary.json`은 실제 처리 수와 오류를 기록한다.

이는 확인용 추출물이다. PNG/MP4 편집을 게임 데이터에 재삽입하는 기능은 별도이며, 주 빌드는 기존 native 파일을 사용한다. 원본 비교 기준은 `originals/disc/`다. 비교 불가 표시는 변경 확정을 뜻하지 않는다.
''',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__': main()
