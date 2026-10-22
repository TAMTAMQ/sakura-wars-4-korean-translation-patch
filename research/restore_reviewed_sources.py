"""검수 중 발견한 구 한글 코드의 원문 오독을 보관 원문으로 복원한다.

originals/disc의 해당 SBX도 구 한글 코드이므로 일본어 바이너리라고 주장하지 않는다.
보관 original_txt의 같은 파일/표 번호를 근거로 삼으며 사용처별 근거를 남긴다.
"""
import copy
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dialogue import Catalogue,load,read_jsonl
from apply_dialogue_review import fingerprint
from build import encode

def norm(s):return re.sub(r'\s+','',''.join(s.split('//')).replace('∈','！').replace('～','〜'))

def restore(label,indexes,explicit_aliases=None,entries_path='work/qa/dialogue/single-review.json'):
    current,old_rows,hashes=load();units=copy.deepcopy(list(current.units.values()));proposed=Catalogue(units)
    entries=json.loads((ROOT/entries_path).read_text(encoding='utf-8'))
    codes=json.loads((ROOT/'config/encoding.json').read_text(encoding='utf-8'))
    evidence=ROOT/'assets/translation/review'/label
    assert not evidence.exists()
    sources={};cache={};changes=[];boundaries=[]
    explicit_aliases=explicit_aliases or {}
    for i in indexes:
        key=entries[i]['unit'];unit=proposed.units[key];before=copy.deepcopy(unit);originals=[]
        for use in unit['occurrences']:
            row=old_rows[use['id']];name=Path('research/legacy/original_txt')/Path(row['file']).with_suffix('.txt')
            if name not in cache:
                raw=(ROOT/name).read_bytes()
                cache[name]=({int(m[1]):m[2] for line in raw.decode('utf-8').splitlines() if (m:=re.match(r'^\[(\d+)\] (.*)$',line))},hashlib.sha256(raw).hexdigest())
            lines,sha=cache[name];number=int(row['id'].rsplit('#',1)[1]);source=lines[number]
            originals.append(source);sources[row['id']]=source
            boundaries.append({'id':row['id'],'before':{'source':row['source']},'after':{'source':source},'reference':name.as_posix(),'reference_sha256':sha,'table_index':number})
        assert len(set(originals))==1,key
        unit['source']=originals[0]
        alias=None
        if i in explicit_aliases:
            alias=entries[explicit_aliases[i]]['unit']
            assert norm(proposed.units[alias]['source'])==norm(unit['source']),(i,alias)
        else:
            texts={current.text(key,f) for f in ['default']+list(before.get('variants',{}))}
            for other in current.units.values():
                if other['id']==key or 'parts' in other or norm(other['source'])!=norm(unit['source']):continue
                other_texts={current.text(other['id'],f) for f in ['default']+list(other.get('variants',{}))}
                if len(texts)==1 and texts==other_texts:alias=other['id'];break
        if alias:
            text=current.text(alias)
            for use in unit['occurrences']:
                row=old_rows[use['id']];assert len(encode(text,codes))<=row['capacity'],use['id']
                use.pop('form',None)
            for field in ['text','variants','breaks']:unit.pop(field,None)
            unit['parts']=[{'ref':alias}]
        unit['review']='보관 원문 대조·공통 문안 연결 · 2026-10-22'
        changes.append({'unit':key,'source':unit['source'],'before':before,'after':unit,'reason':'보관 일본어 원문의 동일 파일/표 번호를 대조해 원문 오독 복원'+(' 및 기존 공통 문안 참조' if alias else '')})
    index_path=ROOT/'assets/translation/index.json';index=json.loads(index_path.read_text(encoding='utf-8'));segments={}
    for descriptor in index['segments']:
        records=read_jsonl(ROOT/descriptor['path'])
        for row in records:
            if row['id'] not in sources:continue
            row['source']=sources[row['id']]
            if 'parts' in proposed.units[row['unit']]:row.pop('form',None)
        segments[descriptor['path']]=records
    fresh=Catalogue(list(proposed.units.values()));resolved=fresh.resolve([r for group in segments.values() for r in group])
    for oid,row in resolved.items():
        assert {k:v for k,v in row.items() if k not in {'source','text','review','form'}}=={k:v for k,v in old_rows[oid].items() if k not in {'source','text','review','form'}},oid
        if oid not in sources:assert row['text']==old_rows[oid]['text'],oid
    evidence.mkdir(parents=True)
    with zipfile.ZipFile(evidence/'before.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in list(hashes)+['assets/translation/index.json']:archive.write(ROOT/path,path)
    for path in {current.paths[c['unit']] for c in changes}:
        records=read_jsonl(ROOT/path)
        (ROOT/path).write_text(''.join(json.dumps(fresh.units[r['id']],ensure_ascii=False)+'\n' for r in records),encoding='utf-8')
    for descriptor in index['segments']:
        path=descriptor['path']
        if any(r['id'] in sources for r in segments[path]):(ROOT/path).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in segments[path]),encoding='utf-8')
        descriptor['sha256']=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
    index_path.write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    ledger=ROOT/'assets/translation/review/decisions.jsonl';decisions={r['unit']:r for r in read_jsonl(ledger)}
    for change in changes:
        key=change['unit'];decisions[key]={'unit':key,'date':'2026-10-22','status':'approved','content_sha256':fingerprint(fresh,key),'note':change['reason']+'. 원문과 번역 개별 대조 완료.'}
        decisions[key]['note']=change['reason']+'. 일본어 원문과 한국어 문안을 각각 읽고 대조 완료.'
    ledger.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in decisions.values()),encoding='utf-8')
    (evidence/'changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (evidence/'sources.json').write_text(json.dumps(boundaries,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    load()
    print(json.dumps({'source_units_restored':len(changes),'source_occurrences':len(sources),'shared_aliases':sum('parts' in c['after'] for c in changes)},ensure_ascii=False))

if __name__=='__main__':restore('20261022-dialogue-source-recovery',range(4174,4221),{4210:815,4213:818})
