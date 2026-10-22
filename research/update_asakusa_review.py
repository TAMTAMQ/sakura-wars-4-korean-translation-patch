"""검수표 #53의 배경 연장과 원본 크기 복원을 기록한다."""
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import export_images as E

def read(path): return json.loads((ROOT / path).read_text(encoding='utf-8'))
def write(path, obj): (ROOT / path).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

def snapshot():
    with zipfile.ZipFile(ROOT / 'out/sakura_wars_4_kr_dev.dcp') as z:
        hashes = {name: hashlib.sha256(z.read(name)).hexdigest() for name in z.namelist()}
        data = z.read('ADVDATA/CG_ALL1.DAT')
        hashes['cg_blocks'] = [hashlib.sha256(s[2]).hexdigest() for s in E.block_specs(data)]
    write('work/issues/asakusa/before-dcp-index.json', hashes)

def main():
    dest = ROOT / 'assets/images/remake/asakusa'; dest.mkdir(parents=True, exist_ok=True)
    before = Image.open(ROOT / 'work/issues/asakusa/before.png').convert('RGBA')
    after = Image.open(ROOT / 'assets/images/remake/ui/ADVDATA/CG_ALL1.DAT/0736_0000.png').convert('RGBA')
    font = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 17)
    comparison = Image.new('RGB', (600, 600), '#243044'); draw = ImageDraw.Draw(comparison)
    for x, image, label in [(10, before, '수정 전'), (310, after, '수정 후')]:
        draw.text((x, 8), label, font=font, fill='white')
        crop = image.crop((0, 0, 140, 280))
        background = Image.new('RGBA', crop.size, '#344563'); background.alpha_composite(crop)
        comparison.paste(background.convert('RGB').resize((280, 560), Image.Resampling.NEAREST), (x, 35))
    target = dest / 'before-after.png'; comparison.save(target)
    path = 'assets/images/review/image_review.json'; rows = read(path)
    row = next(r for r in rows if r['id'] == 53)
    marker = ' [2026-10-22 아사쿠사 배경 연장]'
    row['note'] = row['note'].split(marker)[0] + marker + ' 「浅草」 2자에서 「아사쿠사」 4자가 되며 작아졌던 글자를 원본 글자 높이(약 27~29px)에 맞춰 17→28px로 복원. 둥근 배경판은 위·아래 곡률과 테두리를 보존하고 가운데를 세로로 56px 연장(132→188px). 새 테두리 범위를 저장할 ADCG 타일 (128,128)을 추가해 잘림을 방지. 게임 재삽입·재디코딩 및 DCP 검증 완료, 실제 게임 화면은 미확인.'
    write(path, rows)
    path = 'assets/images/review/image_review_updates.json'; updates = read(path)
    updates = [r for r in updates if r.get('id') != 'asakusa-panel-2026-10-22']
    updates.append({'id': 'asakusa-panel-2026-10-22', 'date': '2026-10-22',
        'title': '#53 아사쿠사 표지판 배경 연장·원본 글자 크기 복원',
        'comparison': target.relative_to(ROOT).as_posix(), 'comparison_label': '아사쿠사: 수정 전 / 수정 후',
        'notes': ['세로 둥근 판의 가운데를 아래로 56px 늘려 상하 곡률·테두리 두께를 보존했다. 「아사쿠사」는 축소하지 않고 원래 한자와 같은 글자 높이에 맞췄다.',
                  '기존 저장 타일이 없는 구역에 필요한 타일 1개를 등록하고 재삽입했다. 캔버스는 640×480 그대로다. 실제 게임 화면 확인은 아직 하지 못했다.']})
    write(path, updates)
    print('검수표 #53 및 아사쿠사 전후 비교 갱신')

if __name__ == '__main__':
    if '--snapshot' in sys.argv: snapshot()
    else: main()
