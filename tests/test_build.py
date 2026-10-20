import contextlib, io, json, sys, tempfile, unittest, zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from build import build, encode, sha

class GuardTests(unittest.TestCase):
    def setUp(self):
        work=Path(__file__).resolve().parents[1]/'work/tests'
        work.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=work); self.root=Path(self.tmp.name)
        for sub in ['config','originals/v05','assets/translation/segments','assets/images/native','assets/fonts/native']:
            (self.root/sub).mkdir(parents=True,exist_ok=True)
        self.raw=bytes.fromhex('f0a6f0a7f8a8f0a9')+b'\0TAIL'
        (self.root/'originals/v05/test.SBX').write_bytes(self.raw)
        self.row={'id':'test#1','file':'test.SBX','offset':0,'capacity':8,'raw_hex':self.raw[:8].hex(),'baseline_text':'사쿠라 군','kind':'fixed','text':'사쿠라 군'}
        self.save('config/baseline.json',{'files':[{'path':'test.SBX','size':len(self.raw),'sha256':sha(self.raw)}]})
        self.save('config/encoding.json',{'사':'f0a6','쿠':'f0a7','라':'f0a8','군':'f0a9'})
        self.save('config/text-bindings.json',{'test#1':{k:v for k,v in self.row.items() if k!='text'}})
        self.save('assets/translation/index.json',{'segments':[{'path':'assets/translation/segments/test.jsonl'}]})
        self.segment()
    def tearDown(self): self.tmp.cleanup()
    def save(self,p,obj): (self.root/p).write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')
    def segment(self,rows=None):
        (self.root/'assets/translation/segments/test.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in (rows or [self.row])),encoding='utf-8')
    def runbuild(self):
        with contextlib.redirect_stdout(io.StringIO()): return build(self.root)
    def test_halfwidth_flag(self):
        self.assertEqual(encode('사쿠라 군',json.loads((self.root/'config/encoding.json').read_text())),self.raw[:8])
    def test_noop_payload(self):
        result=self.runbuild()
        with zipfile.ZipFile(result['output']) as z: self.assertEqual(z.read('test.SBX'),self.raw)
    def test_edit_protects_tail(self):
        self.row['text']='사쿠라'; self.segment(); result=self.runbuild()
        with zipfile.ZipFile(result['output']) as z:
            self.assertEqual(z.read('test.SBX'),bytes.fromhex('f0a6f0a7f0a8')+b'\0\0\0TAIL')
    def test_bad_baseline(self):
        (self.root/'originals/v05/test.SBX').write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError,'기준선'): self.runbuild()
        self.assertFalse((self.root/'out/sakura_wars_4_kr_dev.dcp').exists())
    def test_overflow(self):
        self.row['text']='사쿠라군사쿠라군'; self.segment()
        with self.assertRaisesRegex(ValueError,'가용'): self.runbuild()
    def test_protected_offset(self):
        self.row['offset']=1; self.segment()
        with self.assertRaisesRegex(ValueError,'보호 필드'): self.runbuild()
    def test_duplicate_id(self):
        self.segment([self.row,self.row])
        with self.assertRaisesRegex(ValueError,'중복'): self.runbuild()
    def test_overlap(self):
        other=dict(self.row,id='test#2',text='군')
        self.save('config/text-bindings.json',{r['id']:{k:v for k,v in r.items() if k!='text'} for r in [self.row,other]})
        self.row['text']='사'; self.segment([self.row,other])
        with self.assertRaisesRegex(ValueError,'쓰기 겹침'): self.runbuild()
    def test_missing_id(self):
        (self.root/'assets/translation/segments/test.jsonl').write_text('',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'모집단'): self.runbuild()

if __name__=='__main__': unittest.main()
