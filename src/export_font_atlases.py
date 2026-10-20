import json, hashlib
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1]
def main():
    result=[]
    for name,stride,size in [('SKFONT.CG',338,26),('SKFONT2.CG',288,24),('SKFONT3.CG',242,22),('SKFONT4.CG',242,22)]:
        data=(ROOT/'originals/v05'/name).read_bytes()
        original=(ROOT/'originals/disc'/name).read_bytes()
        count=len(data)//stride; cols=48; cell=size+8
        atlas=Image.new('RGB',(cols*cell,((count+cols-1)//cols)*cell),'#282828')
        changed=[]
        for t in range(count):
            raw=data[t*stride:(t+1)*stride]
            src=np.frombuffer(raw,dtype=np.uint8).reshape(size//2,size)
            values=np.empty((size,size),dtype=np.uint8)
            values[::2]=(src&15)*17; values[1::2]=(src>>4)*17
            atlas.paste(Image.fromarray(values).convert('RGB'),((t%cols)*cell,(t//cols)*cell))
            if raw!=original[t*stride:(t+1)*stride]: changed.append(t)
        out=ROOT/'assets/extracted/fonts'/name
        out.mkdir(parents=True,exist_ok=True); atlas.save(out/'all-glyphs.png')
        row={'source':name,'tiles':count,'changed_tiles':changed,'atlas':(out/'all-glyphs.png').relative_to(ROOT).as_posix()}
        (out/'metadata.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8'); result.append(row)
    (ROOT/'assets/extracted/fonts/index.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('글꼴 아틀라스',len(result))
if __name__=='__main__': main()
