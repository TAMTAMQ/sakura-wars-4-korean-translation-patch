"""완성 DCP의 승리 자막과 이름판 간격을 검증하고 비교 시트를 남긴다."""
import json
import struct
import subprocess
import sys
import types
import zipfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import remake_slg_plates as plates
import export_images as E
from inject_images import targets
from build import encode, sha

def load(path): return json.loads((ROOT / path).read_text(encoding='utf-8'))

def main():
    cases = load('research/victory-lipsync-recovery.json')
    codes = load('config/encoding.json')
    report = load('out/build-report.json')
    with zipfile.ZipFile(ROOT / 'out/sakura_wars_4_kr_dev.dcp') as z:
        for case in cases:
            original = (ROOT / 'originals/v05' / case['id'].split('#')[0]).read_bytes()
            data = z.read(case['id'].split('#')[0])
            pos = case['offset']; raw = bytes.fromhex(case['original_hex']); translated = encode(case['text'], codes)
            assert len(data) == len(original) and len(translated) == len(raw)
            assert data[pos:pos + len(raw)] == translated
            assert data[pos - 2:pos] == b'f\0' and data[pos + len(raw)] == 0
            count = struct.unpack_from('<I', original, 8)[0]
            assert data[:12 + count * 12] == original[:12 + count * 12], 'LIP 표 변경'
            case['verified_hex'] = translated.hex()
        # PNG가 실제 게임 파일에 들어간 결과도 확인한다.
        rel = 'SLG/G02/CMAP02.GRCT'
        data = z.read(rel); spec = E.block_specs(data)[6]
        dec = E.decompress(spec[2], spec[4]) if spec[3] else spec[2]
        actual = np.asarray(E.decode_bpv(dec)[0][1].convert('RGBA')).astype(int)
        png = ROOT / targets()[(rel, 6)][0]
        desired = np.asarray(Image.open(png).convert('RGBA')).astype(int)
        assert np.abs(actual - desired).max() <= 18
    audit = load('research/slg-layout-audit.json')
    assert len(audit) == 72 and all(r['artificial_gap'] < 1e-8 for r in audit)
    # 수정 전 renderer를 읽어 동일 입력의 전후를 나란히 그린다. 게임 파일을 변경하지 않는다.
    previous = subprocess.check_output(['git', '-C', str(ROOT), 'show', 'HEAD:src/remake_slg_plates.py']).decode('utf-8')
    old = types.ModuleType('old_slg_plates'); old.__file__ = str(ROOT / 'src/remake_slg_plates.py')
    exec(compile(previous, old.__file__, 'exec'), old.__dict__)
    cfg = load('assets/images/remake/slg_plates.json')
    dest = ROOT / 'assets/images/remake/battle_issuefix'; dest.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 15)
    sheets = []
    for start in range(0, len(audit), 12):
        page = Image.new('RGB', (1040, 12 * 102 + 40), '#243044'); draw = ImageDraw.Draw(page)
        draw.text((8, 6), '조각 경계 자간 점검: 수정 전 / 수정 후 (문구·글꼴 동일)', font=font, fill='white')
        for i, row in enumerate(audit[start:start + 12]):
            block = next(b for b in cfg['blocks'] if b['source'] == row['source'] and b['block'] == row['block'])
            chain = next(c for c in cfg['templates'][block['template']] if c['key'] == row['field'])
            override = block['text'][row['field']]
            if isinstance(override, dict): chain = {**chain, **{k: v for k, v in override.items() if k != 'text'}}
            args = (row['text'], row['width'], row['height'], chain['layout'], chain.get('track', 0), chain.get('x', 0), cfg['font'], row['cuts'])
            a = old.render_mask(*args); b = plates.render_mask(*args, shadow_guard=row['shadow_guard'])
            y = i * 102 + 40
            draw.text((8, y), f"{row['source']} b{row['block']} {row['field']} — {row['text']}", font=font, fill='white')
            for x, mask in [(8, a), (520, b)]:
                img = Image.fromarray((mask * 255).astype('uint8')).convert('RGB')
                page.paste(img.resize((img.width * 2, img.height * 2)), (x, y + 23))
            if row['text'] == '시카미':
                pair = Image.new('RGB', (340, 100), '#243044'); pd = ImageDraw.Draw(pair)
                pd.text((4, 2), '수정 전', font=font, fill='white'); pd.text((174, 2), '수정 후', font=font, fill='white')
                for x, mask in [(4, a), (174, b)]:
                    pair.paste(Image.fromarray((mask * 255).astype('uint8')).convert('RGB').resize((144, 48)), (x, 28))
                pair.save(dest / 'shikami-before-after.png')
        target = dest / f'layout-{start // 12 + 1:02d}.png'; page.save(target)
        sheets.append(target.relative_to(ROOT).as_posix())
    result = {'dcp': report['output'], 'sha256': report['sha256'], 'victory_captions': cases,
              'split_fields_verified': len(audit), 'max_artificial_gap_px': 0,
              'sheets': sheets, 'runtime_verified': False,
              'runtime_limitation': 'emucap launch_plan: Flycast adapter binary is unavailable'}
    (ROOT / 'research/battle-issuefix-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('victory_captions', 'sheets')}, ensure_ascii=False, indent=2))

if __name__ == '__main__': main()
