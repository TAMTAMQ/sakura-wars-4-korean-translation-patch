"""실제 판정과 교정 전후 문안을 함께 보여 주는 정적 검수표를 생성한다."""
import collections
import json

from apply_dialogue_review import fingerprint
from dialogue import ROOT, load, read_jsonl


def main():
    catalogue,_,_=load()
    directory=ROOT/'assets/translation/review'
    decisions={r['unit']:r for r in read_jsonl(directory/'decisions.jsonl')}
    changes={}
    for path in sorted(directory.glob('20261022-*/changes.json')):
        for change in json.loads(path.read_text(encoding='utf-8')):
            key=change['unit']
            changes.setdefault(key,change)
    rows=[]
    inventory=json.loads((ROOT/'work/qa/dialogue/review-units.json').read_text(encoding='utf-8'))
    for item in inventory:
        key=item['unit'];unit=catalogue.units[key];decision=decisions.get(key,{})
        status=decision.get('status','pending') if decision.get('content_sha256')==fingerprint(catalogue,key) else 'pending'
        correction=changes.get(key)
        old=[]
        if correction:
            old_unit=correction['before']
            old=[old_unit.get('text','[조합 문안]')]+[v.get('text','[줄바꿈 변형]') for v in old_unit.get('variants',{}).values()]
        rows.append({'id':key,'source':unit['source'],'texts':{f:catalogue.text(key,f) for f in ['default']+list(unit.get('variants',{}))},'before':old,'status':status,'note':decision.get('note','아직 문장별 의미 검수를 하지 않았습니다.'),'path':catalogue.paths[key],'uses':[o['id'] for o in unit['occurrences']]})
    counts=dict(collections.Counter(r['status'] for r in rows))
    summary={'total':len(rows),'status':counts,'corrected_units':len(changes),'scope':'대사 검수만 수행. 게임 내 표시 확인 제외.','all_dialogue_review_complete':not any(r['status']!='approved' for r in rows)}
    (directory/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    data=json.dumps(rows,ensure_ascii=False).replace('<','\\u003c')
    html='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>사쿠라대전 4 대사 검수표</title>
<style>body{font-family:system-ui,sans-serif;margin:24px;background:#f4f5f7;color:#20242c}header{position:sticky;top:0;background:#f4f5f7;padding:12px 0}input,select,button{padding:8px;margin-right:8px}table{width:100%;border-collapse:collapse;background:white}th,td{border:1px solid #ccd2da;padding:10px;vertical-align:top;white-space:pre-wrap;word-break:break-word}th{background:#e8edf4}td:nth-child(2),td:nth-child(3),td:nth-child(4){width:23%}small{color:#526174}code{font-size:11px}pre{white-space:pre-wrap}button{cursor:pointer}</style>
<h1>대사 검수표</h1><p id="summary"></p><p>대조 완료와 최종 확정을 구분합니다. 자동 검사 통과는 의미 검수 완료를 뜻하지 않습니다. 수정 전·후 문안은 나란히 보존합니다.</p>
<header><input id="q" size="40" placeholder="원문·번역·ID·사용처 검색"><select id="status"><option value="">모든 상태</option><option value="pending">미검수</option><option value="compared">대조함 · 통일 미확정</option><option value="approved">확정</option><option value="needs_source">원문 복원 필요</option><option value="needs_context">문맥 추가 확인</option><option value="changed">교정 문안</option></select><button id="prev">이전</button><button id="next">다음</button><span id="count"></span></header>
<table><thead><tr><th>상태 · 사용처</th><th>일본어 원문</th><th>교정 전</th><th>현재 공유 문안</th><th>검수 메모</th></tr></thead><tbody id="body"></tbody></table>
<script>const rows=DATA;const labels={pending:'미검수',compared:'대조함 · 통일 미확정',approved:'확정',needs_source:'원문 복원 필요',needs_context:'문맥 추가 확인'};let page=0;
const body=document.getElementById('body'),q=document.getElementById('q'),status=document.getElementById('status');const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function render(){let query=q.value.toLowerCase();let filtered=rows.filter(r=>(!status.value||(status.value==='changed'?r.before.length:r.status===status.value))&&(!query||JSON.stringify(r).toLowerCase().includes(query)));page=Math.min(page,Math.max(0,Math.ceil(filtered.length/50)-1));body.innerHTML=filtered.slice(page*50,page*50+50).map(r=>`<tr><td><b>${escape(labels[r.status])}</b><br><code>${escape(r.id)}</code><details><summary>${r.uses.length}곳</summary>${escape(r.uses.join('\\n'))}</details><small>${escape(r.path)}</small></td><td>${escape(r.source)}</td><td>${escape(r.before.length?r.before.join('\\n────────\\n'):'교정 없음')}</td><td>${escape(Object.entries(r.texts).map(([k,v])=>k+': '+v).join('\\n────────\\n'))}</td><td>${escape(r.note)}</td></tr>`).join('');document.getElementById('count').textContent=`${filtered.length}개 · ${page+1}/${Math.max(1,Math.ceil(filtered.length/50))}쪽`;}
q.oninput=status.onchange=()=>{page=0;render()};document.getElementById('prev').onclick=()=>{page=Math.max(0,page-1);render()};document.getElementById('next').onclick=()=>{page++;render()};document.getElementById('summary').textContent=SUMMARY;render();</script></html>'''
    summary_text=f"총 {len(rows):,}개 문안 · 교정·복원 {len(changes):,}개 · 확정 {counts.get('approved',0):,}개 · 미검수 {counts.get('pending',0):,}개. 전체 검수는 진행 중입니다. 게임 내 표시 확인은 제외했습니다."
    html=html.replace('DATA',data).replace('SUMMARY',json.dumps(summary_text,ensure_ascii=False))
    (directory/'dialogue_review.html').write_text(html,encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
