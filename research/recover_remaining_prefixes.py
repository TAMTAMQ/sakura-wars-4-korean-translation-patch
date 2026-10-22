"""추가로 대조한 짧은 음성 대사 51개의 전체 문안과 미번역 접두부 복원."""
import json
from recover_dialogue_prefixes import ROOT,restore


def main():
    entries=json.loads((ROOT/'work/qa/dialogue/other-prefixes.json').read_text(encoding='utf-8'))
    # 아래는 출력하여 읽은 전체 일본어 원문/각 대응 한국어를 근거로 정한 개별 교정.
    replacements={
        9:'샷∈',                 # ショット의 シ가 일본어로 남은 부분 제거
        10:'영차∈',              # そ〜れっ의 힘주는 구호
        11:'어흥～∈',            # 동물 흉내의 일본어 が 잔재
        15:'아멘∈',              # アーメン의 첫 글자 잔재
        21:'으윽…',              # うぐっ의 일본어 첫 글자 잔재
        24:'으윽…',              # ぐうっ/ぬうっ 두 고통 신음의 첫 글자 잔재
        29:'…치쿠젠니',          # 앞쪽 치가 기존에 남아 있어 새 꼬리를 붙이면 치치쿠젠니가 되는 문제
        33:'냐，냐．',            # 고양이 흉내 み、みー의 일본어 첫 글자 잔재
        34:'냐아．',              # 고양이 흉내 ふみゃー의 일본어 첫 글자 잔재
        44:'칸나…',              # 이름 カンナ가 カ응으로 남은 부분
    }
    restore('20261022-dialogue-prefixes-extra',entries,list(range(len(entries))),replacements)


if __name__=='__main__':main()
