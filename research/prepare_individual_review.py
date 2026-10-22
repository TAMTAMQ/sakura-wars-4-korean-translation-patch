"""기존 재제작본을 동결하고 이미지별 원본/재제작 비교 자료를 만든다."""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT = Path(__file__).resolve().parents[1]

def main():
    review = ROOT / 'assets/images/review'
    frozen = review / 'remake_baseline'
    manifest = review / 'remake_baseline.json'
    if manifest.exists():
        mapping = json.loads(manifest.read_text(encoding='utf-8'))
    else:
        mapping = {}
        for stage in ['slg', 'staffroll', 'ui', 'logo']:
            for r in json.loads((ROOT / 'assets/images/remake' / stage / 'index.json').read_text(encoding='utf-8')):
                key = f"{r['source']}|{r['block']}|{r['texture']}"
                src = ROOT / r['remake']
                target = frozen / r['source'] / f"{r['block']:04d}_{r['texture']:04d}.png"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(src.read_bytes())
                mapping[key] = {'path': target.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(src.read_bytes()).hexdigest()}
        manifest.write_text(json.dumps(mapping, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    rows = json.loads((review / 'image_review.json').read_text(encoding='utf-8'))
    pages = ROOT / 'work/issues/individual-review'; pages.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 13)
    # 원본과 현재 재제작을 이미지별로 붙여서 실제 세로/가로 읽기와 글자 크기를 확인한다.
    groups = [('slg', [r for r in rows if 100 <= r['id'] <= 171]),
              ('other', [r for r in rows if not 100 <= r['id'] <= 171])]
    for group, group_rows in groups:
        for start in range(0, len(group_rows), 8):
            page = Image.new('RGB', (1150, 8 * 240), '#263346'); draw = ImageDraw.Draw(page)
            for j, r in enumerate(group_rows[start:start + 8]):
                y = j * 240
                key = f"{r['source']}|{r['block']}|{r['texture']}"
                current = mapping.get(key, {}).get('path', r['patched'])
                draw.text((5, y + 2), f"#{r['id']} {r['source']} b{r['block']} t{r['texture']}", font=font, fill='white')
                for x, path, caption in [(8, r['original'], '원본'), (580, current, '기존 재제작' if key in mapping else 'v0.5')]:
                    img = Image.open(ROOT / path).convert('RGBA')
                    # 이름판은 1.5배, 큰 이미지는 화면 전체가 보이도록 비율 유지한다.
                    scale = min(1.5, 548 / img.width, 200 / img.height)
                    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.NEAREST)
                    bg = Image.new('RGBA', img.size, '#62738b'); bg.alpha_composite(img)
                    page.paste(bg.convert('RGB'), (x, y + 32))
                    draw.text((x + 420, y + 12), caption, font=font, fill='white')
            page.save(pages / f'{group}-{start // 8 + 1:02d}.png')
    print('기존 재제작 동결', len(mapping), '개 / 검수 대상', len(rows), '종')

if __name__ == '__main__': main()
