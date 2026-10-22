"""최종 패치에서 #53의 전체 배경·글자가 보존되고 다른 블록이 그대로인지 검사한다."""
import hashlib
import json
import sys
import zipfile
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import export_images as E

def main():
    before = json.loads((ROOT / 'work/issues/asakusa/before-dcp-index.json').read_text(encoding='utf-8'))
    with zipfile.ZipFile(ROOT / 'out/sakura_wars_4_kr_dev.dcp') as z:
        changed = [name for name in z.namelist() if hashlib.sha256(z.read(name)).hexdigest() != before[name]]
        # 뒤에 추가된 개별 SLG 수정은 별도 검증기가 담당한다. #53 비교 기준 이후
        # 변경을 허용하는 파일은 명시한 개별 수정의 사본 컨테이너로 한정한다.
        corrections = json.loads((ROOT / 'assets/images/remake/individual/index.json').read_text(encoding='utf-8'))
        reviews = json.loads((ROOT / 'assets/images/review/image_review.json').read_text(encoding='utf-8'))
        ids = {r['id'] for r in corrections}
        additional = {member.rsplit(' ', 2)[0] for row in reviews if row['id'] in ids for member in row['members']}
        assert set(changed) <= {'ADVDATA/CG_ALL1.DAT', 'ADVDATA/GR.IDX'} | additional
        data = z.read('ADVDATA/CG_ALL1.DAT'); specs = E.block_specs(data)
        changed_blocks = [i for i, spec in enumerate(specs) if i >= len(before['cg_blocks']) or hashlib.sha256(spec[2]).hexdigest() != before['cg_blocks'][i]]
        assert changed_blocks == [736], changed_blocks
        spec = specs[736]; decoded = E.decompress(spec[2], spec[4]) if spec[3] else spec[2]
        got = np.asarray(E.decode_adcg(decoded)[0][1].convert('RGBA'))
        want = np.asarray(Image.open(ROOT / 'assets/images/remake/ui/ADVDATA/CG_ALL1.DAT/0736_0000.png').convert('RGBA'))
        diff = int(np.abs(got.astype(int) - want.astype(int)).max())
        assert diff == 0, diff
        assert E.u32(decoded, 4) == 13
        frame = got[128:188, 128:136]
        assert (frame[..., 3] > 0).any(), '연장된 테두리가 저장되지 않음'
    result = {'dcp_sha256': hashlib.sha256((ROOT / 'out/sakura_wars_4_kr_dev.dcp').read_bytes()).hexdigest(),
              'review_id': 53, 'changed_files': changed, 'changed_cg_blocks': changed_blocks,
              'canvas': [640, 480], 'panel_height': [132, 188], 'font_size': [17, 28],
              'tile_count': [12, 13], 'max_pixel_diff': diff, 'runtime_verified': False}
    (ROOT / 'research/asakusa-panel-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__': main()
