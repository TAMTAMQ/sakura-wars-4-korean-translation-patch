"""원문/개선판 양쪽의 실제 문자열 시작을 대조하여 짧은 음성 대사의 잘린 경계를 복원한다."""
import copy
import hashlib
import json
import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dialogue import Catalogue,digest,load,read_jsonl
from build import encode
from apply_dialogue_review import fingerprint


def restore(label, source_list, indexes, replacements):
    catalogue, rows, hashes = load()
    codes=json.loads((ROOT/'config/encoding.json').read_text(encoding='utf-8'))
    reverse={bytes.fromhex(value):key for key,value in codes.items()}
    def decode_prefix(raw):
        result=''
        for i in range(0,len(raw),2):
            part=raw[i:i+2]
            if part in reverse:result+=reverse[part]
            elif part[0]>=0xf8 and bytes([part[0]-8,part[1]]) in reverse:
                result+=reverse[bytes([part[0]-8,part[1]])]+' '
            else:result+=part.decode('cp932')
        return result
    units=copy.deepcopy(list(catalogue.units.values()));proposed=Catalogue(units)
    index_path=ROOT/'assets/translation/index.json';index=json.loads(index_path.read_text(encoding='utf-8'))
    binding_path=ROOT/'config/text-bindings.json';bindings=json.loads(binding_path.read_text(encoding='utf-8'))
    changes=[];corrections=[];cache={};changed_ids=set()
    metadata_fields=['offset','capacity','raw_hex','baseline_text','source']
    for i in indexes:
        key=source_list[i]['unit']; unit=proposed.units[key];full_texts=[];full_sources=[]
        before=copy.deepcopy(unit)
        assert 'text' in unit,key
        for use in unit['occurrences']:
            row=rows[use['id']];name=row['file'];assert name.endswith('.LIP'),use
            if name not in cache:
                cache[name]=((ROOT/'originals/v05'/name).read_bytes(),(ROOT/'originals/disc'/name).read_bytes())
            data,original=cache[name];old_start=row['offset'];k=int(row['id'].rsplit('#',1)[1])
            assert struct.unpack_from('<I',data,12+k*12+8)[0]-1==old_start,use
            start=data.rfind(b'\0',max(old_start-8,0),old_start)+1
            prefix=data[start:old_start]
            assert len(prefix) in [2,4],(use,prefix.hex())
            assert data[old_start:old_start+row['capacity']]==bytes.fromhex(row['raw_hex']),use
            jp_b=struct.unpack_from('<I',original,12+k*12+8)[0]-1
            jp_a=struct.unpack_from('<I',original,12+k*12+4)[0]-1
            jp_start=original.rfind(b'\0',max(jp_a,jp_b-40),jp_b)+1
            jp_end=original.find(b'\0',jp_b)
            source=original[jp_start:jp_end].decode('cp932')
            assert original[jp_start:jp_b] and len(original[jp_start:jp_b])<=8,use
            previous=copy.deepcopy(row)
            baseline=decode_prefix(prefix)+row['baseline_text']
            text=replacements.get(i,decode_prefix(prefix)+row['text'])
            raw=prefix+bytes.fromhex(row['raw_hex'])
            assert data[start:start+len(raw)+1]==raw+b'\0',use
            row.update(offset=start,capacity=len(raw),raw_hex=raw.hex(),baseline_text=baseline,source=source)
            full_texts.append(text);full_sources.append(source)
            for field in list(bindings[row['id']]):
                bindings[row['id']][field]=row[field]
            changed_ids.add(row['id'])
            changes.append({'id':row['id'],'unit':key,'before':{f:previous[f] for f in metadata_fields},'after':{f:row[f] for f in metadata_fields},'prefix_hex':prefix.hex(),'original_japanese':source,'original_text_start':jp_start,'original_table_off_b':jp_b})
        if len(set(full_sources))!=1:
            assert key=='dialogue:a964a2d16fef687d' and set(full_sources)=={'ぬうっ……','ぐうっ……'},key
            unit['source_alternatives']=sorted(set(full_sources))
        unit.pop('variants',None)
        unit.update(text=full_texts[0],source=full_sources[0],review='원문/번역 전체 문자열 경계 복원 · 2026-10-22')
        variants={}
        for use,text in zip(unit['occurrences'],full_texts):
            oid=use['id']
            use.pop('form',None);rows[oid].pop('form',None)
            if text!=full_texts[0]:
                form=next((f for f,v in variants.items() if v['text']==text),None)
                if form is None:
                    form=f'v{len(variants)+1:03d}'
                    variants[form]={'text':text,'base_text_sha256':digest(full_texts[0]),'review':'전체 원문 대조 완료','reason':'앞부분 복원 후에도 필요한 기존 말투·길이 차이 보존'}
                use['form']=form;rows[oid]['form']=form
        if variants:unit['variants']=variants
        if label=='20261022-dialogue-prefixes' and i==1431:
            # 같은 원문의 기존 완전 문안 한 곳을 참조하여 정상 대사/음성 꼬리 번역을 함께 관리.
            target='dialogue:c048ad9566b54db4'
            assert catalogue.units[target]['source']==full_sources[0] and catalogue.text(target)==full_texts[0]
            unit.pop('text');unit['parts']=[{'ref':target}]
        corrections.append({'unit':key,'source':full_sources[0],'before':before,'after':unit,'reason':'off_b 앞에 붙은 실제 문자까지 문안 소유 범위를 복원. 포인터/타이밍은 그대로 두고 전체 문장을 관리'+('하고 일본어 잔재 또는 오역을 교정' if i in replacements else '')})
    segments={}
    for descriptor in index['segments']:
        records=read_jsonl(ROOT/descriptor['path'])
        for record in records:
            if record['id'] in changed_ids:
                for field in metadata_fields:record[field]=rows[record['id']][field]
                record.pop('form',None)
                if 'form' in rows[record['id']]:record['form']=rows[record['id']]['form']
        segments[descriptor['path']]=records
    resolved=proposed.resolve([r for group in segments.values() for r in group])
    for oid in changed_ids:
        assert len(encode(resolved[oid]['text'],codes))<=resolved[oid]['capacity'],oid
    # 복원 공간끼리 또는 기존 다른 문안 영역과 겹치는 일은 허용하지 않는다.
    by_file={}
    for row in resolved.values():by_file.setdefault(row['file'],[]).append(row)
    for group in by_file.values():
        group.sort(key=lambda r:r['offset'])
        for left,right in zip(group,group[1:]):
            if left['id'] in changed_ids or right['id'] in changed_ids:
                assert left['offset']+len(bytes.fromhex(left['raw_hex']))+1<=right['offset'],(left['id'],right['id'])
    evidence=ROOT/'assets/translation/review'/label
    if evidence.exists():raise RuntimeError('이미 적용된 복원')
    evidence.mkdir(parents=True)
    with zipfile.ZipFile(evidence/'before.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in list(hashes)+['assets/translation/index.json','config/text-bindings.json']:
            archive.write(ROOT/path,path)
    for path in {catalogue.paths[u['unit']] for u in corrections}:
        records=read_jsonl(ROOT/path)
        (ROOT/path).write_text(''.join(json.dumps(proposed.units[r['id']],ensure_ascii=False)+'\n' for r in records),encoding='utf-8')
    for descriptor in index['segments']:
        path=descriptor['path']
        if any(r['id'] in changed_ids for r in segments[path]):
            (ROOT/path).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in segments[path]),encoding='utf-8')
        descriptor['sha256']=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
    index_path.write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    binding_path.write_text(json.dumps(bindings,ensure_ascii=False),encoding='utf-8')
    ledger=ROOT/'assets/translation/review/decisions.jsonl';decisions={r['unit']:r for r in read_jsonl(ledger)}
    for correction in corrections:
        key=correction['unit'];decisions[key]={'unit':key,'date':'2026-10-22','status':'approved','content_sha256':fingerprint(proposed,key),'note':correction['reason']}
    ledger.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in decisions.values()),encoding='utf-8')
    (evidence/'changes.json').write_text(json.dumps(corrections,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (evidence/'boundaries.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    load()
    print(json.dumps({'restored_units':len(corrections),'restored_occurrences':len(changes),'corrected_units':len(replacements),'pointer_timing_changes':0},ensure_ascii=False))


def main():
    source_list=json.loads((ROOT/'work/qa/dialogue/single-review.json').read_text(encoding='utf-8'))
    indexes=[707,878,890,891,913,914,936,956,957,965,972,978,1007,1009,1011,1026,1043,1049,1072,1332,1431]
    replacements={878:'간다∈',936:'에잇∈',957:'토텐∈',1007:'간다∈',1026:'어딜 가∈',1049:'…발그레',1431:'메롱∈'}
    restore('20261022-dialogue-prefixes',source_list,indexes,replacements)


if __name__=='__main__':main()
