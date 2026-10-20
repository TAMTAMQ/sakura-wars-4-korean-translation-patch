"""개선판 전체 파일에서 ADCG/BPV1 텍스처를 찾아 PNG로 추출한다."""
import json, re, struct, hashlib, collections
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from prs_decompress import DecompressPrs
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/extracted/images'
def digest(data): return hashlib.sha256(data).hexdigest()
def u32(d,o): return struct.unpack_from('<I',d,o)[0]
def decompress(payload,expected):
    # 시그니처가 압축 데이터에 우연히 나타난 경우도 제한 시간 대신 구조로 거부한다.
    data=memoryview(payload); out=bytearray(); pos=0; bits=0; command=0
    def byte():
        nonlocal pos
        if pos>=len(data): raise ValueError('PRS 입력 끝')
        v=data[pos]; pos+=1; return v
    def bit():
        nonlocal bits,command
        if not bits: command=byte(); bits=8
        v=command&1; command>>=1; bits-=1; return v
    while len(out)<expected:
        if bit(): out.append(byte()); continue
        if bit():
            a=byte(); b=byte(); offset=((b<<8)|a)>>3; amount=a&7
            if a==0 and b==0: break
            amount=byte()+1 if amount==0 else amount+2
            start=len(out)-0x2000+offset
        else:
            amount=(bit()<<1|bit())+2; start=len(out)-0x100+byte()
        if len(out)+amount>expected: raise ValueError('PRS 출력 크기 초과')
        for _ in range(amount):
            out.append(out[start] if 0<=start<len(out) else 0); start+=1
    if len(out)!=expected: raise ValueError('PRS 출력 크기 불일치')
    return bytes(out)
def rgba(v,fmt):
    v=v.astype(np.uint32)
    if fmt==0:
        return np.stack([((v>>10)&31)*255//31,((v>>5)&31)*255//31,(v&31)*255//31,(v>>15)*255],axis=-1).astype('uint8')
    if fmt==1:
        return np.stack([((v>>11)&31)*255//31,((v>>5)&63)*255//63,(v&31)*255//31,np.full(v.shape,255)],axis=-1).astype('uint8')
    if fmt==2:
        return np.stack([((v>>8)&15)*17,((v>>4)&15)*17,(v&15)*17,((v>>12)&15)*17],axis=-1).astype('uint8')
    raise ValueError('미지원 픽셀 포맷 '+str(fmt))
MORTON={}
def morton(w,h):
    if (w,h) in MORTON: return MORTON[w,h]
    y,x=np.indices((h,w)); n=min(w,h); idx=np.zeros((h,w),dtype=np.int64)
    for i in range(n.bit_length()-1): idx|=((y>>i)&1)<<(2*i); idx|=((x>>i)&1)<<(2*i+1)
    idx+=(x//n+y//n)*n*n
    MORTON[w,h]=idx; return idx
def texture(payload,w,h,pf,layout):
    if not 0<w<=4096 or not 0<h<=4096: raise ValueError('텍스처 크기 오류')
    if layout in (3,4,16,17):
        entries=256 if layout in (3,4) else (16 if w<=16 else 32 if w<=32 else 128 if w<=64 else 256)
        cb=np.frombuffer(payload[:entries*8],dtype='<u2').reshape(entries,4)
        codes=np.frombuffer(payload[entries*8:],dtype='uint8')
        if layout in (4,17): codes=codes[-w*h//4:]
        ids=codes[morton(w//2,h//2)]
        values=np.empty((h,w),dtype=np.uint16)
        for y in range(2):
            for x in range(2): values[y::2,x::2]=cb[ids,x*2+y]
    else:
        pix=np.frombuffer(payload[:len(payload)//2*2],dtype='<u2')
        if layout in (2,18): pix=pix[-w*h:]
        values=pix[morton(w,h)] if layout in (1,2,13,18) else pix[:w*h].reshape(h,w)
    return Image.fromarray(rgba(values,pf))
def blocks(raw):
    found=[]
    for match in re.finditer(b'BPV1|ADCG',raw):
        off=match.start(); sig=match.group()
        try:
            size,a,b=struct.unpack_from('<III',raw,off+4)
            if a==8 and sig==b'BPV1':
                dec=raw[off+8:off+8+size]
                if len(dec)!=size: raise ValueError('블록 범위 초과')
                compressed=False
            else:
                if not 0<b<=size<=len(raw)-off-16 or not 8<=a<=64*1024*1024: continue
                dec=decompress(raw[off+16:off+16+b],a)
                if len(dec)!=a: raise ValueError('압축 해제 크기 불일치')
                compressed=True
            if len(dec)<8: continue
            count=u32(dec,4)
            if not 0<count<20000: continue
            found.append((sig.decode(),off,dec,compressed))
        except (IndexError,ValueError,struct.error): continue
    return found
def block_specs(raw):
    result=[]
    for m in re.finditer(b'BPV1|ADCG',raw):
        off=m.start(); sig=m.group().decode()
        if off+16>len(raw): continue
        size,a,b=struct.unpack_from('<III',raw,off+4)
        if (sig=='BPV1' and a==8) or (sig=='ADCG' and a==0xc0000000):
            if 8<=size<=len(raw)-off-8: result.append((sig,off,raw[off+8:off+8+size],False,size))
        elif 0<b<=size<=len(raw)-off-16 and 8<=a<=64*1024*1024:
            result.append((sig,off,raw[off+16:off+16+b],True,a))
    return result
def decode_bpv(dec):
    count=u32(dec,4)
    if 8+count*12>len(dec): raise ValueError('BPV1 표 범위')
    result=[]
    descriptors=[u32(dec,8+i*12) for i in range(count)]
    for i,desc in enumerate(descriptors):
        data_off,mode=struct.unpack_from('<II',dec,desc)
        w,h=struct.unpack_from('<II',dec,desc+16)
        pf=(mode>>16)&255; layout=mode>>24
        if data_off>=len(dec): raise ValueError('픽셀 위치 오류')
        img=texture(dec[data_off:],w,h,pf,layout)
        result.append((i,img,{'width':w,'height':h,'pixel_format':pf,'layout':layout,'data_offset':data_off,'descriptor':desc}))
    return result
def decode_adcg(dec):
    count=u32(dec,4); tw,th=struct.unpack_from('<HH',dec,8); table=u32(dec,12)
    fw,fh=struct.unpack_from('<HH',dec,20)
    pf=dec[16]  # 0=ARGB1555, 1=RGB565, 2=ARGB4444. 스태프롤 등 대부분이 4444다
    if table+count*16>len(dec) or not 0<tw<=1024 or not 0<th<=1024: raise ValueError('ADCG 표 오류')
    if pf not in (0,1,2): raise ValueError('ADCG 픽셀 포맷 '+str(pf))
    canvas=Image.new('RGBA',(fw,fh),(0,0,0,0))
    for i in range(count):
        entry=table+i*16
        tileid,ptr,xy,flags=struct.unpack_from('<IIII',dec,entry)
        start=entry+ptr; x=xy&65535; y=xy>>16
        data=dec[start:start+tw*th*2]
        if len(data)!=tw*th*2: raise ValueError('ADCG 타일 범위')
        tile=texture(data,tw,th,pf,1)
        canvas.paste(tile,(x,y))
    return [(0,canvas,{'width':fw,'height':fh,'tiles':count,'tile_size':[tw,th],'pixel_format':pf})]
def main():
    outputs=[]; files=[]; errors=[]; modes=collections.Counter()
    for path in sorted((ROOT/'originals/v05').rglob('*')):
        if not path.is_file() or path.suffix.upper() in ('.SFD','.CG'): continue
        rel=path.relative_to(ROOT/'originals/v05').as_posix(); raw=path.read_bytes()
        if b'BPV1' not in raw and b'ADCG' not in raw: continue
        print('분석',rel,flush=True)
        bb=block_specs(raw)
        if not bb: continue
        op=ROOT/'originals/disc'/rel; old=op.read_bytes() if op.exists() else b''
        oldblocks=block_specs(old); total=0; changed=0; identical=0
        for bi,(sig,off,packed,compressed,expected) in enumerate(bb):
            if bi<len(oldblocks) and (sig,packed,compressed,expected)==(oldblocks[bi][0],oldblocks[bi][2],oldblocks[bi][3],oldblocks[bi][4]):
                identical+=1; continue
            try:
                dec=decompress(packed,expected) if compressed else packed
                decoded=decode_bpv(dec) if sig=='BPV1' else decode_adcg(dec)
                original=[]
                if bi<len(oldblocks) and oldblocks[bi][0]==sig:
                    try:
                        ob=oldblocks[bi]; od=decompress(ob[2],ob[4]) if ob[3] else ob[2]
                        original=decode_bpv(od) if sig=='BPV1' else decode_adcg(od)
                    except Exception: pass
                for ti,img,meta in decoded:
                    total+=1; modes[(sig,meta.get('pixel_format'),meta.get('layout'))]+=1
                    oldimg=original[ti][1] if ti<len(original) else None
                    visual_changed=oldimg is None or oldimg.size!=img.size or oldimg.tobytes()!=img.tobytes()
                    # 모든 블록을 저장한다. 실제 변경 여부는 색인으로 구분한다.
                    folder=OUT/rel/f'{bi:04d}_{sig}'
                    folder.mkdir(parents=True,exist_ok=True)
                    target=folder/f'{ti:04d}_patched.png'; img.save(target)
                    before=None
                    if oldimg is not None and visual_changed:
                        before=folder/f'{ti:04d}_original.png'; oldimg.save(before)
                    if visual_changed: changed+=1
                    row={'source':rel,'block':bi,'texture':ti,'signature':sig,'offset':off,'compressed':compressed,
                         'changed':visual_changed,'original_comparison_available':oldimg is not None,
                         'png':target.relative_to(ROOT).as_posix(),'original_png':before.relative_to(ROOT).as_posix() if before else None,
                         'pixel_sha256':digest(img.tobytes()),**meta}
                    outputs.append(row)
            except Exception as exc: errors.append({'source':rel,'block':bi,'signature':sig,'offset':off,'error':str(exc)})
        files.append({'source':rel,'blocks':len(bb),'identical_blocks_omitted':identical,'textures':total,'changed_textures':changed})
        print(rel,'텍스처',total,'변경',changed,flush=True)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'index.json').write_text(json.dumps({'files':files,'textures':outputs,'errors':errors,'modes':{str(k):v for k,v in modes.items()}},ensure_ascii=False,indent=2),encoding='utf-8')
    print('완료',len(files),len(outputs),'변경',sum(r['changed'] for r in outputs),'오류',len(errors),flush=True)
if __name__=='__main__': main()
