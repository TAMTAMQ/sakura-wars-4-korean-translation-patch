"""남은 문안을 실제 읽기 위한 조회. 일본어 보관본을 쓸 때 *를 표시한다."""
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dialogue import load
cache={}
def legacy_source(unit,rows):
    originals=[]
    for use in unit['occurrences']:
        row=rows[use['id']]
        if not row['file'].endswith(('.SBX','.SBN')):return None
        p=ROOT/'research/legacy/original_txt'/Path(row['file']).with_suffix('.txt')
        if not p.exists():return None
        if p not in cache:cache[p]={int(m[1]):m[2] for line in p.read_text(encoding='utf-8').splitlines() if (m:=re.match(r'^\[(\d+)\] (.*)$',line))}
        number=int(row['id'].rsplit('#',1)[1])
        if number not in cache[p]:return None
        originals.append(cache[p][number])
    return originals[0] if len(set(originals))==1 else None

def show(start,end):
    catalogue,rows,_=load();entries=json.loads((ROOT/'work/qa/dialogue/single-review.json').read_text(encoding='utf-8'))
    for i in range(start,end):
        u=catalogue.units[entries[i]['unit']];old=legacy_source(u,rows)
        use_old=old is not None and not re.search('[ぁ-ゖァ-ヺ]',u['source']) and old!=u['source']
        source=old if use_old else u['source']
        texts=[catalogue.text(u['id'],f) for f in ['default']+list(u.get('variants',{}))]
        print(str(i)+('*' if use_old else ''),source,'=>',' | '.join(texts))

if __name__=='__main__':show(int(sys.argv[1]),int(sys.argv[2]))
