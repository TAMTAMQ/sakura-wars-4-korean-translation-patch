"""v0.5 통합 기준선에서 편집한 문안과 자산을 합성한다."""
import argparse, hashlib, json, os, re, shutil, struct, tempfile, zipfile
from pathlib import Path
from dialogue import SCHEMA, load as load_dialogue

ROOT=Path(__file__).resolve().parents[1]
def sha(data): return hashlib.sha256(data).hexdigest()
def readjson(path): return json.loads(path.read_text(encoding='utf-8'))
def safe(root,name):
    p=(root/name).resolve()
    if not p.is_relative_to(root.resolve()): raise ValueError('경로 이탈: '+name)
    return p

def encode(text,codes):
    out=bytearray(); i=0
    while i<len(text):
        if text.startswith('⟦',i):
            end=text.index('⟧',i); out+=bytes.fromhex(text[i+1:end]); i=end+1; continue
        ch=text[i]; i+=1
        if ch in codes:
            b=bytearray.fromhex(codes[ch])
            if i<len(text) and text[i]==' ': b[0]|=8; i+=1
            out+=b
        else: out+=ch.encode('cp932')
    if 0 in out: raise ValueError('문안에 NUL을 넣을 수 없습니다.')
    return bytes(out)

def sjis_glyphs(data):
    n=0;i=0
    while i<len(data):
        i+=2 if (0x81<=data[i]<=0x9f or data[i]>=0xe0) else 1; n+=1
    return n

def align_lip(text,codes,orig,pad):
    """여러 줄 대사의 각 줄이 일본어 원문의 해당 줄이 찍히던 칸에서 시작하도록 줄 끝에 빈 타일을 넣는다.
    줄 안의 글자·띄어쓰기는 그대로 둔다(보이는 모양이 번역과 같아야 한다). 맞출 수 없으면 None."""
    if '⟦' in text: return None
    lines=text.split('//'); jp=[sjis_glyphs(x) for x in orig.split(b'//')]
    if len(lines)<2: return None
    glyphs=[len(l)-sum(1 for i,ch in enumerate(l) if ch==' ' and i and l[i-1] in codes) for l in lines]
    width=max(jp); nK=sum(glyphs); nJ=sum(jp)
    if nK>=nJ: return None
    if len(lines)==len(jp) and all(k<=j for k,j in zip(glyphs,jp)): slots=jp
    else:
        # 줄 수가 다르면 줄 시작 칸을 글자 수 비례로 정한다
        slots=[]; seen=0
        for k,n in enumerate(glyphs):
            nxt=nJ if k==len(glyphs)-1 else round((seen+n)*nJ/nK)
            slots.append(min(width,max(n,nxt-round(seen*nJ/nK)))); seen+=n
    return b'//'.join(encode(l,codes)+pad*max(0,s-n) for l,n,s in zip(lines,glyphs,slots))

def build(root=ROOT,output=None,lip_align=False):
    manifest=readjson(root/'config/baseline.json')
    bindings=readjson(root/'config/text-bindings.json')
    index=readjson(root/'assets/translation/index.json')
    codes=readjson(root/'config/encoding.json')
    baseline={}
    # v0.5가 손대지 않은 파일은 원본 디스크가 기준선이다(예: 1화 연출 BT1의 제목 텍스처)
    extra=root/'config/disc-baseline.json'
    disc_items=[{**i,'origin':'disc'} for i in (readjson(extra)['files'] if extra.exists() else [])]
    for item in manifest['files']+disc_items:
        data=safe(root/'originals'/item.get('origin','v05'),item['path']).read_bytes()
        if len(data)!=item['size'] or sha(data)!=item['sha256']: raise ValueError('기준선 불일치: '+item['path'])
        baseline[item['path']]=data
    rows={}; segment_hashes={}; dialogue_info=None
    resolved=None
    if index.get('schema') not in (None,SCHEMA) or ('units' in index and index.get('schema')!=SCHEMA):
        raise ValueError('지원하지 않는 공유 대사 색인 형식')
    if index.get('schema')==SCHEMA:
        catalogue,resolved,segment_hashes=load_dialogue(root,index)
        dialogue_info={'units':len(catalogue.units),'occurrences':len(resolved),
                      'units_with_variants':sum(bool(u.get('variants')) for u in catalogue.units.values())}
    input_rows=list(resolved.values()) if resolved is not None else []
    if resolved is None:
        for seg in index['segments']:
            path=safe(root,seg['path']); data=path.read_bytes(); segment_hashes[seg['path']]=sha(data)
            input_rows.extend(json.loads(line) for line in data.decode('utf-8').splitlines() if line)
    for row in input_rows:
        key=row['id']
        if key in rows or key not in bindings: raise ValueError('중복 또는 미등록 ID: '+key)
        fixed=bindings[key]
        for field in fixed:
            if row.get(field)!=fixed[field]: raise ValueError('보호 필드 변경: '+key+' '+field)
        rows[key]=row
    if set(rows)!=set(bindings): raise ValueError('번역 ID 모집단 누락')
    # LIPSYNC: 표의 off_b가 대사 중간(원본은 마지막 4글자)을 가리킨다. v0.5는 모든 항목에서
    # 대사를 off_b까지 채웠다(짧게 끝나 off_b가 NUL 패딩을 가리키는 항목 0개). 짧아진 대사는
    # 보이지 않는 채움 문자(U+2063, 빈 타일)로 off_b까지 채운다.
    lip_offb={}
    for rel,data in baseline.items():
        if rel.endswith('.LIP'):
            count=struct.unpack_from('<I',data,8)[0]
            lip_offb[rel]=sorted(struct.unpack_from('<I',data,12+k*12+8)[0]-1 for k in range(count))
    pad=bytes.fromhex(codes['⁣']) if lip_offb else b''
    # 지역 해제: 원본 부트 섹터(IP.BIN)를 DCP의 bootsector/IP.BIN으로 넣는다(config/region-free.json)
    rf=root/'config/region-free.json'
    if rf.exists():
        rfc=readjson(rf); ip=safe(root,rfc['source'])
        if not ip.exists(): raise ValueError('원본 IP.BIN 없음: '+rfc['source']+' (원본 GDI track03 첫 16섹터)')
        data=ip.read_bytes()
        if len(data)!=rfc['size'] or sha(data)!=rfc['sha256']: raise ValueError('기준선 불일치: '+rfc['source'])
        baseline['bootsector/IP.BIN']=data
    result={k:bytearray(v) for k,v in baseline.items()}; writes={}; changed=[]
    def write(rel,pos,expected,new,owner):
        data=baseline[rel]
        if data[pos:pos+len(expected)]!=expected: raise ValueError('원본 byte 불일치: '+owner)
        for start,end,other in writes.get(rel,[]):
            if pos<end and start<pos+len(expected): raise ValueError('쓰기 겹침: '+owner+' / '+other)
        writes.setdefault(rel,[]).append((pos,pos+len(expected),owner))
        result[rel][pos:pos+len(expected)]=new
    disc_lip={rel:safe(root/'originals/disc',rel).read_bytes() for rel in lip_offb} if lip_align else {}
    disc_text={}
    for key,row in rows.items():
        rel=row['file']; raw=bytes.fromhex(row['raw_hex'])
        if rel in disc_lip:
            # 시험 기능: 일본어 원문의 글자 칸 위치에 한글을 맞춘다(원문이 쓰던 0 채움 구간까지 사용)
            start=row['offset']; orig=disc_lip[rel]; end=orig.find(b'\0',start)
            base=baseline[rel]; cur=len(raw)
            aligned=align_lip(row['text'],codes,orig[start:end],pad)
            if aligned is not None and len(aligned)<=end-start and not any(base[start+cur:end+1]):
                need=max((b-start for b in lip_offb[rel] if start<b<=end),default=0)
                while len(aligned)<min(need+8,end-start-1): aligned+=pad
                write(rel,start,base[start:end+1],aligned+b'\0'*(end+1-start-len(aligned)),key)
                changed.append(key); continue
        if row['text']==row['baseline_text']: continue
        encoded=encode(row['text'],codes)
        if len(encoded)>row['capacity']:
            raise ValueError(f"{key}: {len(encoded)}바이트 > 현재 가용 {row['capacity']}바이트. 리포인팅 설계 후 확장하세요.")
        if rel in lip_offb:
            start=row['offset']
            need=max((b-start for b in lip_offb[rel] if start<b<=start+row['capacity']),default=0)
            # 원본은 off_b가 마지막 4글자를 가리킨다. off_b에서 대사가 끝나면 off_b가 NUL을 가리키므로
            # off_b 뒤에도 최대 4칸(용량 안)을 채운다.
            if need: need=min(row['capacity'],need+8)
            # 빈 타일도 대사창 한 칸을 차지한다. 마지막 줄이 원문의 가장 긴 줄보다 길어지면
            # 자동 줄바꿈으로 4번째 줄이 생기므로 그 폭까지만 채운다.
            orig=disc_text.setdefault(rel,safe(root/'originals/disc',rel).read_bytes())
            width=max(sjis_glyphs(x) for x in orig[start:orig.index(b'\0',start)].split(b'//'))
            last=row['text'].split('//')[-1]
            room=width-(len(last)-sum(1 for i,ch in enumerate(last) if ch==' ' and i and last[i-1] in codes))
            need=min(need,len(encoded)+len(pad)*max(0,room))
            if (need-len(encoded))%len(pad) and need>len(encoded): need-=1
            while len(encoded)<need: encoded+=pad
        write(rel,row['offset'],raw+b'\0',encoded+b'\0'*(len(raw)+1-len(encoded)),key)
        changed.append(key)
    # 기계어·포인터 패치: config/code-patches*.json (src/make_bracket_patch.py, make_slot_fix_patch.py가 생성)
    for p in [p for cp in sorted((root/'config').glob('code-patches*.json')) for p in readjson(cp)['patches']]:
        orig=bytes.fromhex(p['original_hex']); new=bytes.fromhex(p['new_hex'])
        if len(orig)!=len(new): raise ValueError('코드 패치 길이 불일치: '+p['note'])
        write(p['file'],p['offset'],orig,new,'code:'+p['note'])
    if rf.exists():
        for p in rfc['patches']:
            write('bootsector/IP.BIN',p['offset'],bytes.fromhex(p['original_hex']),bytes.fromhex(p['new_hex']),'region-free')
    for asset_root in ['assets/images/native','assets/fonts/native','assets/video/native']:
        for path in (root/asset_root).rglob('*'):
            if not path.is_file(): continue
            rel=path.relative_to(root/asset_root).as_posix()
            if rel not in baseline: raise ValueError('미등록 자산: '+rel)
            data=path.read_bytes()
            if data==baseline[rel]: continue
            if rel.endswith('.BIN'): raise ValueError('실행/혼합 BIN 교체는 별도 명세가 필요합니다: '+rel)
            if rel in writes:
                # 같은 파일에 문안·고정 패치가 있으면 자산은 바뀐 구간만 쓴다(겹치면 write가 막는다)
                if len(data)!=len(baseline[rel]): raise ValueError('문안과 자산 쓰기 충돌(크기 변경): '+rel)
                base=baseline[rel]; diff=[i for i in range(len(data)) if data[i]!=base[i]]
                s=p=diff[0]
                for i in diff[1:]+[None]:
                    if i is None or i>p+16:
                        write(rel,s,base[s:p+1],data[s:p+1],'native:'+rel)
                        if i is not None: s=i
                    if i is not None: p=i
                continue
            write(rel,0,baseline[rel],data,'native:'+rel)
    for rel,data in result.items():
        if rel not in writes and bytes(data)!=baseline[rel]: raise ValueError('미등록 최종 diff: '+rel)
        if rel in writes:
            # 등록한 쓰기 범위 밖의 byte는 기준선과 완전히 일치해야 한다.
            cursor=0
            for start,end,_ in sorted(writes[rel]):
                if data[cursor:start]!=baseline[rel][cursor:start]: raise ValueError('보호 경계 침범: '+rel)
                cursor=end
            if len(data)==len(baseline[rel]) and data[cursor:]!=baseline[rel][cursor:]: raise ValueError('보호 경계 침범: '+rel)
    output=output or root/'out/sakura_wars_4_kr_dev.dcp'
    output.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(suffix='.partial',dir=output.parent); os.close(fd)
    try:
        with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for rel,data in result.items():
                info=zipfile.ZipInfo(rel,(2026,10,20,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED
                z.writestr(info,data)
        with zipfile.ZipFile(tmp) as z:
            if z.testzip() is not None: raise ValueError('ZIP CRC 오류')
            for rel,data in result.items():
                if z.read(rel)!=data: raise ValueError('출력 재검증 실패: '+rel)
        os.replace(tmp,output)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    report={'output':str(output),'sha256':sha(output.read_bytes()),'files':len(result),
        'changed_translation_ids':changed,'changed_files':sorted(writes),'baseline_payload_equal':not writes,
        'segment_hashes':segment_hashes,'index_sha256':sha((root/'assets/translation/index.json').read_bytes()),
        'runtime_verified':False,'release_approved':False,'dialogue':dialogue_info}
    (output.parent/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='segment_hashes'},ensure_ascii=False,indent=2))
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path)
    parser.add_argument('--lip-align',action='store_true',help='시험: LIPSYNC 한글을 일본어 글자 칸 위치에 맞춤')
    args=parser.parse_args()
    build(output=args.output,lip_align=args.lip_align)
