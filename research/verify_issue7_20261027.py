"""이슈 #7 최종 개발 패치를 실행 없이 재추출·대조한다."""
import hashlib
import json
import struct
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import export_images as E
import inject_images as I
from build import encode
from dialogue import load
from ending_credits import format_names, live_strings


def digest(b):return hashlib.sha256(b).hexdigest()


def main():
    out=ROOT/'work/issues/20261026-ending';out.mkdir(parents=True,exist_ok=True)
    patch=ROOT/'out/sakura_wars_4_kr_dev.dcp'
    catalogue,rows,_=load()
    codes=json.loads((ROOT/'config/encoding.json').read_text(encoding='utf-8'))
    report={'verification':'static only','sha256':digest(patch.read_bytes()),
            'runtime_verified':False,'runtime_checks_excluded_by_user':True}
    with zipfile.ZipFile(patch) as z,zipfile.ZipFile(ROOT/'out/sakura_wars_4_kr_v0.8.7.dcp') as old:
        assert z.testzip() is None
        # 풍림화산은 원본 파일로 남고 패치·재제작 입력에 들어가지 않는다.
        assert 'SLG/COM.BC' not in z.namelist()
        assert not (ROOT/'assets/images/native/SLG/COM.BC').exists()
        preserve=json.loads((ROOT/'config/preserved-assets.json').read_text(encoding='utf-8'))['files'][0]
        assert digest((ROOT/'originals/disc'/preserve['path']).read_bytes())==preserve['sha256']
        report['wind_forest_fire_mountain']='original kanji and animation preserved'
        # 새 로고가 가리키는 모든 실제 사본을 다시 디코딩한다.
        textures=[];containers={};old_containers={};allowed={}
        for (rel,block),texs in I.targets().items():
            for ti,png in texs.items():
                if not png.startswith('assets/images/remake/logo/'):continue
                if rel not in containers:containers[rel]=E.block_specs(z.read(rel))
                spec=containers[rel][block]
                dec=E.decompress(spec[2],spec[4]) if spec[3] else spec[2]
                decoded=E.decode_bpv(dec) if spec[0]=='BPV1' else E.decode_adcg(dec)
                got=np.asarray(decoded[ti][1].convert('RGBA'),dtype=int)
                want=np.asarray(Image.open(ROOT/png).convert('RGBA'),dtype=int)
                assert got.shape==want.shape
                diff=np.abs(got-want)
                assert diff.max()<=18 or diff.mean()<=6,(rel,block,ti,int(diff.max()),float(diff.mean()))
                textures.append({'source':rel,'block':block,'texture':ti,'max_diff':int(diff.max()),'mean_diff':float(diff.mean())})
                allowed.setdefault(rel,set()).add(block)
                # 최종 패치에서 디코딩한 실제 그림을 별도 검수 자료로 남긴다.
                p=out/'final-logo'/rel/f'{block:04d}_{ti:04d}.png';p.parent.mkdir(parents=True,exist_ok=True)
                decoded[ti][1].save(p)
        assert len(textures)==20
        report['logo_texture_readbacks']=textures
        report['logo_design_variants']=8
        # 로고 외 블록은 v0.8.7과 압축 바이트까지 같다.
        for rel,blocks in allowed.items():
            a=containers[rel];b=E.block_specs(old.read(rel))
            assert len(a)==len(b)
            for i,(x,y) in enumerate(zip(a,b)):
                if i not in blocks:assert x==y,(rel,i)
                assert x[1]==y[1],(rel,i,'record moved')
        # GR.IDX에서 로고 두 레코드의 길이 필드 외 변경이 없어야 한다.
        a=z.read('ADVDATA/GR.IDX');b=old.read('ADVDATA/GR.IDX')
        gr_allowed=set();cg=containers['ADVDATA/CG_ALL1.DAT']
        for i in [733,735]:
            sector=(cg[i][1]-8)//2048
            for p in range(0x128,0x4b08,16):
                if struct.unpack_from('<I',b,p)[0]==sector:gr_allowed.update(range(p+4,p+8))
        assert all(i in gr_allowed for i,(x,y) in enumerate(zip(a,b)) if x!=y)
        # 엔딩 시 14장과 마지막 세로 문구는 이미 번역된 자료가 그대로 들어 있다.
        for rel,blocks,stage in [('ADVDATA/NC_ALL1.DAT',range(728,742),'nc'),('ADVDATA/CG_ALL1.DAT',[1048],'quotes')]:
            specs=E.block_specs(z.read(rel));prior=E.block_specs(old.read(rel))
            for block in blocks:
                s=specs[block];assert s==prior[block]
                dec=E.decompress(s[2],s[4]) if s[3] else s[2]
                a=np.asarray(E.decode_adcg(dec)[0][1].convert('RGBA'),dtype=int)
                p=ROOT/f'assets/images/remake/{stage}'/rel/f'{block:04d}_0000.png'
                b=np.asarray(Image.open(p).convert('RGBA'),dtype=int)
                assert np.abs(a-b).max()<=18
        report['existing_ending_translations_verified']=15
        # ASCR 명령·파일 길이 불변 및 스태프 77행의 실제 포인터·문안 확인.
        cfg=json.loads((ROOT/'config/ending-credits-layout.json').read_text(encoding='utf-8'))
        rel=cfg['file'];data=z.read(rel);base=(ROOT/'originals/v05'/rel).read_bytes();table,pool,_=live_strings(base)
        assert len(data)==len(base) and data[:table]==base[:table]
        managed={i['id']:i for i in cfg['rows']}
        for key,item in managed.items():
            r=rows[key];at=table+struct.unpack_from('<I',data,r['pointer_offset'])[0]
            assert at==item['offset']
            assert data[at:data.index(0,at)]==encode(format_names(r['text'],item,10),codes)
        report['staff_two_column_rows_verified']=len(managed)
        # 모든 편집 문안의 인코딩 결과를 DCP의 적용 위치와 직접 대조한다.
        readbacks=0;data_cache={}
        for key,r in rows.items():
            if key in managed or r['text']==r['baseline_text']:continue
            if r['file'] not in data_cache:data_cache[r['file']]=z.read(r['file'])
            data=data_cache[r['file']];expected=encode(r['text'],codes);at=r['offset']
            assert data[at:at+len(expected)]==expected,key
            readbacks+=1
        report['translated_text_readbacks']=readbacks
        restored=json.loads((ROOT/'assets/translation/review/20261026-issue7-monsieur/changes.json').read_text(encoding='utf-8'))
        for item in restored:
            expected=item['before']['text']
            if item['unit']=='dialogue:954c9454546d2e94':
                expected=expected.replace('후훗…고마워','후훗…천만에')
            assert catalogue.text(item['unit'])==expected,item['unit']
        report['monsieur_original_address_restored']=len(restored)
        # 사용자 지정: 낫표는 비교표 수정 전(v0.8.7)의 글꼴·실행 코드 그대로.
        assert z.read('1ST_READ.BIN')==old.read('1ST_READ.BIN')
        for name in ['SKFONT.CG','SKFONT2.CG','SKFONT3.CG','SKFONT4.CG']:
            assert z.read(name)==old.read(name),name
        report['brackets_restored_to_before']=True
        assert z.read('ADVDATA/ENDING.BIN')==old.read('ADVDATA/ENDING.BIN')
        assert 'ADVDATA/KAO_ALL1.DAT' not in z.namelist()
        report['ending_execution_code_unchanged_since_v087']=True
        report['portrait_container_not_modified']=True
        report['changed_files_since_v087']=[n for n in z.namelist() if z.read(n)!=old.read(n)]
    report['ok']=True
    (out/'static-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in {'logo_texture_readbacks','changed_files_since_v087'}},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
