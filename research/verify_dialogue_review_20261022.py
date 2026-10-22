"""교정 전후 메타데이터·산출 패치의 실제 문자열 및 변경 경계를 독립 대조한다."""
import collections
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from build import encode
from dialogue import Catalogue,load


def main():
    catalogue,rows,hashes=load()
    with zipfile.ZipFile(ROOT/'assets/translation/review/20261022-dialogue/before.zip') as archive:
        old_index=json.loads(archive.read('assets/translation/index.json'))
        old_units=[json.loads(line) for entry in old_index['units'] for line in archive.read(entry['path']).decode('utf-8').splitlines() if line]
        old_occurrences=[json.loads(line) for entry in old_index['segments'] for line in archive.read(entry['path']).decode('utf-8').splitlines() if line]
    old_rows=Catalogue(old_units).resolve(old_occurrences)
    assert set(rows)==set(old_rows)
    # 문자열의 앞부분 누락을 복원한 경우에만 근거 파일의 명시적 경계 변경을 허용.
    expected_metadata={oid:dict(row) for oid,row in old_rows.items()}
    restored=0
    restored_ids=set()
    for evidence in sorted((ROOT/'assets/translation/review').glob('20261022-dialogue-prefixes*/boundaries.json')):
        for item in json.loads(evidence.read_text(encoding='utf-8')):
            oid=item['id'];expected=expected_metadata[oid]
            for key,value in item['before'].items():assert expected[key]==value,(oid,key)
            expected.update(item['after']);restored+=1;restored_ids.add(oid)
            raw=bytes.fromhex(expected['raw_hex'])
            data=(ROOT/'originals/v05'/expected['file']).read_bytes()
            assert data[expected['offset']:expected['offset']+len(raw)+1]==raw+b'\0',oid
    source_restored=0
    for evidence in sorted((ROOT/'assets/translation/review').glob('20261022-dialogue-source*/sources.json')):
        for item in json.loads(evidence.read_text(encoding='utf-8')):
            oid=item['id'];expected=expected_metadata[oid]
            assert expected['source']==item['before']['source'],oid
            raw=(ROOT/item['reference']).read_bytes()
            assert hashlib.sha256(raw).hexdigest()==item['reference_sha256'],oid
            prefix=f"[{item['table_index']:04d}] "
            lines=[s[len(prefix):] for s in raw.decode('utf-8').splitlines() if s.startswith(prefix)]
            assert lines==[item['after']['source']],oid
            expected.update(item['after']);source_restored+=1
    for oid,row in rows.items():
        assert {k:v for k,v in row.items() if k not in ['text','review','form']}=={k:v for k,v in expected_metadata[oid].items() if k not in ['text','review','form']},oid
    changed=[row for oid,row in rows.items() if row['text']!=old_rows[oid]['text'] or oid in restored_ids]
    codes=json.loads((ROOT/'config/encoding.json').read_text(encoding='utf-8'))
    allowed=collections.defaultdict(list)
    path=ROOT/'out/sakura_wars_4_kr_dev.dcp'
    old_path=ROOT/'work/qa/dialogue/before-review.dcp'
    changed_files=[]
    actual_changed=[]
    with zipfile.ZipFile(path) as patch,zipfile.ZipFile(old_path) as previous:
        assert set(patch.namelist())==set(previous.namelist())
        for row in changed:
            payload=patch.read(row['file'])
            start=row['offset'];text=encode(row['text'],codes)
            assert len(text)<=row['capacity'],row['id']
            if row['text']==row['baseline_text']:
                text=bytes.fromhex(row['raw_hex'])
            assert payload[start:start+len(text)]==text,row['id']
            tail=payload[start+len(text):start+len(bytes.fromhex(row['raw_hex']))+1]
            if row['file'].endswith('.LIP'):
                pad=bytes.fromhex(codes['\u2063'])
                while tail.startswith(pad):tail=tail[len(pad):]
            assert tail and set(tail)=={0},(row['id'],tail.hex())
            allowed[row['file']].append((start,start+len(bytes.fromhex(row['raw_hex']))+1))
            end=start+len(bytes.fromhex(row['raw_hex']))+1
            if payload[start:end]!=previous.read(row['file'])[start:end]:actual_changed.append(row)
        for name in patch.namelist():
            before=previous.read(name);after=patch.read(name)
            if before==after:continue
            changed_files.append(name)
            assert len(before)==len(after),name
            cursor=0
            for start,end in sorted(allowed[name]):
                assert before[cursor:start]==after[cursor:start],(name,cursor,start)
                cursor=end
            assert before[cursor:]==after[cursor:],(name,cursor)
    report=json.loads((ROOT/'out/build-report.json').read_text(encoding='utf-8'))
    assert report['sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    assert report['segment_hashes']==hashes
    result={'protected_metadata_checked':len(rows),'explicit_boundary_restorations':restored,'source_occurrences_restored':source_restored,'catalogue_text_changed_occurrences':len(changed),'actual_changed_occurrences':len(actual_changed),'actual_changed_units':len({r['unit'] for r in actual_changed}),'changed_files':changed_files,'encoded_or_baseline_texts_verified':len(changed),'outside_text_slots_unchanged':True,'images_video_code_unchanged':True,'before_dcp_sha256':hashlib.sha256(old_path.read_bytes()).hexdigest(),'dcp_sha256':report['sha256'],'game_display_check':'사용자 요청으로 제외'}
    (ROOT/'research/dialogue-review-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
