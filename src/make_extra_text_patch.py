"""대사 추출에서 빠져 일본어로 남은 짧은 문자열을 제자리에서 한국어로 바꾸는 패치를 만든다.

  - LIPSYNC1~4: 표가 입 모양 데이터 꼬리 「f」를 가리켜 추출기가 놓친 짧은 외침
    (「決め∈」 복원 때와 같은 구조: off_b → 'f' 00 → 실제 자막)
  - ADVDATA/APPEND/APPEND.BIN: 부록의 장면 제목·음악 목록 일부
  - MINIGAME/MGJT.BIN: 마작 메뉴·역 이름·경기 번호

번역문은 원문 문자열 자리(뒤따르는 0 채움 포함) 안에 들어가야 한다. 남는 자리는 0으로 채운다.
폰트의 0x88~0x8F 한자 칸은 한글로 바뀌어 있어, 이 범위 한자가 섞인 미번역 문자열은 엉뚱한 한글로 보였다.
출력: config/code-patches-extra-text.json (build.py가 원본 byte를 확인하고 적용한다)
"""
import json
from pathlib import Path

from build import encode, readjson

ROOT = Path(__file__).resolve().parents[1]
SHOUT = {'はっ！': '하앗∈', '次っ！': '다음∈', 'クッ！': '큭∈', 'くっ！': '큭∈', 'チッ！': '칫∈',
         '勝負！': '승부∈', 'あん！': '아앙∈', 'ん……': '음…', 'へ〓': '에〓'}
LIP = {'ADVDATA/LIPSYNC1.LIP': [0x27E1F, 0x27E32, 0x27E99, 0x2A1E0, 0x2BADC, 0x2C22C, 0x2C242],
       'ADVDATA/LIPSYNC2.LIP': [0x4CC06, 0x4CC19, 0x4CC80, 0x4EFC7, 0x508C3, 0x51013, 0x51029],
       'ADVDATA/LIPSYNC3.LIP': [0x447A9, 0x447BC, 0x44823, 0x46B6A, 0x48466, 0x48BB6, 0x48BCC],
       'ADVDATA/LIPSYNC4.LIP': [0x1DC1B, 0x1E852, 0x203EE, 0x20ADD, 0x2252D, 0x27572, 0x28A3A, 0x2A477,
                                0x32E73, 0x32E86, 0x32EED, 0x35234, 0x36B30, 0x37280, 0x37296]}
APPEND = {'大神華撃団・参上∈': '오오가미 화격단∈', '教会。': '교회．', '成敗！': '처단∈',
          '‰！帝　～最終幕～': '‰！제　～최종막～', 'こころ': '마음', '帝都動乱': '제도 동란',
          '一触即発': '일촉즉발', 'お昼寝': '낮잠', '幽明異境': '유명이경', '激震': '격진', 'ミカサ': '미카사',
          '迅雷': '우레', '敗北': '패배', '‰！帝国華撃団': '‰！제국화격단', '絶対運命のタンゴ': '절대운명의 탱고',
          '激突': '격돌', '兆し': '조짐', '作戦会議': '작전 회의', '雄叫び': '함성', '道化': '광대',
          '決戦！巨大蒸気獣': '결전！거대 증기수', '未来（ボヤージュ）': '미래（보야주）', '祈り': '기도', '雅嵐': '가란'}
MGJT = {'自由対戦': '자유 대전', '役一覧': '역 목록', '遊戯終了': '게임 종료', 'ページ': '페이지', '終了': '종료',
        '対戦者変更': '상대 변경', '戻る': '뒤로', 'はい': '예', 'いいえ': '아니오', '鳥！': '새∈',
        '修道服と機関銃': '수녀복과 기관총', '演目【西遊記】': '작품【서유기】', '演目【青い鳥】': '작품【파랑새】',
        '星組': '성조', '親友': '친우', '学友': '학우', 'ピンク': '핑크', 'レッド': '레드', 'ブルー': '블루',
        '男の園': '남자들', '風組': '풍조', '薔薇組': '장미조', '演目【リア王】三姉妹': '작품【리어왕】세 자매',
        '巴里華撃団特別コーチ': '파리화격단 특별 코치', '深川邸探索': '저택 탐색', '花組男役三人娘': '화조 남역 세 소녀',
        '花組身長トップ３': '화조 장신 톱３', '帝劇古株組': '제극 고참조', '帝劇転勤組': '제극 전근조',
        '巴里華撃団スカウト組': '파리화격단 스카우트조', '花組黒髪三人娘': '화조 흑발 세 소녀',
        '華撃団五人娘': '화격단 오인방', '破邪剣征　桜花天舞': '파사검정 앵화천무',
        '神崎風塵流　紫仙燕子花': '칸자키 풍진류 자선연자화', '征　遠　鎮': '정　원　진',
        '超絶　猛火赤龍∵∩': '초절 맹화적룡∵∩', '落花流水': '낙화유수', '紅蘭　フラッシュ': '홍란 플래시',
        '織姫　フラッシュ': '오리히메 플래시', '花火　フラッシュ': '하나비 플래시', '加山　フラッシュ': '카야마 플래시',
        '大神　フラッシュ': '오오가미 플래시', 'ロン': '론', '第１局': '제１국', '第２局': '제２국', '最終局': '최종국',
        '同種２組': '동종２조', '同色２組': '동색２조', '合体攻撃': '합체 공격',
        **{f'第{n}試合': f'제{n}경기' for n in ['１', '２', '３', '４', '５', '６', '７', '８', '９', '１０', '１１', '１２', '１３']}}
# 원본과 같은 바이트로 남은 위치(2026-10-24 전수 검사). 1ST_READ·ESM 등의 오류 메시지·이진 데이터는 대상이 아니다.
OFFSETS = {
    'ADVDATA/APPEND/APPEND.BIN': [0x1070C, 0x10A57, 0x11115, 0x11A03, 0x11A16, 0x11A63, 0x11A6C, 0x11A9C, 0x11AD0,
                                  0x11AD9, 0x11ADE, 0x11B1C, 0x11B8F, 0x11B94, 0x11BAC, 0x11CCB, 0x11CFD, 0x11D22,
                                  0x11D58, 0x11D5F, 0x11D64, 0x11DE0, 0x11DFC, 0x11E8A],
    'MINIGAME/MGJT.BIN': [0x366EE, 0x36704, 0x36714, 0x3773E, 0x37909, 0x38D30, 0x38D40, 0x38E43, 0x38E48, 0x3D7FB,
                          0x3D820, 0x3D874, 0x3D892, 0x3D8A1, 0x3D974, 0x3D997, 0x3D9AB, 0x3D9C4, 0x3D9EA, 0x3DAA8,
                          0x3DAAF, 0x3DAB4, 0x3DBCA, 0x3DC85, 0x3DC9A, 0x3DD0A, 0x3DD19, 0x3DD46, 0x3DD51, 0x3DD5C,
                          0x3DD95, 0x3DDA4, 0x3DDE5, 0x3DDF8, 0x3DE2C, 0x3DE4A, 0x3DECF, 0x3DF39, 0x3DF4A, 0x3DFC0,
                          0x3DFF3, 0x3E004, 0x3E10A, 0x3EE3B, 0x3EE44, 0x3EE4D, 0x3EE56, 0x3EE5F, 0x3EE68, 0x3EE71,
                          0x3EE7A, 0x3EE83, 0x3EE8C, 0x3EE97, 0x3EEA2, 0x3EEAD, 0x3EEB8, 0x3EEBF, 0x3EEC6, 0x40BDB,
                          0x40C35, 0x40C3E, 0x40C66, 0x40C91, 0x40CAF, 0x40CBE, 0x40CF4, 0x40D10, 0x40E08, 0x40EC3,
                          0x40ED8, 0x40F48, 0x40F57, 0x40F84, 0x40F8F, 0x40FBC, 0x40FC1, 0x41006, 0x41090, 0x4109F,
                          0x410AC]}


def main():
    codes = readjson(ROOT / 'config/encoding.json')
    patches, fails = [], []
    jobs = [(rel, offs, SHOUT) for rel, offs in LIP.items()]
    jobs += [(rel, OFFSETS[rel], table) for rel, table in
             (('ADVDATA/APPEND/APPEND.BIN', APPEND), ('MINIGAME/MGJT.BIN', MGJT))]
    for rel, offs, table in jobs:
        data = (ROOT / 'originals/v05' / rel).read_bytes()
        disc = (ROOT / 'originals/disc' / rel).read_bytes()
        for off in offs:
            end = data.index(0, off)
            if data[off:end + 1] != disc[off:end + 1]:
                fails.append((rel, hex(off), '원본과 다름'))
                continue
            src = data[off:end].decode('cp932')
            if src not in table:
                fails.append((rel, hex(off), '번역 없음', src))
                continue
            room = end
            while room + 1 < len(data) and data[room + 1] == 0:  # 뒤따르는 0 채움(마지막 하나는 NUL로 남김)
                room += 1
            new = encode(table[src], codes)
            if len(new) > room - off:
                fails.append((rel, hex(off), '자리 부족', src, table[src], len(new), room - off))
                continue
            new += bytes(max(end + 1 - off - len(new), 1))
            patches.append({'file': rel, 'offset': off, 'original_hex': data[off:off + len(new)].hex(),
                            'new_hex': new.hex(), 'note': f'미추출 문자열 {src} → {table[src]} (make_extra_text_patch.py)'})
    for f in fails:
        print('실패', f)
    out = ROOT / 'config/code-patches-extra-text.json'
    out.write_text(json.dumps({'patches': patches}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('패치', len(patches), '실패', len(fails))


if __name__ == '__main__':
    main()
