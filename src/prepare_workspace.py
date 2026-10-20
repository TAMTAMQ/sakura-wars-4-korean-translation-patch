"""복원 자료의 보호 필드 고정 및 이미지 열람용 추출. 빌드에서는 실행하지 않는다."""
import json, sys, re, struct, hashlib, html
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from extract_cbd_images import decompress_adcg_block, render_adcg_image
from extract_cg_all import find_entries
ROOT=Path(__file__).resolve().parents[1]

def main():
    bindings={}
    for p in (ROOT/'assets/translation/segments').rglob('*.jsonl'):
        for line in p.read_text(encoding='utf-8').splitlines():
            r=json.loads(line)
            bindings[r['id']]={k:v for k,v in r.items() if k not in ['text','review','source']}
    (ROOT/'config/text-bindings.json').write_text(json.dumps(bindings,ensure_ascii=False),encoding='utf-8')
    previews=[]; issues=[]
    for path in (ROOT/'assets/images/native').rglob('*'):
        if not path.is_file(): continue
        rel=path.relative_to(ROOT/'assets/images/native').as_posix(); raw=path.read_bytes()
        original=ROOT/'originals/disc'/rel
        old=original.read_bytes() if original.exists() else b''
        positions=find_entries(raw) if raw[:4]==b'AGR1' else ([0] if raw[:4]==b'ADCG' else [])
        oldpos=find_entries(old) if old[:4]==b'AGR1' else ([0] if old[:4]==b'ADCG' else [])
        for i,pos in enumerate(positions):
            offset=pos+8 if raw[:4]==b'AGR1' else pos
            size=struct.unpack_from('<I',raw,offset+12)[0]+16
            oo=(oldpos[i]+8 if old[:4]==b'AGR1' else oldpos[i]) if i<len(oldpos) else None
            if oo is not None and raw[offset:offset+size]==old[oo:oo+size]: continue
            try:
                dec=decompress_adcg_block(raw,offset); img,err=render_adcg_image(dec,rel)
                if img is None: raise ValueError(err)
                output=ROOT/'assets/images/previews'/(rel+f'.{i:04d}.png')
                output.parent.mkdir(parents=True,exist_ok=True); img.save(output)
                previews.append({'native':rel,'record':i,'offset':offset,'preview':output.relative_to(ROOT).as_posix(),'size':img.size})
            except Exception as exc: issues.append({'native':rel,'record':i,'error':str(exc)})
        if not positions:
            issues.append({'native':rel,'signature':raw[:4].hex(),'status':'네이티브 자산으로 통합; PNG 변환기 미구현'})
    (ROOT/'research/image-index.json').write_text(json.dumps({'previews':previews,'unconverted':issues},ensure_ascii=False,indent=2),encoding='utf-8')
    body=['<!doctype html><meta charset="utf-8"><title>사쿠라대전 4 복원 이미지</title><style>body{font-family:Malgun Gothic;background:#202126;color:#eee}img{max-width:480px}figure{display:inline-block;vertical-align:top;max-width:500px}figcaption{overflow-wrap:anywhere}</style><h1>개선판 이미지 열람</h1><p>PNG는 확인용입니다. 빌드는 assets/images/native의 게임 내장 파일을 사용합니다.</p>']
    for entry in previews:
        body.append('<figure><img loading="lazy" src="../'+html.escape(entry['preview'])+'"><figcaption>'+html.escape(entry['native'])+' #'+str(entry['record'])+'</figcaption></figure>')
    (ROOT/'docs/images.html').write_text('\n'.join(body),encoding='utf-8')
    print(json.dumps({'bindings':len(bindings),'previews':len(previews),'unconverted':len(issues)},ensure_ascii=False),flush=True)

if __name__=='__main__': main()
