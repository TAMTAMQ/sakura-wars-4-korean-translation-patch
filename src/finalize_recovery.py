"""글리프 대조에서 확인한 추가 8개 문자를 복원하고 스캔 잡음을 제외한다."""
import json, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXTRA={'f7ca':'쭉','f7cb':'눴','f7cc':'엠','f7cd':'훙','f7ce':'멧','f7cf':'섞','f7d0':'뤼','f7d1':'…'}
def main():
    if json.loads((ROOT/'assets/translation/index.json').read_text(encoding='utf-8')).get('schema'):
        raise SystemExit('공유 대사 이관 이후에는 복원 초기화 도구를 실행할 수 없습니다.')
    encoding=json.loads((ROOT/'config/encoding.json').read_text(encoding='utf-8'))
    encoding.update({c:b for b,c in EXTRA.items()})
    (ROOT/'config/encoding.json').write_text(json.dumps(encoding,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    index=json.loads((ROOT/'assets/translation/index.json').read_text(encoding='utf-8'))
    rejected=[]; count=0
    for seg in index['segments']:
        path=ROOT/seg['path']; kept=[]
        for line in path.read_text(encoding='utf-8').splitlines():
            row=json.loads(line)
            if any(ord(c)<32 for c in row['text']):
                rejected.append(row); continue
            for code,ch in EXTRA.items():
                token=bytes.fromhex(code).decode('cp932')
                row['text']=row['text'].replace(token,ch)
                row['baseline_text']=row['baseline_text'].replace(token,ch)
            kept.append(row)
        path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in kept),encoding='utf-8')
        seg['rows']=len(kept); seg['sha256']=hashlib.sha256(path.read_bytes()).hexdigest(); count+=len(kept)
    (ROOT/'assets/translation/index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'research/rejected-text-candidates.json').write_text(json.dumps(rejected,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary=json.loads((ROOT/'research/migration-summary.json').read_text(encoding='utf-8'))
    summary['text_rows']=count; summary['rejected_scanner_noise']=len(rejected)
    (ROOT/'research/migration-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__': main()
